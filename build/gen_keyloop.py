# Gold Hunter - Tasten-Schleife von Main.vi (Event-Struktur), von gen_main.py eingebunden.
#   Tasten -> Key_Send; Klick aufs X oben rechts -> Ende; Klick in den oberen Rand (DRAG_Y) und Ziehen -> Fenster verschieben.
#   Mausereignisse fuer das Verschieben gehen NICHT an Key_Send (sonst fuellt Mouse Move die Tasten-Queue).
from gh_lib import *

CLOSE_X, CLOSE_Y = W - 48, 40         # Klickfeld des X oben rechts im Bild (Pixel)
DRAG_Y = 30                           # oberer Rand, an dem man das Fenster mit der Maus verschieben kann (Pixel)
B = '\\3A'
PB = 'Front Panel Window' + B + 'Panel Bounds'


def key_loop():
    """liefert das AIXML der Schleife; erwartet im Hauptdiagramm 11.k (Channels), 16.vi (This VI), 24.v (0) und 26.v (0)"""
    u = [6000]
    L = []

    def nu():
        u[0] += 1
        return u[0]

    lp = 100
    L.append('  <Constant _name="not dragging" type="bool" value="false" outputs="value:30.v" uid="30" uid_parent="root"/>')
    L.append(f'  <Structure _name="While Loop" count="" uid="{lp}" uid_parent="root" label="Keys">')
    L.append(f'    <Tunnel _id="In1" inputs="value:11.k" outputs="value:101.v" uid="101" uid_parent="{lp}"/>')
    L.append(f'    <Tunnel _id="In2" inputs="value:16.vi" outputs="value:105.v" uid="105" uid_parent="{lp}"/>')
    # Schieberegister: Tasten-Geschichte (Cheat), Ziehen an/aus, Griffpunkt x/y
    for sid, init, left, right in (('102', '24.v', '103', '150.h'), ('106', '30.v', '107', '141.drag'),
                                   ('108', '26.v', '109', '141.gx'), ('118', '26.v', '119', '141.gy')):
        L.append(f'    <ShiftReg uid="{sid}" uid_parent="{lp}">')
        L.append(f'      <Left inputs="value:{init}" outputs="value:{left}.v" uid="{left}" uid_parent="{sid}"/>')
        L.append(f'      <Right inputs="value:{right}" outputs="value:" uid="{int(sid) + 50}" uid_parent="{sid}"/>')
        L.append('    </ShiftReg>')
    ev = 110
    L.append(f'    <Structure _name="Event Structure" uid="{ev}" uid_parent="{lp}">')
    ins = ['107.v', '109.v', '119.v', '105.v']
    for k, src in enumerate(ins, 1):
        L.append(f'      <Tunnel _id="In{k}" inputs="value:{src}" uid="{nu()}" uid_parent="{ev}"/>')

    def const(f, typ, val, name=None, ind='        '):
        x = nu()
        n = f'_name="{name}" ' if name else ''
        L.append(f'{ind}<Constant {n}type="{typ}" value="{val}" outputs="value:{x}.v" uid="{x}" uid_parent="{f}"/>')
        return f'{x}.v'

    def node(f, prim, ins_, outs_, extra='', ind='        '):
        x = nu()
        o = ','.join(f'{t}:{x}.o{k}' for k, t in enumerate(outs_))
        i = ','.join(f'{t}:{n}' for t, n in ins_)
        e = f' {extra}' if extra else ''
        L.append(f'{ind}<Node _name="{prim}"{e} inputs="{i}" outputs="{o}" uid="{x}" uid_parent="{f}"/>')
        return [f'{x}.o{k}' for k in range(len(outs_))]

    def frame(selector, body):
        f = nu()
        L.append(f'      <CaseFrame selector="{selector}" uid="{f}" uid_parent="{ev}">')
        inner = []
        for k in range(1, len(ins) + 1):
            t = nu()
            L.append(f'        <Tunnel _id="In{k}" outputs="value:{t}.v" uid="{t}" uid_parent="{f}"/>')
            inner.append(f'{t}.v')
        # Ausgaenge: ScanCode, Released, Quit, Send (an Key_Send), Drag, GrabX, GrabY
        for k, o in enumerate(body(f, inner), 1):
            L.append(f'        <Tunnel _id="Out{k}" inputs="value:{o}" uid="{nu()}" uid_parent="{f}"/>')
        L.append('      </CaseFrame>')

    def key(released):
        def body(f, i):
            sc, = node(f, 'Event Data Node', [], ['ScanCode'], 'fields="ScanCode"')
            sc32, = node(f, 'To Long Integer', [('number', sc)], ['32bit integer'])
            rel, no, yes = const(f, 'bool', 'true' if released else 'false'), const(f, 'bool', 'false'), const(f, 'bool', 'true')
            return [sc32, rel, no, yes, i[0], i[1], i[2]]
        return body

    frame(' Key Down ', key(False))
    frame(' Key Up ', key(True))

    def stop(f, i):
        x = nu()
        L.append(f'        <Control _name="Stop" type="bool" style="latched" value="false" outputs="value:{x}.v" uid="{x}" uid_parent="{f}"/>')
        m1, no, yes = const(f, 'int32', '-1'), const(f, 'bool', 'false'), const(f, 'bool', 'true')
        return [m1, no, f'{x}.v', yes, i[0], i[1], i[2]]
    frame(' &quot;Stop&quot;' + B + ' Value Change ', stop)

    def close(f, i):
        yes = const(f, 'bool', 'true', 'discard')
        x = nu()
        L.append(f'        <Node _name="Event Filter Node" fields="Discard?" inputs="Discard?:{yes}" outputs="" uid="{x}" uid_parent="{f}"/>')
        m1, no = const(f, 'int32', '-1'), const(f, 'bool', 'false')
        return [m1, no, yes, yes, i[0], i[1], i[2]]
    frame(' Panel Close? ', close)

    def coords(f):
        c, = node(f, 'Event Data Node', [], ['Coords'], 'fields="Coords"')
        return node(f, 'Unbundle By Name', [('input cluster', c)], ['Horizontal', 'Vertical'], 'fields="Horizontal,Vertical"')

    def down(f, i):
        h, v = coords(f)
        right, = node(f, 'Greater Or Equal?', [('x', h), ('y', const(f, 'int32', CLOSE_X, 'X button left'))], ['x &gt;= y?'])
        upper, = node(f, 'Less Or Equal?', [('x', v), ('y', const(f, 'int32', CLOSE_Y, 'X button bottom'))], ['x &lt;= y?'])
        hit, = node(f, 'And', [('x', right), ('y', upper)], ['x .and. y?'])
        top, = node(f, 'Less Or Equal?', [('x', v), ('y', const(f, 'int32', DRAG_Y, 'drag border'))], ['x &lt;= y?'])
        nohit, = node(f, 'Not', [('x', hit)], ['.not. x?'])
        drag, = node(f, 'And', [('x', top), ('y', nohit)], ['x .and. y?'])
        m1, no = const(f, 'int32', '-1'), const(f, 'bool', 'false')
        return [m1, no, hit, hit, drag, h, v]          # nur das X geht an Key_Send (Quit)
    frame(' &quot;Screen&quot;' + B + ' Mouse Down ', down)

    def release(f, i):
        m1, no = const(f, 'int32', '-1'), const(f, 'bool', 'false')
        return [m1, no, no, no, no, i[1], i[2]]
    frame(' &quot;Screen&quot;' + B + ' Mouse Up ', release)
    frame(' &quot;Screen&quot;' + B + ' Mouse Leave ', release)

    def move(f, i):
        h, v = coords(f)
        dx, = node(f, 'Subtract', [('x', h), ('y', i[1])], ['x-y'])
        dy, = node(f, 'Subtract', [('x', v), ('y', i[2])], ['x-y'])
        cs = nu()
        L.append(f'        <Structure _name="Case Structure" selectin="{i[0]}" uid="{cs}" uid_parent="{f}">')
        for k, src in enumerate((i[3], dx, dy), 1):
            L.append(f'          <Tunnel _id="In{k}" inputs="value:{src}" uid="{nu()}" uid_parent="{cs}"/>')
        for sel in ('True', 'False'):
            fr = nu()
            L.append(f'          <CaseFrame selector="{sel}" selectout="" uid="{fr}" uid_parent="{cs}">')
            t = []
            for k in range(1, 4):
                x = nu()
                L.append(f'            <Tunnel _id="In{k}" outputs="value:{x}.v" uid="{x}" uid_parent="{fr}"/>')
                t.append(f'{x}.v')
            if sel == 'True':                          # Fenster um den Versatz zum Griffpunkt verschieben
                e0 = const(fr, ERR, ERR_V, 'no error', '            ')
                x = nu()
                L.append(f'            <Call target="Window_Move.vi" inputs="VI:{t[0]},DX:{t[1]},DY:{t[2]},error in:{e0}" outputs="error out:" uid="{x}" uid_parent="{fr}"/>')
            L.append('          </CaseFrame>')
        L.append('        </Structure>')
        m1, no = const(f, 'int32', '-1'), const(f, 'bool', 'false')
        return [m1, no, no, no, i[0], i[1], i[2]]
    frame(' &quot;Screen&quot;' + B + ' Mouse Move ', move)

    for k, n in enumerate(('141.sc', '141.up', '141.quit', '141.send', '141.drag', '141.gx', '141.gy'), 1):
        L.append(f'      <Tunnel _id="Out{k}" outputs="value:{n}" uid="{nu()}" uid_parent="{ev}"/>')
    L.append('    </Structure>')
    # Key_Send nur fuer Tasten, Stop, Panel Close und das X
    cs = 160
    L.append(f'    <Structure _name="Case Structure" selectin="141.send" uid="{cs}" uid_parent="{lp}">')
    for k, src in enumerate(('101.v', '141.sc', '141.up', '141.quit', '103.v'), 1):
        L.append(f'      <Tunnel _id="In{k}" inputs="value:{src}" uid="{nu()}" uid_parent="{cs}"/>')
    for sel in ('True', 'False'):
        fr = nu()
        L.append(f'      <CaseFrame selector="{sel}" selectout="" uid="{fr}" uid_parent="{cs}">')
        t = []
        for k in range(1, 6):
            x = nu()
            L.append(f'        <Tunnel _id="In{k}" outputs="value:{x}.v" uid="{x}" uid_parent="{fr}"/>')
            t.append(f'{x}.v')
        if sel == 'True':
            e0 = const(fr, ERR, ERR_V, 'no error')
            ks = nu()
            L.append(f'        <Call target="Key_Send.vi" inputs="Channels:{t[0]},ScanCode:{t[1]},Released:{t[2]},Quit:{t[3]},History:{t[4]},error in:{e0}" '
                     f'outputs="Quit out:{ks}.q,History out:{ks}.h,error out:" uid="{ks}" uid_parent="{fr}"/>')
            outs = [f'{ks}.q', f'{ks}.h']
        else:
            outs = [const(fr, 'bool', 'false'), t[4]]
        for k, o in enumerate(outs, 1):
            L.append(f'        <Tunnel _id="Out{k}" inputs="value:{o}" uid="{nu()}" uid_parent="{fr}"/>')
        L.append('      </CaseFrame>')
    L.append(f'      <Tunnel _id="Out1" outputs="value:150.q" uid="{nu()}" uid_parent="{cs}"/>')
    L.append(f'      <Tunnel _id="Out2" outputs="value:150.h" uid="{nu()}" uid_parent="{cs}"/>')
    L.append('    </Structure>')
    L.append(f'    <Condition inputs="value:150.q" value="stop" uid="151" uid_parent="{lp}"/>')
    L.append('  </Structure>')
    return '\n'.join(L)
