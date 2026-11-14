# Gold Hunter - gemeinsame Typen, Konstanten und der AIXML-Helfer (Klasse Doc aus Pauls Hoehenflug uebernommen)
import os
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))

ERR = 'cluster{bool.status,int32.code,string.source}'
ERR_V = '[false,0,]'
POS = 'cluster{int32.X,int32.Y}'
TILES = 'array.2{uint8}'
RECT = 'cluster{int16.left,int16.top,int16.right,int16.bottom}'
IMG = ('cluster{int32.image type,int32.image depth,array{uint8}.image,array{uint8}.mask,'
       'array{uint32}.colors,cluster{int16.left,int16.top,int16.right,int16.bottom}.Rectangle}')
IMG_V = '[0,0,[],[],[],[0,0,0,0]]'
SPRITES = f'array{{{IMG}}}'
# ein Raum der Welt: ID "305" = Tiefe 3, Spalte 5
ROOM = f'cluster{{string.ID,int32.Depth,int32.Column,{TILES}.Tiles}}'
ROOM_V = '[,0,0,[]]'
ROOMS = f'array{{{ROOM}}}'

# Bildschirm (Pixel): HUD oben, darunter das Spielfeld. Spielkoordinaten sind relativ zum Spielfeld.
TILE = 48
COLS, ROWS = 40, 20
W, HUD_H = COLS * TILE, 120
FIELD_H = ROWS * TILE
H = HUD_H + FIELD_H

# Kachelwerte (Room_Load): Zeichen der Raumdatei -> uint8
TILE_CODE = {'.': 0, '#': 1, '=': 2, '~': 3, 'H': 4, '|': 5, ':': 6, '<': 7, '>': 8,
             'R': 10, 'B': 11, 'Y': 12, 'r': 13, 'b': 14, 'y': 15, 'g': 16, 'G': 17, 'T': 18, 'S': 19, 'Z': 20, 'K': 21, 'P': 22}
T = TILE_CODE
# Sprite-Index = Zeile in Resources\Sprites\sprites.txt
SPR = {n.strip(): i for i, n in enumerate(open(os.path.join(ROOT, 'Resources', 'Sprites', 'sprites.txt'), encoding='utf-8')) if n.strip()}
# Startbild je Kachelwert (nur Objekte), -1 = nichts zu zeichnen
TILE_SPRITE = {T['~']: 'floor_0', T['<']: 'belt_l_0', T['>']: 'belt_r_0', T['R']: 'door_r', T['B']: 'door_b', T['Y']: 'door_y',
               T['r']: 'key_r', T['b']: 'key_b', T['y']: 'key_y', T['g']: 'gold_0', T['G']: 'hoard_0', T['T']: 'torch_0',
               T['S']: 'spider_0', T['Z']: 'snake_1', T['K']: 'skull_0', T['P']: 'claude_r_stand'}
TOP_ALIGNED = [T['~'], T['<'], T['>'], T['R'], T['B'], T['Y']]     # oben an der Kachel ausgerichtet, sonst steht das Bild auf dem Boden
DOOR_CODES = (T['R'], T['Y'])                                        # Tuer-Kachelwerte 10..12

LIBS = {'Level': 'GH_Level.lvlib', 'Engine': 'GH_Engine.lvlib', 'Render': 'GH_Render.lvlib', 'Audio': 'GH_Audio.lvlib', 'App': 'GH_App.lvlib'}
_SRC = os.path.join(ROOT, 'Source')
LIBRARY_OF = {}
for _dir, _lib in LIBS.items():
    _d = os.path.join(_SRC, _dir)
    if os.path.exists(os.path.join(_d, _lib)):
        for _f in os.listdir(_d):
            if _f.endswith('.vi'):
                LIBRARY_OF[_f] = _lib


def qualified(name):
    return f'{LIBRARY_OF[name]}:{name}' if name in LIBRARY_OF else name


def esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


class Doc:
    def __init__(self, name, desc, base=1000):
        self.name, self.desc, self.L, self.u = name, desc, [], base
        self.stack = ['root']

    def nu(self):
        self.u += 1
        return str(self.u)

    @property
    def p(self):
        return self.stack[-1]

    def add(self, s):
        self.L.append('  ' * len(self.stack) + s)

    def ctrl(self, name, typ, val, con=None, conn='required'):
        u = self.nu()
        pane = f'conIdx="{con}" connection="{conn}" ' if con is not None else ''
        self.add(f'<Control _name="{esc(name)}" type="{typ}" value="{esc(val)}" {pane}outputs="value:{u}.v" uid="{u}" uid_parent="{self.p}"/>')
        return f'{u}.v'

    def indic(self, name, typ, val, src, con=None, conn='recommended'):
        u = self.nu()
        pane = f'conIdx="{con}" connection="{conn}" ' if con is not None else ''
        self.add(f'<Indicator _name="{esc(name)}" type="{typ}" value="{esc(val)}" {pane}inputs="value:{src}" uid="{u}" uid_parent="{self.p}"/>')

    def err_in(self):
        return self.ctrl('error in', ERR, ERR_V, 11)

    def err_out(self, src):
        self.indic('error out', ERR, ERR_V, src, 15)

    def const(self, typ, val, name=None):
        u = self.nu()
        n = f'_name="{esc(name)}" ' if name else ''
        self.add(f'<Constant {n}type="{typ}" value="{esc(val)}" outputs="value:{u}.v" uid="{u}" uid_parent="{self.p}"/>')
        return f'{u}.v'

    def i32c(self, v):
        return self.const('int32', str(v))

    def _io(self, u, outs):
        o, res = [], {}
        for t in outs:
            if t.startswith('-'):
                o.append(f'{t[1:]}:')
            else:
                net = f'{u}.o{len(res)}'
                o.append(f'{t}:{net}')
                res[t] = net
        return ','.join(o), res

    def node(self, prim, ins, outs, extra=''):
        u = self.nu()
        i = ','.join(f'{t}:{n}' for t, n in ins)
        o, res = self._io(u, outs)
        ex = f' {extra}' if extra else ''
        self.add(f'<Node _name="{esc(prim)}"{ex} inputs="{i}" outputs="{o}" uid="{u}" uid_parent="{self.p}"/>')
        return res

    def call(self, target, ins, outs):
        u = self.nu()
        i = ','.join(f'{t}:{n}' for t, n in ins)
        o, res = self._io(u, outs)
        self.add(f'<Call target="{target}" inputs="{i}" outputs="{o}" uid="{u}" uid_parent="{self.p}"/>')
        return res

    # --- Kurzformen
    def add2(self, x, y): return self.node('Add', [('x', x), ('y', y)], ['x+y'])['x+y']
    def sub(self, x, y): return self.node('Subtract', [('x', x), ('y', y)], ['x-y'])['x-y']
    def mul(self, x, y): return self.node('Multiply', [('x', x), ('y', y)], ['x*y'])['x*y']
    def sel(self, s, t, f): return self.node('Select', [('s', s), ('t', t), ('f', f)], ['s? t\\3Af'])['s? t\\3Af']
    def eq(self, x, y): return self.node('Equal?', [('x', x), ('y', y)], ['x = y?'])['x = y?']
    def ne(self, x, y): return self.node('Not Equal?', [('x', x), ('y', y)], ['x != y?'])['x != y?']
    def lt(self, x, y): return self.node('Less?', [('x', x), ('y', y)], ['x &lt; y?'])['x &lt; y?']
    def gt(self, x, y): return self.node('Greater?', [('x', x), ('y', y)], ['x &gt; y?'])['x &gt; y?']
    def and_(self, x, y): return self.node('And', [('x', x), ('y', y)], ['x .and. y?'])['x .and. y?']
    def or_(self, x, y): return self.node('Or', [('x', x), ('y', y)], ['x .or. y?'])['x .or. y?']
    def not_(self, x): return self.node('Not', [('x', x)], ['.not. x?'])['.not. x?']
    def idx(self, arr, i): return self.node('Index Array', [('array', arr), ('index', i)], ['element'])['element']
    def i32(self, x): return self.node('To Long Integer', [('number', x)], ['32bit integer'])['32bit integer']
    def b01(self, x): return self.node('Boolean To (0\\2C1)', [('Boolean', x)], ['0\\2C 1'])['0\\2C 1']
    def inc(self, x): return self.node('Increment', [('x', x)], ['x+1'])['x+1']

    def qr(self, x, y):
        r = self.node('Quotient & Remainder', [('x', x), ('y', y)], ['x-y*floor(x/y)', 'floor(x/y)'])
        return r['x-y*floor(x/y)'], r['floor(x/y)']

    def unb(self, cl, fields):
        r = self.node('Unbundle By Name', [('input cluster', cl)], fields, extra=f'fields="{esc(",".join(fields))}"')
        return [r[f] for f in fields]

    def bun(self, cl, pairs):
        fields = [f for f, _ in pairs]
        r = self.node('Bundle By Name', [(f, n) for f, n in pairs] + [('input cluster', cl)], ['output cluster'],
                      extra=f'fields="{esc(",".join(fields))}"')
        return r['output cluster']

    def build_path(self, base, name):
        return self.node('Build Path', [('base path', base), ('name or relative path', name)], ['appended path'])['appended path']

    def strip(self, p):
        return self.node('Strip Path', [('path', p)], ['stripped path', '-name'])['stripped path']

    # --- Strukturen
    def begin(self, kind, attrs='', label=None):
        u = self.nu()
        lab = f' label="{esc(label)}"' if label else ''
        a = (' ' + attrs.replace('@', u)) if attrs else ''
        self.add(f'<Structure _name="{kind}"{a} uid="{u}" uid_parent="{self.p}"{lab}>')
        self.stack.append(u)
        return u

    def end(self):
        self.stack.pop()
        self.add('</Structure>')

    def tunnel_in(self, k, src, mode=None):
        u = self.nu()
        m = f' mode="{mode}"' if mode else ''
        self.add(f'<Tunnel _id="In{k}" inputs="value:{src}"{m} outputs="value:{u}.v" uid="{u}" uid_parent="{self.p}"/>')
        return f'{u}.v'

    def tunnel_out(self, k, src, mode=None, cond=None):
        u = self.nu()
        m = f' mode="{mode}"' if mode else ''
        if cond:
            m = f' cond="{cond}"' + m
        self.add(f'<Tunnel _id="Out{k}" inputs="value:{src}"{m} outputs="value:{u}.v" uid="{u}" uid_parent="{self.p}"/>')
        return f'{u}.v'

    def case(self, selector_net, ins, frames, nout):
        """Case-Struktur. frames: [(selector, body)], body(inner_inputs) -> Liste der Ausgangs-Netze."""
        cu = self.begin('Case Structure', f'selectin="{selector_net}"')
        for k, src in enumerate(ins, 1):
            self.add(f'<Tunnel _id="In{k}" inputs="value:{src}" uid="{self.nu()}" uid_parent="{cu}"/>')
        for selector, body in frames:
            f = self.nu()
            self.add(f'<CaseFrame selector="{selector}" selectout="" uid="{f}" uid_parent="{cu}">')
            self.stack.append(f)
            inner = []
            for k in range(1, len(ins) + 1):
                t = self.nu()
                self.add(f'<Tunnel _id="In{k}" outputs="value:{t}.v" uid="{t}" uid_parent="{f}"/>')
                inner.append(f'{t}.v')
            outs = body(inner)
            assert len(outs) == nout, (selector, outs)
            for k, o in enumerate(outs, 1):
                self.add(f'<Tunnel _id="Out{k}" inputs="value:{o}" uid="{self.nu()}" uid_parent="{f}"/>')
            self.stack.pop()
            self.add('</CaseFrame>')
        res = []
        for k in range(1, nout + 1):
            t = self.nu()
            self.add(f'<Tunnel _id="Out{k}" outputs="value:{t}.v" uid="{t}" uid_parent="{cu}"/>')
            res.append(f'{t}.v')
        self.end()
        return res

    def write(self, fname=None):
        txt = f'<VI _name="{qualified(self.name)}" description="{esc(self.desc)}">\n' + '\n'.join(self.L) + '\n</VI>\n'
        fname = fname or os.path.splitext(self.name)[0] + '.xml'
        open(os.path.join(HERE, fname), 'w', encoding='utf-8').write(txt)
        print('wrote', fname, len(self.L), 'lines')


def shiftreg(d, loop_uid, seed):
    """Schieberegister; liefert (linkes Netz, Platzhalter-Id). Rechts mit close_reg(d, id, netz) verbinden."""
    s, l, rr = d.nu(), d.nu(), d.nu()
    d.add(f'<ShiftReg uid="{s}" uid_parent="{loop_uid}">')
    d.add(f'  <Left inputs="value:{seed}" outputs="value:{l}.v" uid="{l}" uid_parent="{s}"/>')
    d.add(f'  <Right inputs="value:@R{rr}@" outputs="value:{rr}.v" uid="{rr}" uid_parent="{s}"/>')
    d.add('</ShiftReg>')
    return f'{l}.v', rr


def close_reg(d, rr, net):
    d.L = [x.replace(f'@R{rr}@', net) for x in d.L]
    return f'{rr}.v'
