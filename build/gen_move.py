# Gold Hunter - Bewegung von Claude und den Gegnern, aufgeteilt in kleine Inline-SubVIs (gen_play.py bindet das ein).
#   Player_Move: waagrechter Schritt (Wand, Foerderband) und Auswahl nach Modus; die vier Modi rechnen Move_Ground, Move_Air,
#   Move_Ladder und Move_Pole. Enemies_Step: Zufallszahl und Auswahl; Enemy_Walk und Enemy_Climb rechnen den Schritt.
#   Die SubVIs werden inline gesetzt (kein Aufruf zur Laufzeit), sie machen nur die Diagramme kleiner. Regeln wie vorher.
from gh_lib import *

T = TILE_CODE


def tile_reader(d, tiles, err):
    """liefert tile(x, y) -> int32 ueber Tile_Read. Tile_Read kann keinen Fehler erzeugen (nur ein Array-Zugriff): jede Abfrage
    bekommt dieselbe 'kein Fehler'-Konstante - eine Fehlerkette durch alle Abfragen legte das Diagramm in eine lange Reihe
    (Player_Move 10 000 px breit) und verhinderte, dass LabVIEW die Abfragen parallel rechnet. err bleibt unberuehrt."""
    ok = d.const(ERR, ERR_V, 'no error')

    def tile(x, y):
        r = d.call('Tile_Read.vi', [('Tiles', tiles), ('X', x), ('Y', y), ('error in', ok)], ['Tile', '-error out'])
        return d.i32(r['Tile'])
    return tile


def _lut(table, n):
    return '[' + ','.join(str(table.get(k, -1)) for k in range(n)) + ']'


class Terrain:
    """Kachel-Abfragen fuer Claude: fest, duenner Boden (Schwundboden traegt nur bis FloorPhase 2), Leiter/Seil, Stange"""

    def __init__(self, d, tiles, fphase):
        n = max(T.values()) + 1
        c = d.i32c
        self.d = d
        self.L_SOL = d.const('array{int32}', _lut({k: 1 for k in SOLID}, n), 'Solid')
        self.L_PLA = d.const('array{int32}', _lut({k: 1 for k in PLATFORM}, n), 'Thin floor')
        self.L_LAD = d.const('array{int32}', _lut({k: 1 for k in CLIMBABLE}, n), 'Ladder or rope')
        self.off = d.eq(fphase, c(2))
        self.tile = tile_reader(d, tiles, None)

    def has(self, code, tbl): return self.d.gt(self.d.idx(tbl, code), self.d.i32c(0))
    def sol(self, code): return self.has(code, self.L_SOL)
    def pla(self, code):
        d = self.d
        return d.and_(self.has(code, self.L_PLA), d.not_(d.and_(d.eq(code, d.i32c(T['~'])), self.off)))
    def lad(self, code): return self.has(code, self.L_LAD)
    def pol(self, code): return self.d.eq(code, self.d.i32c(T['|']))
    def row_top(self, y): return self.d.mul(self.d.qr(y, self.d.i32c(TILE))[1], self.d.i32c(TILE))


def px(d, v10): return d.qr(v10, d.i32c(10))[1]
def anyb(d, *v):
    out = v[0]
    for x in v[1:]:
        out = d.or_(out, x)
    return out
def allb(d, *v):
    out = v[0]
    for x in v[1:]:
        out = d.and_(out, x)
    return out
def ge(d, a, b): return d.node('Greater Or Equal?', [('x', a), ('y', b)], ['x &gt;= y?'])['x &gt;= y?']
def le(d, a, b): return d.node('Less Or Equal?', [('x', a), ('y', b)], ['x &lt;= y?'])['x &lt;= y?']


def _mover(name, desc, with_jump):
    """gemeinsamer Kopf der vier Move_*: State, (Jump), XA10 (x nach dem waagrechten Schritt) -> Terrain und Masse"""
    d = Doc(name, desc)
    st = d.ctrl('State', STATE, STATE_V, 0)
    jump = d.ctrl('Jump', 'bool', 'false', 5, 'recommended') if with_jump else None
    xa10 = d.ctrl('XA10', 'int32', '0', 7)
    e = d.err_in()
    c = d.i32c
    tiles, y10, vy10, run, vert, stand, fphase, room = d.unb(st, ['Tiles', 'Y10', 'VY10', 'Run', 'Vert', 'StandY', 'FloorPhase', 'Room'])
    t = Terrain(d, tiles, fphase)
    xa = px(d, xa10)
    m = dict(st=st, jump=jump, xa10=xa10, e=e, y10=y10, vy10=vy10, run=run, vert=vert, stand=stand, room=room, t=t,
             cx=d.add2(xa, c(16)), lf=d.add2(xa, c(BOX_L)), rt=d.add2(xa, c(BOX_R)), y=px(d, y10))
    m['feet'] = d.add2(m['y'], c(CLAUDE_H))
    m['snap10'] = d.mul(d.qr(m['cx'], c(TILE))[1], c(TILE * 10))
    return d, m


def move_ground():
    d, m = _mover('Move_Ground.vi', 'Claude on the ground, one tick: stands on a wall, thin floor or ladder top; jump; step onto a ladder or '
                  'rope (Up/Down); grab a pole over its hole; otherwise fall (Mode 2). Inline subVI of Player_Move.', True)
    c, t, cx, feet = d.i32c, m['t'], m['cx'], m['feet']
    jump, vert = m['jump'], m['vert']
    gL, gR, gC = t.tile(m['lf'], feet), t.tile(m['rt'], feet), t.tile(cx, feet)
    sup = anyb(d, t.sol(gL), t.sol(gR), t.pla(gL), t.pla(gR), t.lad(gC))
    to_lad = d.or_(d.and_(d.eq(vert, c(-1)), t.lad(t.tile(cx, d.sub(feet, c(2))))), d.and_(d.eq(vert, c(1)), t.lad(gC)))
    on_pole = d.and_(d.not_(sup), t.pol(t.tile(cx, d.add2(m['y'], c(24)))))
    no_jump = d.not_(jump)
    d.indic('Mode', 'int32', '0', d.sel(jump, c(2), d.sel(to_lad, c(1), d.sel(sup, c(0), d.sel(on_pole, c(3), c(2))))), 4)
    d.indic('X10', 'int32', '0', d.sel(d.and_(no_jump, d.or_(to_lad, on_pole)), m['snap10'], m['xa10']), 6)
    d.indic('Y10', 'int32', '0', d.sel(d.and_(no_jump, to_lad), d.add2(m['y10'], d.mul(vert, c(CLIMB10))), m['y10']), 8)
    d.indic('VY10', 'int32', '0', d.sel(jump, c(JUMP10), c(0)), 10)
    d.err_out(m['e'])
    d.write()


def move_air():
    d, m = _mover('Move_Air.vi', 'Claude in the air, one tick: gravity (parachute in the treasure room), head bump, landing on walls, thin '
                  'floors (only from above) and ladder tops, grabbing a ladder (with Up/Down), a rope or a pole while falling. Dead = landed '
                  'more than the allowed height below the last firm stand (never with the parachute). Inline subVI of Player_Move.', False)
    c, t, cx, lf, rt, feet = d.i32c, m['t'], m['cx'], m['lf'], m['rt'], m['feet']
    y10, vert = m['y10'], m['vert']
    chute = d.eq(m['room'], c(TREASURE_IDX))
    v1 = d.add2(m['vy10'], c(GRAVITY10))
    vmax = d.sel(chute, c(CHUTE10), c(VY_MAX10))
    vy = d.sel(d.gt(v1, vmax), vmax, v1)
    ay10 = d.add2(y10, vy)
    ay = px(d, ay10)
    afeet = d.add2(ay, c(CLAUDE_H))
    rising = d.lt(vy, c(0))
    bump = d.and_(rising, d.or_(t.sol(t.tile(lf, ay)), t.sol(t.tile(rt, ay))))
    a_top = t.row_top(afeet)
    crossed = d.and_(le(d, feet, a_top), ge(d, afeet, a_top))
    aL, aR, aC = t.tile(lf, afeet), t.tile(rt, afeet), t.tile(cx, afeet)
    lad_top = d.and_(t.lad(aC), d.not_(t.lad(t.tile(cx, d.sub(afeet, c(TILE))))))
    land = allb(d, d.not_(rising), crossed, anyb(d, t.sol(aL), t.sol(aR), t.pla(aL), t.pla(aR), lad_top))
    land_y = d.sub(a_top, c(CLAUDE_H))
    mid = t.tile(cx, d.add2(ay, c(24)))
    falling = d.gt(vy, c(0))
    grab_l = d.and_(t.lad(mid), d.or_(d.ne(vert, c(0)), d.and_(d.eq(mid, c(T[':'])), falling)))
    grab_p = d.and_(t.pol(mid), falling)
    grab = d.and_(d.not_(land), d.or_(grab_l, grab_p))
    d.indic('Mode', 'int32', '0', d.sel(land, c(0), d.sel(grab_l, c(1), d.sel(grab_p, c(3), c(2)))), 4)
    d.indic('X10', 'int32', '0', d.sel(grab, m['snap10'], m['xa10']), 6)
    d.indic('Y10', 'int32', '0', d.sel(land, d.mul(land_y, c(10)), d.sel(bump, y10, ay10)), 8)
    d.indic('VY10', 'int32', '0', d.sel(anyb(d, land, bump, grab), c(0), vy), 10)
    d.indic('Dead', 'bool', 'false', allb(d, land, d.gt(d.sub(land_y, m['stand']), c(MAX_FALL)), d.not_(chute)), 13)
    d.err_out(m['e'])
    d.write()


def move_ladder():
    d, m = _mover('Move_Ladder.vi', 'Claude on a ladder or rope, one tick: climb with Up/Down, stop at the top, on a floor or under a ceiling, '
                  'fall off the end of a rope, step off sideways, jump off. Inline subVI of Player_Move.', True)
    c, t, cx = d.i32c, m['t'], m['cx']
    y10, vert, jump = m['y10'], m['vert'], m['jump']
    ly10 = d.add2(y10, d.mul(vert, c(CLIMB10)))
    ly = px(d, ly10)
    lfeet = d.add2(ly, c(CLAUDE_H))
    up, down = d.eq(vert, c(-1)), d.eq(vert, c(1))
    ceiling = d.and_(up, t.sol(t.tile(cx, ly)))
    l_above = d.sub(lfeet, c(2))
    at_top = allb(d, up, d.not_(ceiling), d.not_(t.lad(t.tile(cx, l_above))))
    top_y = d.sub(d.add2(t.row_top(l_above), c(TILE)), c(CLAUDE_H))
    floor = d.and_(down, t.sol(t.tile(cx, lfeet)))
    floor_y = d.sub(t.row_top(lfeet), c(CLAUDE_H))
    rope_end = allb(d, down, d.not_(t.lad(t.tile(cx, l_above))), d.not_(t.lad(t.tile(cx, lfeet))))
    step_off = d.and_(d.ne(m['run'], c(0)), d.eq(vert, c(0)))
    d.indic('Mode', 'int32', '0', d.sel(jump, c(2), d.sel(d.or_(at_top, floor), c(0), d.sel(d.or_(rope_end, step_off), c(2), c(1)))), 4)
    d.indic('Y10', 'int32', '0', d.sel(at_top, d.mul(top_y, c(10)), d.sel(floor, d.mul(floor_y, c(10)), d.sel(ceiling, y10, ly10))), 8)
    d.indic('VY10', 'int32', '0', d.sel(jump, c(JUMP10), c(0)), 10)
    d.err_out(m['e'])
    d.write()


def move_pole():
    d, m = _mover('Move_Pole.vi', 'Claude on a pole, one tick: slide down until a floor, fall off the lower end. Inline subVI of Player_Move.', False)
    c, t, cx = d.i32c, m['t'], m['cx']
    py10 = d.add2(m['y10'], c(SLIDE10))
    py = px(d, py10)
    pfeet = d.add2(py, c(CLAUDE_H))
    p_floor = t.sol(t.tile(cx, pfeet))
    p_end = d.and_(d.not_(t.pol(t.tile(cx, d.add2(py, c(24))))), d.not_(t.pol(t.tile(cx, pfeet))))
    d.indic('Mode', 'int32', '0', d.sel(p_floor, c(0), d.sel(p_end, c(2), c(3))), 4)
    d.indic('Y10', 'int32', '0', d.sel(p_floor, d.mul(d.sub(t.row_top(pfeet), c(CLAUDE_H)), c(10)), py10), 8)
    d.err_out(m['e'])
    d.write()


def player_move():
    d = Doc('Player_Move.vi', 'Moves Claude by one tick: the step sideways (walking in Mode 0 and 2, conveyor push in Mode 0, stopped by a '
            'wall), then the mode: Move_Ground (0), Move_Ladder (1), Move_Air (2) or Move_Pole (3), all inline. Facing follows Run; '
            'StandY = last firm stand (for the fall height). Positions are tenths of a pixel.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    jump = d.ctrl('Jump', 'bool', 'false', 5, 'recommended')
    e = d.err_in()
    c = d.i32c
    tiles, x10, y10, mode, facing, run, stand, fphase = d.unb(st, ['Tiles', 'X10', 'Y10', 'Mode', 'Facing', 'Run', 'StandY', 'FloorPhase'])
    t = Terrain(d, tiles, fphase)
    x, y = px(d, x10), px(d, y10)
    feet = d.add2(y, c(CLAUDE_H))
    m0, m1, m2 = d.eq(mode, c(0)), d.eq(mode, c(1)), d.eq(mode, c(2))
    under = t.tile(d.add2(x, c(16)), feet)
    belt = d.sel(d.eq(under, c(T['<'])), c(-BELT10), d.sel(d.eq(under, c(T['>'])), c(BELT10), c(0)))
    dx = d.add2(d.sel(d.or_(m0, m2), d.mul(run, c(WALK10)), c(0)), d.sel(m0, belt, c(0)))
    nx10 = d.add2(x10, dx)
    nx = px(d, nx10)
    lead = d.sel(d.gt(dx, c(0)), d.add2(nx, c(BOX_R)), d.add2(nx, c(BOX_L)))
    wall = anyb(d, t.sol(t.tile(lead, d.add2(y, c(2)))), t.sol(t.tile(lead, d.add2(y, c(24)))), t.sol(t.tile(lead, d.sub(feet, c(2)))))
    xa10 = d.sel(d.and_(d.ne(dx, c(0)), wall), x10, nx10)
    g = d.call('Move_Ground.vi', [('State', st), ('Jump', jump), ('XA10', xa10), ('error in', e)], ['Mode', 'X10', 'Y10', 'VY10', '-error out'])
    a = d.call('Move_Air.vi', [('State', st), ('XA10', xa10), ('error in', e)], ['Mode', 'X10', 'Y10', 'VY10', 'Dead', '-error out'])
    l = d.call('Move_Ladder.vi', [('State', st), ('Jump', jump), ('XA10', xa10), ('error in', e)], ['Mode', 'Y10', 'VY10', '-error out'])
    p = d.call('Move_Pole.vi', [('State', st), ('XA10', xa10), ('error in', e)], ['Mode', 'Y10', '-error out'])

    def pick(gv, lv, av, pv): return d.sel(m0, gv, d.sel(m1, lv, d.sel(m2, av, pv)))
    n_mode = pick(g['Mode'], l['Mode'], a['Mode'], p['Mode'])
    n_x10 = pick(g['X10'], x10, a['X10'], x10)
    n_y10 = pick(g['Y10'], l['Y10'], a['Y10'], p['Y10'])
    n_vy = pick(g['VY10'], l['VY10'], a['VY10'], c(0))
    n_stand = d.sel(d.eq(n_mode, c(2)), stand, px(d, n_y10))
    n_face = d.sel(d.gt(run, c(0)), c(0), d.sel(d.lt(run, c(0)), c(1), facing))
    out = d.bun(st, [('X10', n_x10), ('Y10', n_y10), ('VY10', n_vy), ('Mode', n_mode), ('Facing', n_face), ('StandY', n_stand),
                     ('Dead', d.and_(m2, a['Dead']))])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.err_out(e)
    d.write()


# ------------------------------------------------------------------ Gegner
def _enemy_head(name, desc):
    d = Doc(name, desc)
    tiles = d.ctrl('Tiles', TILES, '[]', 0)
    en = d.ctrl('Enemy', ENEMY, '[0,0,0,1,0]', 5)
    spd = d.ctrl('Speed', 'int32', '0', 7)
    rnd = d.ctrl('Random', 'int32', '0', 9)
    e = d.err_in()
    n = max(T.values()) + 1
    L = dict(sol=d.const('array{int32}', _lut({k: 1 for k in SOLID}, n), 'Solid'),
             pla=d.const('array{int32}', _lut({k: 1 for k in PLATFORM}, n), 'Thin floor'),
             lad=d.const('array{int32}', _lut({k: 1 for k in CLIMBABLE}, n), 'Ladder or rope'))
    has = lambda code, k: d.gt(d.idx(L[k], code), d.i32c(0))
    kind, x10, y10, dir_ = d.unb(en, ['Kind', 'X10', 'Y10', 'Dir'])
    return d, dict(tile=tile_reader(d, tiles, None), has=has, kind=kind, x10=x10, y10=y10, dir=dir_, spd=spd, rnd=rnd, e=e,
                   x=px(d, x10), y=px(d, y10))


def enemy_walk():
    d, m = _enemy_head('Enemy_Walk.vi', 'One step of a walking enemy: turns at walls, doors, edges, ladder holes (skull), vanishing floors and '
                       'the room edge; a spider walks over ladder tops and, crossing a tile border at a ladder or rope, may start to climb '
                       'up or down (Random). Inline subVI of Enemies_Step.')
    c, tile, has, x10, x, y, dir_, spd = d.i32c, m['tile'], m['has'], m['x10'], m['x'], m['y'], m['dir'], m['spd']
    sol = lambda code: has(code, 'sol')
    lad = lambda code: has(code, 'lad')
    spider = d.eq(m['kind'], c(0))
    nx10 = d.add2(x10, d.mul(dir_, spd))
    nx = px(d, nx10)
    front = d.sel(d.gt(dir_, c(0)), d.add2(nx, c(31)), nx)
    ahead = tile(front, d.add2(y, c(32)))
    # Schwundboeden ('~') betreten Gegner nie: sie koennten nicht rechtzeitig herunter, bevor der Boden durchsichtig wird.
    # Steht einer schon darauf (Startplatz), darf er weiterlaufen, bis er festen Boden erreicht.
    hatch_ahead = d.eq(ahead, c(T['~']))
    on_hatch = d.eq(tile(d.add2(x, c(16)), d.add2(y, c(32))), c(T['~']))
    sup_any = anyb(d, sol(ahead), has(ahead, 'pla'), lad(ahead))
    support = d.and_(d.sel(spider, sup_any, d.or_(sol(ahead), has(ahead, 'pla'))), d.or_(d.not_(hatch_ahead), on_hatch))
    blocked = anyb(d, sol(tile(front, d.add2(y, c(16)))), d.lt(nx, c(0)), d.gt(nx, c(W - 32)), d.not_(support))
    w_x10 = d.sel(blocked, x10, nx10)
    w_dir = d.sel(blocked, d.sub(c(0), dir_), dir_)
    # Spinne an einer Leiter: beim Ueberqueren einer Kachelgrenze
    passing = allb(d, spider, d.not_(blocked), d.lt(d.qr(nx10, c(TILE * 10))[0], spd))
    colx = d.add2(d.mul(d.qr(nx, c(TILE))[1], c(TILE)), c(16))
    can_up = lad(tile(colx, d.add2(y, c(16))))
    # nur Leitern, die im Raum enden: die kleine Leiter im Boden der untersten Reihe fuehrt in den Raum darunter - dort steckte die
    # Spinne sonst unsichtbar im Loch am Bildrand fest, genau wo Claude hinunterklettert
    can_down = d.and_(lad(tile(colx, d.add2(y, c(33)))), d.lt(d.add2(y, c(33)), c(FIELD_H - TILE)))
    pick = d.qr(m['rnd'], c(4))[0]
    go_up = allb(d, passing, can_up, d.eq(pick, c(0)))
    go_down = allb(d, passing, can_down, d.not_(go_up), d.eq(pick, c(1)))
    climb = d.or_(go_up, go_down)
    d.indic('X10', 'int32', '0', d.sel(climb, d.mul(d.sub(colx, c(16)), c(10)), w_x10), 4)
    d.indic('Dir', 'int32', '0', d.sel(go_up, c(-1), d.sel(go_down, c(1), w_dir)), 6)
    d.indic('Mode', 'int32', '0', d.sel(climb, c(1), c(0)), 8)
    d.err_out(m['e'])
    d.write()


def enemy_climb():
    d, m = _enemy_head('Enemy_Climb.vi', 'One step of a climbing spider: up or down; on reaching a floor or the top it walks on in a random '
                       'direction (Random), at the end of a rope or the top of the room it turns. Inline subVI of Enemies_Step.')
    c, tile, has, y10, x, dir_, spd = d.i32c, m['tile'], m['has'], m['y10'], m['x'], m['dir'], m['spd']
    sol = lambda code: has(code, 'sol')
    lad = lambda code: has(code, 'lad')
    ny10 = d.add2(y10, d.mul(dir_, spd))
    ny = px(d, ny10)
    cxm = d.add2(x, c(16))
    rdir = d.sub(d.mul(d.qr(m['rnd'], c(2))[0], c(2)), c(1))
    down_floor = d.and_(d.gt(dir_, c(0)), d.or_(sol(tile(cxm, d.add2(ny, c(32)))), ge(d, d.add2(ny, c(32)), c(FIELD_H))))
    floor_y = d.sub(d.mul(d.qr(d.add2(ny, c(32)), c(TILE))[1], c(TILE)), c(32))
    down_end = allb(d, d.gt(dir_, c(0)), d.not_(down_floor), d.not_(lad(tile(cxm, d.add2(ny, c(31))))), d.not_(lad(tile(cxm, d.add2(ny, c(33))))))
    up_top = d.and_(d.lt(dir_, c(0)), d.not_(lad(tile(cxm, d.add2(ny, c(31))))))
    top_y = d.sub(d.mul(d.inc(d.qr(d.add2(ny, c(31)), c(TILE))[1]), c(TILE)), c(32))
    up_wall = d.and_(d.lt(dir_, c(0)), le(d, ny, c(0)))
    d.indic('Y10', 'int32', '0', d.sel(down_floor, d.mul(floor_y, c(10)), d.sel(up_top, d.mul(top_y, c(10)), d.sel(d.or_(down_end, up_wall), y10, ny10))), 4)
    d.indic('Dir', 'int32', '0', d.sel(d.or_(down_floor, up_top), rdir, d.sel(d.or_(down_end, up_wall), d.sub(c(0), dir_), dir_)), 6)
    d.indic('Mode', 'int32', '0', d.sel(d.or_(down_floor, up_top), c(0), c(1)), 8)
    d.err_out(m['e'])
    d.write()


def enemies_step():
    d = Doc('Enemies_Step.vi', 'Moves every enemy by one tick. Snake: stays. Skull: rolls on its floor and turns at walls, doors, edges, '
            'ladder holes, vanishing floors and the room edge (Enemy_Walk). Spider: walks like the skull but also over ladder tops; when '
            'it passes a ladder or rope it may climb up or down (random), and on reaching a floor it walks on in a random direction '
            '(Enemy_Climb). Spiders never leave the room and never jump. Speeds per level (tenths of a pixel per tick). Random numbers '
            'from Seed (LCG), one per enemy and tick.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    tiles, enemies, level, seed = d.unb(st, ['Tiles', 'Enemies', 'Level', 'Seed'])
    li = clampv(d, d.sub(level, c(1)), c(0), c(2))
    sp_spider = d.idx(d.const('array{int32}', '[' + ','.join(map(str, LV_SPIDER)) + ']', 'Spider speed'), li)
    sp_skull = d.idx(d.const('array{int32}', '[' + ','.join(map(str, LV_SKULL)) + ']', 'Skull speed'), li)
    speeds = d.node('Build Array', [('element', sp_spider), ('element', c(0)), ('element', sp_skull)], ['appended array'])['appended array']
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    en = d.tunnel_in(1, enemies, 'index')
    t_, spd_t, e1 = d.tunnel_in(2, tiles), d.tunnel_in(3, speeds), d.tunnel_in(4, e)
    s_l, s_r = shiftreg(d, lp, seed)
    kind, x10, y10, dir_, mode = d.unb(en, ['Kind', 'X10', 'Y10', 'Dir', 'Mode'])
    seed2 = d.add2(d.mul(s_l, d.const('uint32', '1103515245')), d.const('uint32', '12345'))
    rnd = d.i32(d.qr(d.qr(seed2, d.const('uint32', '65536'))[1], d.const('uint32', '32768'))[0])
    spd = d.idx(spd_t, kind)
    w = d.call('Enemy_Walk.vi', [('Tiles', t_), ('Enemy', en), ('Speed', spd), ('Random', rnd), ('error in', e1)], ['X10', 'Dir', 'Mode', '-error out'])
    k = d.call('Enemy_Climb.vi', [('Tiles', t_), ('Enemy', en), ('Speed', spd), ('Random', rnd), ('error in', e1)], ['Y10', 'Dir', 'Mode', '-error out'])
    still = d.eq(kind, c(1))
    climbing = d.eq(mode, c(1))
    n_x10 = d.sel(still, x10, d.sel(climbing, x10, w['X10']))
    n_y10 = d.sel(still, y10, d.sel(climbing, k['Y10'], y10))
    n_dir = d.sel(still, dir_, d.sel(climbing, k['Dir'], w['Dir']))
    n_mode = d.sel(still, c(0), d.sel(climbing, k['Mode'], w['Mode']))
    out_arr = d.tunnel_out(1, d.bun(en, [('X10', n_x10), ('Y10', n_y10), ('Dir', n_dir), ('Mode', n_mode)]), 'index')
    d.end()
    seed_out = close_reg(d, s_r, seed2)
    d.indic('State out', STATE, STATE_V, d.bun(st, [('Enemies', out_arr), ('Seed', seed_out)]), 4)
    d.err_out(e)
    d.write()


def clampv(d, v, lo, hi):
    return d.sel(d.lt(v, lo), lo, d.sel(d.gt(v, hi), hi, v))


MOVE = (move_ground, move_air, move_ladder, move_pole, player_move, enemy_walk, enemy_climb, enemies_step)
