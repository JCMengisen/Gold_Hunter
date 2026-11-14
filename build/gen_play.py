import re
# Gold Hunter - AIXML-Quellen fuer Spiel (Engine), Bildaufbau (Render), Ton (Audio), App und den Build-Contract.
# Grund-VIs (Dateien, Kacheln, Bilder) stehen in gen_game.py.
# Aufruf: python gen_play.py [funktion ...]     ohne Argument: alle
import json
import sys
from gh_lib import *
from gen_game import lut, read_lines, moved, BASIC

c_ = None


def ge(d, a, b): return d.node('Greater Or Equal?', [('x', a), ('y', b)], ['x &gt;= y?'])['x &gt;= y?']
def le(d, a, b): return d.node('Less Or Equal?', [('x', a), ('y', b)], ['x &lt;= y?'])['x &lt;= y?']


def anyb(d, *v):
    r = v[0]
    for k in v[1:]:
        r = d.or_(r, k)
    return r


def allb(d, *v):
    r = v[0]
    for k in v[1:]:
        r = d.and_(r, k)
    return r


def clampv(d, v, lo, hi):
    return d.sel(d.lt(v, lo), lo, d.sel(d.gt(v, hi), hi, v))


def minv(d, a, b): return d.sel(d.lt(a, b), a, b)
def maxv(d, a, b): return d.sel(d.gt(a, b), a, b)
def px(d, v10): return d.qr(v10, d.i32c(10))[1]
def table(d, values, name): return d.const('array{int32}', '[' + ','.join(str(v) for v in values) + ']', name)
def counter(d, n): return d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', n)], ['initialized array'])['initialized array']
def lvl_index(d, level): return clampv(d, d.sub(level, d.i32c(1)), d.i32c(0), d.i32c(2))
def w16(d, v): return d.node('To Word Integer', [('number', v)], ['16bit integer'])['16bit integer']
def size(d, arr): return d.i32(d.node('Array Size', [('array', arr)], ['size(s)'])['size(s)'])


# gen_blit.py setzt BLIT = True fuer die Blit-Varianten der Zeichen-VIs
BLIT = False


def condition(d, loop_uid, net):
    d.add(f'<Condition inputs="value:{net}" value="stop" uid="{d.nu()}" uid_parent="{loop_uid}"/>')


def tile_reader(d, tiles, err):
    """liefert tile(x, y) -> int32 ueber Tile_Read; err ist eine Liste [netz] fuer die Fehlerkette"""
    def tile(x, y):
        r = d.call('Tile_Read.vi', [('Tiles', tiles), ('X', x), ('Y', y), ('error in', err[0])], ['Tile', 'error out'])
        err[0] = r['error out']
        return d.i32(r['Tile'])
    return tile


def put_tile(d, tiles, row, col, value_u8):
    return d.node('Replace Array Subset', [('array', tiles), ('new element/subarray', value_u8), ('index (row)', row), ('index (col)', col)],
                  ['output array'], extra='dimensions="2"')['output array']


def get_tile(d, tiles, row, col):
    return d.node('Index Array', [('array', tiles), ('index (row)', row), ('index (col)', col)], ['element'], extra='dimensions="2"')['element']


def u8(d, v): return d.node('To Unsigned Byte Integer', [('number', v)], ['unsigned 8bit integer'])['unsigned 8bit integer']


# ================================================================== Engine
def player_move():
    d = Doc('Player_Move.vi', 'Moves Claude by one tick. Ground: walk, conveyor push, jump, step onto a ladder or rope, fall off an edge, '
            'grab a pole over its hole. Air: gravity, head bump, landing on walls, thin floors (only from above) and ladder tops, '
            'grabbing a ladder (with Up/Down), a rope or a pole while falling. Ladder/rope: climb, stop at the top, floor or ceiling, '
            'step off sideways, jump off. Pole: slide down. A vanishing floor carries only while FloorPhase < 2. '
            'Dead = landed more than the allowed height below the last firm stand. Positions are tenths of a pixel.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    jump = d.ctrl('Jump', 'bool', 'false', 5, 'recommended')
    e = d.err_in()
    tiles, x10, y10, vy10, mode, facing, run, vert, stand, fphase = d.unb(
        st, ['Tiles', 'X10', 'Y10', 'VY10', 'Mode', 'Facing', 'Run', 'Vert', 'StandY', 'FloorPhase'])
    n = max(TILE_CODE.values()) + 1
    L_SOL = d.const('array{int32}', lut({k: 1 for k in SOLID}, n), 'Solid')
    L_PLA = d.const('array{int32}', lut({k: 1 for k in PLATFORM}, n), 'Thin floor')
    L_LAD = d.const('array{int32}', lut({k: 1 for k in CLIMBABLE}, n), 'Ladder or rope')
    c = d.i32c
    err = [e]
    tile = tile_reader(d, tiles, err)
    off = d.eq(fphase, c(2))

    def has(code, tbl): return d.gt(d.idx(tbl, code), c(0))
    def sol(code): return has(code, L_SOL)
    def pla(code): return d.and_(has(code, L_PLA), d.not_(d.and_(d.eq(code, c(T['~'])), off)))
    def lad(code): return has(code, L_LAD)
    def pol(code): return d.eq(code, c(T['|']))
    def row_top(y): return d.mul(d.qr(y, c(TILE))[1], c(TILE))

    x, y = px(d, x10), px(d, y10)
    feet = d.add2(y, c(CLAUDE_H))
    m0, m1, m2 = d.eq(mode, c(0)), d.eq(mode, c(1)), d.eq(mode, c(2))
    no_jump = d.not_(jump)
    under = tile(d.add2(x, c(16)), feet)
    belt = d.sel(d.eq(under, c(T['<'])), c(-BELT10), d.sel(d.eq(under, c(T['>'])), c(BELT10), c(0)))
    dx = d.add2(d.sel(d.or_(m0, m2), d.mul(run, c(WALK10)), c(0)), d.sel(m0, belt, c(0)))
    nx10 = d.add2(x10, dx)
    nx = px(d, nx10)
    lead = d.sel(d.gt(dx, c(0)), d.add2(nx, c(BOX_R)), d.add2(nx, c(BOX_L)))
    wall = anyb(d, sol(tile(lead, d.add2(y, c(2)))), sol(tile(lead, d.add2(y, c(24)))), sol(tile(lead, d.sub(feet, c(2)))))
    xa10 = d.sel(d.and_(d.ne(dx, c(0)), wall), x10, nx10)
    xa = px(d, xa10)
    cx, lf, rt = d.add2(xa, c(16)), d.add2(xa, c(BOX_L)), d.add2(xa, c(BOX_R))
    snap10 = d.mul(d.qr(cx, c(TILE))[1], c(TILE * 10))
    # ---- Boden
    gL, gR, gC = tile(lf, feet), tile(rt, feet), tile(cx, feet)
    sup = anyb(d, sol(gL), sol(gR), pla(gL), pla(gR), lad(gC))
    to_lad = d.or_(d.and_(d.eq(vert, c(-1)), lad(tile(cx, d.sub(feet, c(2))))), d.and_(d.eq(vert, c(1)), lad(gC)))
    on_pole = d.and_(d.not_(sup), pol(tile(cx, d.add2(y, c(24)))))
    g_mode = d.sel(jump, c(2), d.sel(to_lad, c(1), d.sel(sup, c(0), d.sel(on_pole, c(3), c(2)))))
    g_snap = d.and_(no_jump, d.or_(to_lad, on_pole))
    g_x10 = d.sel(g_snap, snap10, xa10)
    g_y10 = d.sel(d.and_(no_jump, to_lad), d.add2(y10, d.mul(vert, c(CLIMB10))), y10)
    g_vy = d.sel(jump, c(JUMP10), c(0))
    # ---- Luft
    v1 = d.add2(vy10, c(GRAVITY10))
    vy = d.sel(d.gt(v1, c(VY_MAX10)), c(VY_MAX10), v1)
    ay10 = d.add2(y10, vy)
    ay = px(d, ay10)
    afeet = d.add2(ay, c(CLAUDE_H))
    rising = d.lt(vy, c(0))
    bump = d.and_(rising, d.or_(sol(tile(lf, ay)), sol(tile(rt, ay))))
    a_top = row_top(afeet)
    crossed = d.and_(le(d, feet, a_top), ge(d, afeet, a_top))
    aL, aR, aC = tile(lf, afeet), tile(rt, afeet), tile(cx, afeet)
    lad_top = d.and_(lad(aC), d.not_(lad(tile(cx, d.sub(afeet, c(TILE))))))
    land = allb(d, d.not_(rising), crossed, anyb(d, sol(aL), sol(aR), pla(aL), pla(aR), lad_top))
    land_y = d.sub(a_top, c(CLAUDE_H))
    mid = tile(cx, d.add2(ay, c(24)))
    falling = d.gt(vy, c(0))
    grab_l = d.and_(lad(mid), d.or_(d.ne(vert, c(0)), d.and_(d.eq(mid, c(T[':'])), falling)))
    grab_p = d.and_(pol(mid), falling)
    grab = d.and_(d.not_(land), d.or_(grab_l, grab_p))
    a_mode = d.sel(land, c(0), d.sel(grab_l, c(1), d.sel(grab_p, c(3), c(2))))
    a_y10 = d.sel(land, d.mul(land_y, c(10)), d.sel(bump, y10, ay10))
    a_vy = d.sel(anyb(d, land, bump, grab), c(0), vy)
    a_x10 = d.sel(grab, snap10, xa10)
    dead = allb(d, m2, land, d.gt(d.sub(land_y, stand), c(MAX_FALL)))
    # ---- Leiter / Seil
    ly10 = d.add2(y10, d.mul(vert, c(CLIMB10)))
    ly = px(d, ly10)
    lfeet = d.add2(ly, c(CLAUDE_H))
    up, down = d.eq(vert, c(-1)), d.eq(vert, c(1))
    ceiling = d.and_(up, sol(tile(cx, ly)))
    l_above = d.sub(lfeet, c(2))
    at_top = allb(d, up, d.not_(ceiling), d.not_(lad(tile(cx, l_above))))
    top_y = d.sub(d.add2(row_top(l_above), c(TILE)), c(CLAUDE_H))
    floor = d.and_(down, sol(tile(cx, lfeet)))
    floor_y = d.sub(row_top(lfeet), c(CLAUDE_H))
    rope_end = allb(d, down, d.not_(lad(tile(cx, l_above))), d.not_(lad(tile(cx, lfeet))))
    step_off = d.and_(d.ne(run, c(0)), d.eq(vert, c(0)))
    l_mode = d.sel(jump, c(2), d.sel(d.or_(at_top, floor), c(0), d.sel(d.or_(rope_end, step_off), c(2), c(1))))
    l_y10 = d.sel(at_top, d.mul(top_y, c(10)), d.sel(floor, d.mul(floor_y, c(10)), d.sel(ceiling, y10, ly10)))
    l_vy = d.sel(jump, c(JUMP10), c(0))
    # ---- Rutschstange
    py10 = d.add2(y10, c(SLIDE10))
    py = px(d, py10)
    pfeet = d.add2(py, c(CLAUDE_H))
    p_floor = sol(tile(cx, pfeet))
    p_end = d.and_(d.not_(pol(tile(cx, d.add2(py, c(24))))), d.not_(pol(tile(cx, pfeet))))
    p_mode = d.sel(p_floor, c(0), d.sel(p_end, c(2), c(3)))
    p_y10 = d.sel(p_floor, d.mul(d.sub(row_top(pfeet), c(CLAUDE_H)), c(10)), py10)

    def pick(g, l, a, p): return d.sel(m0, g, d.sel(m1, l, d.sel(m2, a, p)))
    n_mode = pick(g_mode, l_mode, a_mode, p_mode)
    n_x10 = pick(g_x10, x10, a_x10, x10)
    n_y10 = pick(g_y10, l_y10, a_y10, p_y10)
    n_vy = pick(g_vy, l_vy, a_vy, c(0))
    n_stand = d.sel(d.eq(n_mode, c(2)), stand, px(d, n_y10))
    n_face = d.sel(d.gt(run, c(0)), c(0), d.sel(d.lt(run, c(0)), c(1), facing))
    out = d.bun(st, [('X10', n_x10), ('Y10', n_y10), ('VY10', n_vy), ('Mode', n_mode), ('Facing', n_face), ('StandY', n_stand), ('Dead', dead)])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.err_out(err[0])
    d.write()


def enemies_init():
    d = Doc('Enemies_Init.vi', 'Builds the enemies of a room from its tiles: S spider (Kind 0), Z snake (1), K skull (2) at their start tiles, '
            'walking left or right (by the tile position), not climbing.')
    tiles = d.ctrl('Tiles', TILES, '[]', 0)
    e = d.err_in()
    c = d.i32c
    proto = d.const(ENEMY, '[0,0,0,1,0]', 'Enemy')
    outer = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    r = f'{outer}i.v'
    row = d.tunnel_in(1, tiles, 'index')
    p1 = d.tunnel_in(2, proto)
    inner = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    col = f'{inner}i.v'
    code8 = d.tunnel_in(1, row, 'index')
    p2, r2 = d.tunnel_in(2, p1), d.tunnel_in(3, r)
    code = d.i32(code8)
    is_enemy = d.and_(ge(d, code, c(ENEMY_CODES[0])), le(d, code, c(ENEMY_CODES[1])))
    odd = d.qr(d.add2(col, r2), c(2))[0]
    en = d.bun(p2, [('Kind', d.sub(code, c(ENEMY_CODES[0]))), ('X10', d.mul(col, c(TILE * 10))), ('Y10', d.mul(r2, c(TILE * 10))),
                    ('Dir', d.sub(d.mul(odd, c(2)), c(1))), ('Mode', c(0))])
    row_out = d.tunnel_out(1, en, 'index', cond=is_enemy)
    d.end()
    all_ = d.tunnel_out(1, row_out, 'concat')
    d.end()
    d.indic('Enemies', ENEMIES, '[]', all_, 4)
    d.err_out(e)
    d.write()


def room_change():
    d = Doc('Room_Change.vi', 'Changes the room when the middle of Claude leaves the playfield: left/right to the neighbour in the same depth, '
            'up/down to the room above/below. The tiles of the old room (gold taken, doors opened) are stored in World, the new room '
            'comes from World, its enemies start again (Enemies_Init). The position moves by one room size, the fall height carries '
            'over, the arrival is the new restart point. Without a room above, Claude cannot leave the top of the playfield.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    x10, y10, room, stand, mode, world, tiles = d.unb(st, ['X10', 'Y10', 'Room', 'StandY', 'Mode', 'World', 'Tiles'])
    cx = d.add2(px(d, x10), c(16))
    cy = d.add2(px(d, y10), c(24))
    dc = d.sel(d.lt(cx, c(0)), c(-1), d.sel(ge(d, cx, c(W)), c(1), c(0)))
    dd = d.sel(d.lt(cy, c(0)), c(-1), d.sel(ge(d, cy, c(FIELD_H)), c(1), c(0)))
    here = d.idx(world, room)
    depth, column = d.unb(here, ['Depth', 'Column'])
    want_d, want_c = d.add2(depth, dd), d.add2(column, dc)
    above_d = d.sub(depth, c(1))
    none = c(-1)
    none2 = c(-1)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    r = d.tunnel_in(1, world, 'index')
    wd, wc, ad, cc = d.tunnel_in(2, want_d), d.tunnel_in(3, want_c), d.tunnel_in(4, above_d), d.tunnel_in(5, column)
    f_l, f_r = shiftreg(d, lp, none)
    a_l, a_r = shiftreg(d, lp, none2)
    d2, c2 = d.unb(r, ['Depth', 'Column'])
    f2 = d.sel(d.and_(d.eq(d2, wd), d.eq(c2, wc)), i, f_l)
    a2 = d.sel(d.and_(d.eq(d2, ad), d.eq(c2, cc)), i, a_l)
    d.end()
    found = close_reg(d, f_r, f2)
    above = close_reg(d, a_r, a2)
    change = d.and_(d.or_(d.ne(dc, c(0)), d.ne(dd, c(0))), ge(d, found, c(0)))
    world2 = d.node('Replace Array Subset', [('array', world), ('new element/subarray', d.bun(here, [('Tiles', tiles)])), ('index', room)],
                    ['output array'])['output array']
    (new_tiles,) = d.unb(d.idx(world2, found), ['Tiles'])
    ei = d.call('Enemies_Init.vi', [('Tiles', new_tiles), ('error in', e)], ['Enemies', 'error out'])
    nx10 = d.sub(x10, d.mul(dc, c(W * 10)))
    ny10 = d.sub(y10, d.mul(dd, c(FIELD_H * 10)))
    moved_st = d.bun(st, [('Room', found), ('Tiles', new_tiles), ('World', world2), ('Enemies', ei['Enemies']), ('X10', nx10), ('Y10', ny10),
                          ('StandY', d.sub(stand, d.mul(dd, c(FIELD_H)))), ('EntryX10', nx10), ('EntryY10', ny10), ('EntryMode', mode)])
    top_clamp = d.and_(d.lt(above, c(0)), d.lt(y10, c(0)))
    stay = d.bun(st, [('Y10', d.sel(top_clamp, c(0), y10))])
    d.indic('State out', STATE, STATE_V, d.sel(change, moved_st, stay), 4)
    d.indic('Changed', 'bool', 'false', change, 6)
    d.err_out(ei['error out'])
    d.write()


def items_collect():
    d = Doc('Items_Collect.vi', 'Collects the objects Claude touches (four points of his body): coin +100, gold hoard +500, key +200 and one '
            'key of its colour, torch +500 and light in all rooms. The tile becomes empty, the matching sound bit is set.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    n = max(TILE_CODE.values()) + 1
    pts = d.const('array{int32}', lut(PTS, n).replace('-1', '0'), 'Points')
    kr = d.const('array{int32}', lut({T['r']: 1}, n).replace('-1', '0'), 'Red key')
    kb = d.const('array{int32}', lut({T['b']: 1}, n).replace('-1', '0'), 'Blue key')
    ky = d.const('array{int32}', lut({T['y']: 1}, n).replace('-1', '0'), 'Yellow key')
    tch = d.const('array{int32}', lut({T['T']: 1}, n).replace('-1', '0'), 'Torch')
    snd = d.const('array{int32}', lut({T['r']: SND['key'], T['b']: SND['key'], T['y']: SND['key'], T['g']: SND['coin'], T['G']: SND['hoard'],
                                       T['T']: SND['torch']}, n).replace('-1', '0'), 'Sound')
    dxs, dys = table(d, [BOX_L, BOX_R, BOX_L, BOX_R], 'Probe X'), table(d, [16, 16, 40, 40], 'Probe Y')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    ox, oy = d.tunnel_in(1, dxs, 'index'), d.tunnel_in(2, dys, 'index')
    tb = [d.tunnel_in(k + 3, v) for k, v in enumerate((pts, kr, kb, ky, tch, snd))]
    s_l, s_r = shiftreg(d, lp, st)
    tiles, x10, y10, score, k1, k2, k3, torch, sound = d.unb(s_l, ['Tiles', 'X10', 'Y10', 'Score', 'KeyR', 'KeyB', 'KeyY', 'Torch', 'Sound'])
    col = clampv(d, d.qr(d.add2(px(d, x10), ox), c(TILE))[1], c(0), c(COLS - 1))
    row = clampv(d, d.qr(d.add2(px(d, y10), oy), c(TILE))[1], c(0), c(ROWS - 1))
    code8 = get_tile(d, tiles, row, col)
    code = d.i32(code8)
    take = d.and_(ge(d, code, c(T['r'])), le(d, code, c(T['T'])))
    tiles2 = put_tile(d, tiles, row, col, d.sel(take, d.const('uint8', '0'), code8))
    s2 = d.bun(s_l, [('Tiles', tiles2), ('Score', d.add2(score, d.idx(tb[0], code))), ('KeyR', d.add2(k1, d.idx(tb[1], code))),
                     ('KeyB', d.add2(k2, d.idx(tb[2], code))), ('KeyY', d.add2(k3, d.idx(tb[3], code))),
                     ('Torch', d.or_(torch, d.gt(d.idx(tb[4], code), c(0)))), ('Sound', d.or_(sound, d.idx(tb[5], code)))])
    d.end()
    d.indic('State out', STATE, STATE_V, close_reg(d, s_r, s2), 4)
    d.err_out(e)
    d.write()


def door_open():
    d = Doc('Door_Open.vi', f'Opens the door Claude touches (in the direction he faces) when he has a key of its colour: the key is used up, '
            f'all tiles of that door (one column, up to 3 tiles above and below) become empty, +{DOOR_POINTS} points, door sound.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    tiles, x10, y10, facing, k1, k2, k3, score, sound = d.unb(st, ['Tiles', 'X10', 'Y10', 'Facing', 'KeyR', 'KeyB', 'KeyY', 'Score', 'Sound'])
    x, y = px(d, x10), px(d, y10)
    probe = d.sel(d.eq(facing, c(0)), d.add2(x, c(BOX_R + 4)), d.add2(x, c(BOX_L - 4)))
    col = clampv(d, d.qr(probe, c(TILE))[1], c(0), c(COLS - 1))
    row_a = clampv(d, d.qr(d.add2(y, c(40)), c(TILE))[1], c(0), c(ROWS - 1))
    row_b = clampv(d, d.qr(d.add2(y, c(20)), c(TILE))[1], c(0), c(ROWS - 1))
    ca, cb = d.i32(get_tile(d, tiles, row_a, col)), d.i32(get_tile(d, tiles, row_b, col))
    is_door = lambda v: d.and_(ge(d, v, c(T['R'])), le(d, v, c(T['Y'])))
    code = d.sel(is_door(ca), ca, cb)
    row = d.sel(is_door(ca), row_a, row_b)
    idx = clampv(d, d.sub(code, c(T['R'])), c(0), c(2))
    keys = d.node('Build Array', [('element', k1), ('element', k2), ('element', k3)], ['appended array'])['appended array']
    have = d.idx(keys, idx)
    opening = d.and_(is_door(code), d.gt(have, c(0)))
    offs = table(d, [-3, -2, -1, 0, 1, 2, 3], 'Rows around')
    code_u8 = u8(d, code)
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    k = d.tunnel_in(1, offs, 'index')
    r0, c0, cu, op = d.tunnel_in(2, row), d.tunnel_in(3, col), d.tunnel_in(4, code_u8), d.tunnel_in(5, opening)
    t_l, t_r = shiftreg(d, lp, tiles)
    rr = clampv(d, d.add2(r0, k), c(0), c(ROWS - 1))
    cur = get_tile(d, t_l, rr, c0)
    t2 = put_tile(d, t_l, rr, c0, d.sel(d.and_(op, d.eq(cur, cu)), d.const('uint8', '0'), cur))
    d.end()
    tiles2 = close_reg(d, t_r, t2)
    keys2 = d.node('Replace Array Subset', [('array', keys), ('new element/subarray', d.sub(have, c(1))), ('index', idx)], ['output array'])['output array']
    out = d.bun(st, [('Tiles', tiles2), ('KeyR', d.idx(keys2, c(0))), ('KeyB', d.idx(keys2, c(1))), ('KeyY', d.idx(keys2, c(2))),
                     ('Score', d.add2(score, c(DOOR_POINTS))), ('Sound', d.or_(sound, c(SND['door'])))])
    d.indic('State out', STATE, STATE_V, d.sel(opening, out, st), 4)
    d.indic('Opened', 'bool', 'false', opening, 6)
    d.err_out(e)
    d.write()


def enemies_step():
    d = Doc('Enemies_Step.vi', 'Moves every enemy by one tick. Snake: stays. Skull: rolls on its floor and turns at walls, doors, edges, '
            'ladder holes and the room edge. Spider: walks like the skull but also over ladder tops; when it passes a ladder or rope it '
            'may climb up or down (random), and on reaching a floor it walks on in a random direction. Spiders never leave the room and '
            'never jump. Speeds per level (tenths of a pixel per tick). Random numbers from Seed (LCG).')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    tiles, enemies, level, seed, fphase = d.unb(st, ['Tiles', 'Enemies', 'Level', 'Seed', 'FloorPhase'])
    li = lvl_index(d, level)
    sp_spider, sp_skull = d.idx(table(d, LV_SPIDER, 'Spider speed'), li), d.idx(table(d, LV_SKULL, 'Skull speed'), li)
    speeds = d.node('Build Array', [('element', sp_spider), ('element', c(0)), ('element', sp_skull)], ['appended array'])['appended array']
    n = max(TILE_CODE.values()) + 1
    L_SOL = d.const('array{int32}', lut({k: 1 for k in SOLID}, n), 'Solid')
    L_PLA = d.const('array{int32}', lut({k: 1 for k in PLATFORM}, n), 'Thin floor')
    L_LAD = d.const('array{int32}', lut({k: 1 for k in CLIMBABLE}, n), 'Ladder or rope')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    en = d.tunnel_in(1, enemies, 'index')
    t_, spd_t = d.tunnel_in(2, tiles), d.tunnel_in(3, speeds)
    lsol, lpla, llad = d.tunnel_in(4, L_SOL), d.tunnel_in(5, L_PLA), d.tunnel_in(6, L_LAD)
    s_l, s_r = shiftreg(d, lp, seed)
    e_l, e_r = shiftreg(d, lp, e)
    err = [e_l]
    tile = tile_reader(d, t_, err)
    has = lambda code, tbl: d.gt(d.idx(tbl, code), c(0))
    sol = lambda code: has(code, lsol)
    lad = lambda code: has(code, llad)
    sup_any = lambda code: anyb(d, sol(code), has(code, lpla), lad(code))
    kind, x10, y10, dir_, mode = d.unb(en, ['Kind', 'X10', 'Y10', 'Dir', 'Mode'])
    seed2 = d.add2(d.mul(s_l, d.const('uint32', '1103515245')), d.const('uint32', '12345'))
    rnd = d.i32(d.qr(d.qr(seed2, d.const('uint32', '65536'))[1], d.const('uint32', '32768'))[0])
    spd = d.idx(spd_t, kind)
    spider = d.eq(kind, c(0))
    x, y = px(d, x10), px(d, y10)
    # ---- waagrecht
    nx10 = d.add2(x10, d.mul(dir_, spd))
    nx = px(d, nx10)
    front = d.sel(d.gt(dir_, c(0)), d.add2(nx, c(31)), nx)
    ahead = tile(front, d.add2(y, c(32)))
    support = d.sel(spider, sup_any(ahead), d.or_(sol(ahead), has(ahead, lpla)))
    blocked = anyb(d, sol(tile(front, d.add2(y, c(16)))), d.lt(nx, c(0)), d.gt(nx, c(W - 32)), d.not_(support))
    w_x10 = d.sel(blocked, x10, nx10)
    w_dir = d.sel(blocked, d.sub(c(0), dir_), dir_)
    # Spinne an einer Leiter: beim Ueberqueren einer Kachelgrenze
    passing = allb(d, spider, d.not_(blocked), d.lt(d.qr(nx10, c(TILE * 10))[0], spd))
    colx = d.add2(d.mul(d.qr(nx, c(TILE))[1], c(TILE)), c(16))
    can_up = lad(tile(colx, d.add2(y, c(16))))
    can_down = lad(tile(colx, d.add2(y, c(33))))
    pick = d.qr(rnd, c(4))[0]
    go_up = allb(d, passing, can_up, d.eq(pick, c(0)))
    go_down = allb(d, passing, can_down, d.not_(go_up), d.eq(pick, c(1)))
    climb = d.or_(go_up, go_down)
    w_mode = d.sel(climb, c(1), c(0))
    w_x10b = d.sel(climb, d.mul(d.sub(colx, c(16)), c(10)), w_x10)
    w_dirb = d.sel(go_up, c(-1), d.sel(go_down, c(1), w_dir))
    # ---- klettern (nur Spinnen)
    ny10 = d.add2(y10, d.mul(dir_, spd))
    ny = px(d, ny10)
    cxm = d.add2(x, c(16))
    rdir = d.sub(d.mul(d.qr(rnd, c(2))[0], c(2)), c(1))
    down_floor = d.and_(d.gt(dir_, c(0)), d.or_(sol(tile(cxm, d.add2(ny, c(32)))), ge(d, d.add2(ny, c(32)), c(FIELD_H))))
    floor_y = d.sub(d.mul(d.qr(d.add2(ny, c(32)), c(TILE))[1], c(TILE)), c(32))
    down_end = allb(d, d.gt(dir_, c(0)), d.not_(down_floor), d.not_(lad(tile(cxm, d.add2(ny, c(31))))), d.not_(lad(tile(cxm, d.add2(ny, c(33))))))
    up_top = d.and_(d.lt(dir_, c(0)), d.not_(lad(tile(cxm, d.add2(ny, c(31))))))
    top_y = d.sub(d.mul(d.inc(d.qr(d.add2(ny, c(31)), c(TILE))[1]), c(TILE)), c(32))
    up_wall = d.and_(d.lt(dir_, c(0)), le(d, ny, c(0)))
    c_mode = d.sel(d.or_(down_floor, up_top), c(0), c(1))
    c_y10 = d.sel(down_floor, d.mul(floor_y, c(10)), d.sel(up_top, d.mul(top_y, c(10)), d.sel(d.or_(down_end, up_wall), y10, ny10)))
    c_dir = d.sel(d.or_(down_floor, up_top), rdir, d.sel(d.or_(down_end, up_wall), d.sub(c(0), dir_), dir_))
    # ---- zusammenfuehren
    still = d.eq(kind, c(1))
    climbing = d.eq(mode, c(1))
    n_x10 = d.sel(still, x10, d.sel(climbing, x10, w_x10b))
    n_y10 = d.sel(still, y10, d.sel(climbing, c_y10, y10))
    n_dir = d.sel(still, dir_, d.sel(climbing, c_dir, w_dirb))
    n_mode = d.sel(still, c(0), d.sel(climbing, c_mode, w_mode))
    en2 = d.bun(en, [('X10', n_x10), ('Y10', n_y10), ('Dir', n_dir), ('Mode', n_mode)])
    out_arr = d.tunnel_out(1, en2, 'index')
    d.end()
    seed_out = close_reg(d, s_r, seed2)
    err_out = close_reg(d, e_r, err[0])
    d.indic('State out', STATE, STATE_V, d.bun(st, [('Enemies', out_arr), ('Seed', seed_out)]), 4)
    d.err_out(err_out)
    d.write()


def hit_check():
    d = Doc('Hit_Check.vi', 'Does an enemy touch Claude? Compares Claude\'s box (x 8..23, y 6..47 of his 32 x 48 picture) with the box of '
            'each enemy (spider, low snake that can be jumped over, skull).')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    x10, y10, enemies = d.unb(st, ['X10', 'Y10', 'Enemies'])
    x, y = px(d, x10), px(d, y10)
    cl, cr, ct, cb = d.add2(x, c(CBOX[0])), d.add2(x, c(CBOX[1])), d.add2(y, c(CBOX[2])), d.add2(y, c(CBOX[3]))
    tl, tr, tt, tb = (table(d, [b[k] for b in EBOX], n) for k, n in enumerate(('Box left', 'Box right', 'Box top', 'Box bottom')))
    f = d.const('bool', 'false')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    en = d.tunnel_in(1, enemies, 'index')
    a = [d.tunnel_in(k + 2, v) for k, v in enumerate((cl, cr, ct, cb, tl, tr, tt, tb))]
    h_l, h_r = shiftreg(d, lp, f)
    kind, ex10, ey10 = d.unb(en, ['Kind', 'X10', 'Y10'])
    ex, ey = px(d, ex10), px(d, ey10)
    el, er = d.add2(ex, d.idx(a[4], kind)), d.add2(ex, d.idx(a[5], kind))
    et, eb = d.add2(ey, d.idx(a[6], kind)), d.add2(ey, d.idx(a[7], kind))
    hit = allb(d, d.lt(a[0], er), d.lt(el, a[1]), d.lt(a[2], eb), d.lt(et, a[3]))
    h2 = d.or_(h_l, hit)
    d.end()
    d.indic('Hit', 'bool', 'false', close_reg(d, h_r, h2), 4)
    d.err_out(e)
    d.write()


def respawn():
    d = Doc('Respawn.vi', 'Puts Claude back to the arrival point of the room (after a life was lost): position and climbing mode of the '
            'arrival, standing still, enemies of the room back at their start.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    e = d.err_in()
    c = d.i32c
    ex, ey, em, tiles = d.unb(st, ['EntryX10', 'EntryY10', 'EntryMode', 'Tiles'])
    ei = d.call('Enemies_Init.vi', [('Tiles', tiles), ('error in', e)], ['Enemies', 'error out'])
    mode = d.sel(d.eq(em, c(2)), c(0), em)
    out = d.bun(st, [('X10', ex), ('Y10', ey), ('VY10', c(0)), ('Mode', mode), ('StandY', px(d, ey)), ('Run', c(0)), ('Vert', c(0)),
                     ('Dead', d.const('bool', 'false')), ('Enemies', ei['Enemies'])])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.err_out(ei['error out'])
    d.write()


def level_setup():
    d = Doc('Level_Setup.vi', 'Starts a level: all rooms as they are in the files (World = Rooms), Claude on the start tile P of the first '
            'room, no keys, no torch, enemies of the first room, phase Ready with the LEVEL message. Score, lives and highscores stay.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 5)
    level = d.ctrl('Level', 'int32', '1', 7)
    e = d.err_in()
    c = d.i32c
    (tiles,) = d.unb(d.idx(rooms, c(START_IDX)), ['Tiles'])
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    row = d.tunnel_in(1, tiles, 'index')
    hit = d.node('Search 1D Array', [('1D array', row), ('element', d.const('uint8', str(T['P']))), ('start index (0)', '')],
                 ['index of element'])['index of element']
    cols = d.tunnel_out(1, hit, 'index')
    d.end()
    found = d.node('Greater Or Equal To 0?', [('x', cols)], ['x &gt;= 0?'])['x &gt;= 0?']
    prow = d.node('Search 1D Array', [('1D array', found), ('element', d.const('bool', 'true')), ('start index (0)', '')],
                  ['index of element'])['index of element']
    pcol = d.idx(cols, prow)
    y = d.sub(d.mul(d.inc(prow), c(TILE)), c(CLAUDE_H))
    x10, y10 = d.mul(pcol, c(TILE * 10)), d.mul(y, c(10))
    ei = d.call('Enemies_Init.vi', [('Tiles', tiles), ('error in', e)], ['Enemies', 'error out'])
    f = d.const('bool', 'false')
    out = d.bun(st, [('Level', level), ('Room', c(START_IDX)), ('Tiles', tiles), ('World', rooms), ('Enemies', ei['Enemies']),
                     ('X10', x10), ('Y10', y10), ('VY10', c(0)), ('Mode', c(0)), ('Facing', c(0)), ('Run', c(0)), ('Vert', c(0)), ('StandY', y),
                     ('EntryX10', x10), ('EntryY10', y10), ('EntryMode', c(0)), ('KeyR', c(0)), ('KeyB', c(0)), ('KeyY', c(0)),
                     ('Torch', f), ('Dead', f), ('LevelStart', d.const('bool', 'true')), ('Phase', c(PH['Ready'])), ('PhaseTicks', c(0))])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.err_out(ei['error out'])
    d.write()


def game_new():
    d = Doc('Game_New.vi', f'Starts a new game: {LIVES} lives, score 0, next extra life at {EXTRA_LIFE}, level 1 (Level_Setup). '
            f'Tick starts at 0 (same rhythm of the vanishing floors every time). Demo: the same game, but in phase Demo with a fixed random seed.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 5)
    demo = d.ctrl('Demo', 'bool', 'false', 7, 'recommended')
    e = d.err_in()
    c = d.i32c
    s1 = d.bun(st, [('Lives', c(LIVES)), ('Score', c(0)), ('NextLife', c(EXTRA_LIFE)), ('DemoStep', c(0)), ('Tick', d.const('uint32', '0'))])
    ls = d.call('Level_Setup.vi', [('State', s1), ('Rooms', rooms), ('Level', c(1)), ('error in', e)], ['State out', 'error out'])
    seed, snd = d.unb(ls['State out'], ['Seed', 'Sound'])
    out = d.bun(ls['State out'], [('Phase', d.sel(demo, c(PH['Demo']), c(PH['Ready']))),
                                  ('Seed', d.sel(demo, d.const('uint32', str(DEMO_SEED)), seed)),
                                  ('Sound', d.sel(demo, c(0), d.or_(snd, c(SND['level']))))])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.err_out(ls['error out'])
    d.write()


def keys_apply():
    d = Doc('Keys_Apply.vi', 'Applies a key to the movement wishes: Left/Right set Run, ReleaseL/ReleaseR stop only the matching direction, '
            'Release stops, Up/Down set Vert, ReleaseV stops climbing.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    key = d.ctrl('Key', KEY, '0', 5, 'recommended')
    e = d.err_in()
    c = d.i32c
    k = d.i32(key)
    is_ = lambda name: d.eq(k, c(IN[name]))
    run, vert = d.unb(st, ['Run', 'Vert'])
    stop_run = anyb(d, is_('Release'), d.and_(is_('ReleaseL'), d.eq(run, c(-1))), d.and_(is_('ReleaseR'), d.eq(run, c(1))))
    run2 = d.sel(is_('Left'), c(-1), d.sel(is_('Right'), c(1), d.sel(stop_run, c(0), run)))
    vert2 = d.sel(is_('Up'), c(-1), d.sel(is_('Down'), c(1), d.sel(is_('ReleaseV'), c(0), vert)))
    d.indic('State out', STATE, STATE_V, d.bun(st, [('Run', run2), ('Vert', vert2)]), 4)
    d.err_out(e)
    d.write()


def game_play():
    d = Doc('Game_Play.vi', 'One tick of play: rhythm of the vanishing floors (FloorPhase), Claude moves (Player_Move, jump sound), takes '
            'objects (Items_Collect), opens doors (Door_Open), enemies move (Enemies_Step), Hit_Check, room change (Room_Change) and '
            f'an extra life every {EXTRA_LIFE} points (at most {MAX_LIVES}). Hit = an enemy touches Claude, Died = deadly fall.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    jump = d.ctrl('Jump', 'bool', 'false', 5, 'recommended')
    e = d.err_in()
    c = d.i32c
    tick, level = d.unb(st, ['Tick', 'Level'])
    li = lvl_index(d, level)
    on, off = d.idx(table(d, LV_ON, 'Floor on'), li), d.idx(table(d, LV_OFF, 'Floor off'), li)
    t = d.qr(d.i32(tick), d.add2(on, off))[0]
    phase = d.sel(d.lt(t, d.sub(on, c(LV_WARN))), c(0), d.sel(d.lt(t, on), c(1), c(2)))
    pm = d.call('Player_Move.vi', [('State', d.bun(st, [('FloorPhase', phase)])), ('Jump', jump), ('error in', e)], ['State out', 'error out'])
    mode, vy, snd = d.unb(pm['State out'], ['Mode', 'VY10', 'Sound'])
    jumped = allb(d, jump, d.eq(mode, c(2)), d.eq(vy, c(JUMP10)))
    # Rutschgeraeusch: beim Aufspringen auf die Stange und dann alle SLIDE_EVERY Ticks, solange Claude rutscht
    mode0, = d.unb(st, ['Mode'])
    sliding = d.and_(d.eq(mode, c(3)), d.or_(d.ne(mode0, c(3)), d.eq(d.qr(d.i32(tick), c(SLIDE_EVERY))[0], c(0))))
    s1 = d.bun(pm['State out'], [('Sound', d.or_(d.or_(snd, d.sel(jumped, c(SND['jump']), c(0))), d.sel(sliding, c(SND['slide']), c(0))))])
    ic = d.call('Items_Collect.vi', [('State', s1), ('error in', pm['error out'])], ['State out', 'error out'])
    do = d.call('Door_Open.vi', [('State', ic['State out']), ('error in', ic['error out'])], ['State out', '-Opened', 'error out'])
    es = d.call('Enemies_Step.vi', [('State', do['State out']), ('error in', do['error out'])], ['State out', 'error out'])
    hc = d.call('Hit_Check.vi', [('State', es['State out']), ('error in', es['error out'])], ['Hit', 'error out'])
    rc = d.call('Room_Change.vi', [('State', es['State out']), ('error in', hc['error out'])], ['State out', '-Changed', 'error out'])
    score, nxt, lives, snd2, dead = d.unb(rc['State out'], ['Score', 'NextLife', 'Lives', 'Sound', 'Dead'])
    extra = ge(d, score, nxt)
    out = d.bun(rc['State out'], [('NextLife', d.sel(extra, d.add2(nxt, c(EXTRA_LIFE)), nxt)),
                                  ('Lives', d.sel(extra, minv(d, d.inc(lives), c(MAX_LIVES)), lives)),
                                  ('Sound', d.or_(snd2, d.sel(extra, c(SND['life']), c(0))))])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.indic('Hit', 'bool', 'false', hc['Hit'], 6)
    d.indic('Died', 'bool', 'false', dead, 8)
    d.err_out(rc['error out'])
    d.write()


# Demo: Tastenfolge im Startraum (mit sim_player.py abgestimmt)
# Demo-Tastenfolge fuer WALK10 = 30 / BELT10 = 20 (umgerechnet mit retime_demo.py, gleicher Weg, Pausen fuer die Schwundboeden)
DEMO_EVENTS = [(0, 'Right'), (236, 'ReleaseR'), (237, 'Down'), (301, 'ReleaseV'), (363, 'Left'), (615, 'ReleaseL'), (639, 'Right'),
               (825, 'ReleaseR'), (826, 'Down'), (890, 'ReleaseV'), (891, 'Right'), (983, 'ReleaseR'), (984, 'Left'), (1120, 'ReleaseL'),
               (1121, 'Down')]


def demo_input():
    d = Doc('Demo_Input.vi', 'Key of the demo for one demo tick (Step). Outside the listed steps: no key (0).')
    step = d.ctrl('Step', 'int32', '0', 0)
    e = d.err_in()
    steps = table(d, [t for t, _ in DEMO_EVENTS], 'Demo steps')
    keys = d.const(f'array{{{KEY}}}', '[' + ','.join(str(IN[k]) for _, k in DEMO_EVENTS) + ']', 'Demo keys')
    ix = d.node('Search 1D Array', [('1D array', steps), ('element', step), ('start index (0)', '')], ['index of element'])['index of element']
    d.indic('Key', KEY, '0', d.idx(keys, ix), 4)
    d.err_out(e)
    d.write()


def highscore_load():
    d = Doc('Highscore_Load.vi', 'Reads the highscore list from Resources\\Data\\highscores.txt (one line per entry: Score;Name). Without '
            'the file or with an empty file the default list comes back and no error.')
    e = d.err_in()
    r = d.call('Resource_Path.vi', [('File name', d.const('string', 'highscores.txt')), ('Subfolder', d.const('string', 'Data')),
                                    ('error in', e)], ['Path', 'error out'])
    rows, err = read_lines(d, r['Path'], r['error out'], ';')
    d.begin('For Loop', 'count="" maxin="" maxout=""')
    row = d.tunnel_in(1, rows, 'index')
    num = d.node('Decimal String To Number', [('string', d.idx(row, d.i32c(0))), ('offset', ''), ('default (0L)', d.i32c(0))],
                 ['-offset past number', 'number'])['number']
    hs = d.bun(d.const(HS, '[0,]'), [('Score', num), ('Name', d.idx(row, d.i32c(1)))])
    tab = d.tunnel_out(1, hs, 'index')
    d.end()
    st, = d.unb(err, ['status'])
    bad = d.or_(st, d.eq(size(d, tab), d.i32c(0)))
    d.indic('Table', HSTAB, '[]', d.sel(bad, d.const(HSTAB, HS_DEFAULT, 'Default list'), tab), 4)
    d.err_out(d.sel(st, d.const(ERR, ERR_V), err))
    d.write()


def highscore_save():
    d = Doc('Highscore_Save.vi', 'Writes the highscore list to Resources\\Data\\highscores.txt (Score;Name per line).')
    tab = d.ctrl('Table', HSTAB, '[]', 0)
    e = d.err_in()
    semi, nl, empty = d.const('string', ';'), d.const('string', '\\0D\\0A'), d.const('string', '')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    hs = d.tunnel_in(1, tab, 'index')
    a, b = d.tunnel_in(2, semi), d.tunnel_in(3, nl)
    t_l, t_r = shiftreg(d, lp, empty)
    sc, name = d.unb(hs, ['Score', 'Name'])
    num = d.node('Number To Decimal String', [('number', sc), ('width (-)', '')], ['decimal integer string'])['decimal integer string']
    line = d.node('Concatenate Strings', [('string', t_l), ('string', num), ('string', a), ('string', name), ('string', b)],
                  ['concatenated string'])['concatenated string']
    d.end()
    text = close_reg(d, t_r, line)
    r = d.call('Resource_Path.vi', [('File name', d.const('string', 'highscores.txt')), ('Subfolder', d.const('string', 'Data')),
                                    ('error in', e)], ['Path', 'error out'])
    w = d.node('Write to Text File', [('file (use dialog)', r['Path']), ('text', text), ('error in', r['error out']),
                                      ('prompt (Choose or enter file path)', '')], ['-refnum out', '-cancelled', 'error out'])
    d.err_out(w['error out'])
    d.write()


def highscore_insert():
    d = Doc('Highscore_Insert.vi', f'Inserts Score and Name into the list, sorts it (best first) and keeps the best {HS_MAX}.')
    tab = d.ctrl('Table', HSTAB, '[]', 0)
    sc = d.ctrl('Score', 'int32', '0', 5)
    name = d.ctrl('Name', 'string', '', 7)
    e = d.err_in()
    new = d.bun(d.const(HS, '[0,]'), [('Score', sc), ('Name', name)])
    allx = d.node('Build Array', [('array', tab), ('element', new)], ['appended array'], extra='concat="true"')['appended array']
    srt = d.node('Sort 1D Array', [('array', allx)], ['sorted array'])['sorted array']
    rev = d.node('Reverse 1D Array', [('array', srt)], ['reversed array'])['reversed array']
    top = d.node('Array Subset', [('array', rev), ('index', d.i32c(0)), ('length', d.i32c(HS_MAX))], ['subarray'])['subarray']
    d.indic('Table out', HSTAB, '[]', top, 4)
    d.err_out(e)
    d.write()


def name_text(d, letters):
    """Buchstaben-Indizes (0..26) -> Text"""
    alpha, empty = d.const('string', ALPHA), d.const('string', '')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    l = d.tunnel_in(1, letters, 'index')
    al = d.tunnel_in(2, alpha)
    s_l, s_r = shiftreg(d, lp, empty)
    ch = d.node('String Subset', [('string', al), ('offset (0)', l), ('length (rest)', d.i32c(1))], ['substring'])['substring']
    s2 = d.node('Concatenate Strings', [('string', s_l), ('string', ch)], ['concatenated string'])['concatenated string']
    d.end()
    return close_reg(d, s_r, s2)


def game_start():
    d = Doc('Game_Start.vi', 'Loads the whole world (World_Load) and the highscores and returns the first state (title screen) and the '
            'rooms as they are in the files (for every new level).')
    e = d.err_in()
    wl = d.call('World_Load.vi', [('error in', e)], ['Rooms', '-Grid', 'error out'])
    hl = d.call('Highscore_Load.vi', [('error in', wl['error out'])], ['Table', 'error out'])
    s0 = d.bun(d.const(STATE, STATE_V), [('Highscores', hl['Table']), ('Name', d.const('array{int32}', NAME_START))])
    ls = d.call('Level_Setup.vi', [('State', s0), ('Rooms', wl['Rooms']), ('Level', d.i32c(1)), ('error in', hl['error out'])],
                ['State out', 'error out'])
    st = d.bun(ls['State out'], [('Phase', d.i32c(PH['Title'])), ('PhaseTicks', d.i32c(0))])
    d.indic('State', STATE, STATE_V, st, 4)
    d.indic('Rooms', ROOMS, '[]', wl['Rooms'], 6)
    d.err_out(ls['error out'])
    d.write()


def game_step():
    d = Doc('Game_Step.vi', 'One game tick, a state machine over the phases ' + ', '.join(PHASES) + '. Title: card, then the highscore '
            'table, then the demo; Enter starts, Esc quits. Ready: short pause with a message. Playing: Game_Play; a hit or a deadly fall '
            'starts Dying, the treasure room starts Treasure. Paused: Esc/P or Enter continues. Dying: one life less, then Ready at the '
            'arrival point or GameOver. Treasure: playing against the clock, then LevelDone and the next level. GameOver: then Name '
            'entry (arrows choose letters, Enter saves) when the score is good enough, else Title. Sound bits for the audio loop; music '
            'during ' + ', '.join(MUSIC_PHASES) + '. Keys: ' + ', '.join(f'{i} {k}' for i, k in enumerate(KEYS)) + '.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    key = d.ctrl('Key', KEY, '0', 5, 'recommended')
    rooms = d.ctrl('Rooms', ROOMS, '[]', 7)
    e = d.err_in()
    c = d.i32c
    k = d.i32(key)
    tick, quit_, phase = d.unb(st, ['Tick', 'Quit'] + ['Phase'])
    st1 = d.bun(st, [('Tick', d.inc(tick)), ('Sound', c(0)), ('Quit', d.or_(quit_, d.eq(k, c(IN['Quit']))))])

    def to(s, ph, sound=0, extra=()):
        pairs = [('Phase', c(PH[ph])), ('PhaseTicks', c(0))] + list(extra)
        if sound:
            snd, = d.unb(s, ['Sound'])
            pairs.append(('Sound', d.or_(snd, c(sound))))
        return d.bun(s, pairs)

    def ticks(s):
        pt, = d.unb(s, ['PhaseTicks'])
        return d.inc(pt)

    def f_title(i):
        s, kk, rm, err = i
        pt = ticks(s)
        start = d.eq(kk, c(IN['Start']))
        demo_go = ge(d, pt, c(TITLE_CARD + TITLE_SCORES))
        gn = d.call('Game_New.vi', [('State', s), ('Rooms', rm), ('Demo', d.not_(start)), ('error in', err)], ['State out', 'error out'])
        q, = d.unb(s, ['Quit'])
        idle = d.bun(s, [('PhaseTicks', pt), ('Quit', d.or_(q, d.eq(kk, c(IN['Pause']))))])
        return [d.sel(d.or_(start, demo_go), gn['State out'], idle), gn['error out']]

    def f_demo(i):
        s, kk, rm, err = i
        start = d.eq(kk, c(IN['Start']))
        gn = d.call('Game_New.vi', [('State', s), ('Rooms', rm), ('Demo', d.const('bool', 'false')), ('error in', err)], ['State out', 'error out'])
        step, = d.unb(s, ['DemoStep'])
        di = d.call('Demo_Input.vi', [('Step', step), ('error in', gn['error out'])], ['Key', 'error out'])
        ka = d.call('Keys_Apply.vi', [('State', s), ('Key', di['Key']), ('error in', di['error out'])], ['State out', 'error out'])
        gp = d.call('Game_Play.vi', [('State', ka['State out']), ('Jump', d.eq(d.i32(di['Key']), c(IN['Jump']))), ('error in', ka['error out'])],
                    ['State out', 'Hit', 'Died', 'error out'])
        room, = d.unb(gp['State out'], ['Room'])
        played = d.bun(gp['State out'], [('DemoStep', d.inc(step)), ('Sound', c(0))])
        over = anyb(d, gp['Hit'], gp['Died'], ge(d, step, c(DEMO_LEN)), d.ne(room, c(START_IDX)))
        back = d.bun(s, [('Phase', c(PH['Title'])), ('PhaseTicks', c(0)), ('Sound', c(0))])
        return [d.sel(start, gn['State out'], d.sel(over, back, played)), gp['error out']]

    def f_ready(i):
        s, kk, rm, err = i
        ka = d.call('Keys_Apply.vi', [('State', s), ('Key', u16(kk)), ('error in', err)], ['State out', 'error out'])
        pt = ticks(s)
        go = ge(d, pt, c(READY_TICKS))
        # Levelbeginn: Claude klettert am Seil von oben herunter und steht am Ende der Phase auf der oberen Plattform
        intro, ex10, ey10, x10, y10, md = d.unb(ka['State out'], ['LevelStart', 'EntryX10', 'EntryY10', 'X10', 'Y10', 'Mode'])
        yint = maxv(d, d.sub(ey10, d.mul(d.sub(c(READY_TICKS), pt), c(CLIMB10))), c(0))
        wait = d.bun(ka['State out'], [('PhaseTicks', pt), ('X10', d.sel(intro, ex10, x10)), ('Y10', d.sel(intro, yint, y10)),
                                       ('Mode', d.sel(intro, d.sel(d.lt(yint, ey10), c(1), c(0)), md)), ('VY10', c(0))])
        landed = d.bun(ka['State out'], [('X10', d.sel(intro, ex10, x10)), ('Y10', d.sel(intro, ey10, y10)), ('Mode', d.sel(intro, c(0), md)),
                                         ('StandY', d.sel(intro, d.qr(ey10, c(10))[1], d.unb(ka['State out'], ['StandY'])[0]))])
        play = to(landed, 'Playing', extra=[('LevelStart', d.const('bool', 'false'))])
        return [d.sel(go, play, wait), ka['error out']]

    def u16(v): return d.node('To Unsigned Word Integer', [('number', v)], ['unsigned 16bit integer'])['unsigned 16bit integer']

    def f_playing(i):
        s, kk, rm, err = i
        pause = d.eq(kk, c(IN['Pause']))
        ka = d.call('Keys_Apply.vi', [('State', s), ('Key', u16(kk)), ('error in', err)], ['State out', 'error out'])
        gp = d.call('Game_Play.vi', [('State', ka['State out']), ('Jump', d.eq(kk, c(IN['Jump']))), ('error in', ka['error out'])],
                    ['State out', 'Hit', 'Died', 'error out'])
        room, = d.unb(gp['State out'], ['Room'])
        dying = to(gp['State out'], 'Dying', SND['death'], [('Run', c(0)), ('Vert', c(0))])
        treasure = to(gp['State out'], 'Treasure', SND['treasure'])
        nxt = d.sel(d.or_(gp['Hit'], gp['Died']), dying, d.sel(d.eq(room, c(TREASURE_IDX)), treasure, gp['State out']))
        return [d.sel(pause, to(s, 'Paused'), nxt), gp['error out']]

    def f_paused(i):
        s, kk, rm, err = i
        go = d.or_(d.eq(kk, c(IN['Pause'])), d.eq(kk, c(IN['Start'])))
        return [d.sel(go, to(s, 'Playing'), s), err]

    def f_dying(i):
        s, kk, rm, err = i
        pt = ticks(s)
        lives, = d.unb(s, ['Lives'])
        rs = d.call('Respawn.vi', [('State', d.bun(s, [('Lives', d.sub(lives, c(1)))])), ('error in', err)], ['State out', 'error out'])
        done = ge(d, pt, c(DYING_TICKS))
        over = le(d, lives, c(1))
        gameover = to(d.bun(s, [('Lives', c(0))]), 'GameOver', SND['gameover'])
        again = to(rs['State out'], 'Ready', SND['ready'])
        return [d.sel(done, d.sel(over, gameover, again), d.bun(s, [('PhaseTicks', pt)])), rs['error out']]

    def f_treasure(i):
        s, kk, rm, err = i
        ka = d.call('Keys_Apply.vi', [('State', s), ('Key', u16(kk)), ('error in', err)], ['State out', 'error out'])
        gp = d.call('Game_Play.vi', [('State', ka['State out']), ('Jump', d.eq(kk, c(IN['Jump']))), ('error in', ka['error out'])],
                    ['State out', '-Hit', '-Died', 'error out'])
        pt = ticks(s)
        level, = d.unb(s, ['Level'])
        limit = d.idx(table(d, LV_TREASURE, 'Treasure time'), lvl_index(d, level))
        played = d.bun(gp['State out'], [('PhaseTicks', pt), ('Dead', d.const('bool', 'false'))])
        done = to(played, 'LevelDone', SND['level'], [('Run', c(0)), ('Vert', c(0))])
        return [d.sel(ge(d, pt, limit), done, played), gp['error out']]

    def f_leveldone(i):
        s, kk, rm, err = i
        pt = ticks(s)
        level, snd = d.unb(s, ['Level', 'Sound'])
        ls = d.call('Level_Setup.vi', [('State', s), ('Rooms', rm), ('Level', d.inc(level)), ('error in', err)], ['State out', 'error out'])
        nxt = d.bun(ls['State out'], [('Sound', d.or_(snd, c(SND['level'])))])
        return [d.sel(ge(d, pt, c(LEVELDONE_TICKS)), nxt, d.bun(s, [('PhaseTicks', pt)])), ls['error out']]

    def f_gameover(i):
        s, kk, rm, err = i
        pt = ticks(s)
        score, tab = d.unb(s, ['Score', 'Highscores'])
        last, = d.unb(d.idx(tab, c(HS_MAX - 1)), ['Score'])
        good = d.or_(d.gt(score, last), d.lt(size(d, tab), c(HS_MAX)))
        name = to(s, 'Name', extra=[('Name', d.const('array{int32}', NAME_START)), ('Cursor', c(0))])
        title = to(s, 'Title')
        return [d.sel(ge(d, pt, c(GAMEOVER_TICKS)), d.sel(good, name, title), d.bun(s, [('PhaseTicks', pt)])), err]

    def f_name(i):
        s, kk, rm, err = i
        letters, cur, score, tab = d.unb(s, ['Name', 'Cursor', 'Score', 'Highscores'])
        is_ = lambda n: d.eq(kk, c(IN[n]))
        letter = d.idx(letters, cur)
        up = d.qr(d.add2(letter, c(1)), c(len(ALPHA)))[0]
        dn = d.qr(d.add2(letter, c(len(ALPHA) - 1)), c(len(ALPHA)))[0]
        letter2 = d.sel(is_('Up'), up, d.sel(is_('Down'), dn, letter))
        letters2 = d.node('Replace Array Subset', [('array', letters), ('new element/subarray', letter2), ('index', cur)], ['output array'])['output array']
        cur2 = clampv(d, d.add2(cur, d.sel(is_('Right'), c(1), d.sel(is_('Left'), c(-1), c(0)))), c(0), c(NAME_LEN - 1))
        edited = d.bun(s, [('Name', letters2), ('Cursor', cur2)])
        text = name_text(d, letters)
        hi = d.call('Highscore_Insert.vi', [('Table', tab), ('Score', score), ('Name', text), ('error in', err)], ['Table out', 'error out'])
        done = is_('Start')
        # gespeichert wird nur beim Bestaetigen (Case, damit die Datei nicht jeden Tick geschrieben wird)
        err2, = d.case(done, [hi['Table out'], hi['error out']], [
            # ein Fehler beim Speichern darf das Spiel nicht anhalten (die Liste bleibt im Speicher)
            ('True', lambda j: [(d.call('Highscore_Save.vi', [('Table', j[0]), ('error in', j[1])], ['-error out']), j[1])[1]]),
            ('False', lambda j: [j[1]]),
        ], 1)
        saved = to(d.bun(s, [('Highscores', hi['Table out'])]), 'Title')
        return [d.sel(done, saved, edited), err2]

    frames = [(str(PH['Title']), f_title), (str(PH['Ready']), f_ready), (str(PH['Playing']), f_playing), (str(PH['Paused']), f_paused),
              (str(PH['Dying']), f_dying), (str(PH['Treasure']), f_treasure), (str(PH['LevelDone']), f_leveldone),
              (str(PH['GameOver']), f_gameover), (str(PH['Name']), f_name), ('Default', f_demo)]
    out, err = d.case(phase, [st1, k, rooms, e], frames, 2)
    ph2, snd2 = d.unb(out, ['Phase', 'Sound'])
    music = anyb(d, *[d.eq(ph2, c(PH[p])) for p in MUSIC_PHASES])
    out2 = d.bun(out, [('Sound', d.or_(snd2, d.sel(music, c(SND['music']), c(0))))])
    d.indic('State out', STATE, STATE_V, out2, 4)
    d.err_out(err)
    d.write()


# ================================================================== Render
def room_images():
    d = Doc('Room_Images.vi', f'Loads the three pictures of a room for a colour theme (room_<Theme>_<ID>.png, _dim, _dark) as rasters of '
            f'{FIELD_H} rows x {W * 3} bytes (24 bit). Template = image data of the lit picture without pixels (type, depth, colours).')
    rid = d.ctrl('Room ID', 'string', '005', 0)
    theme = d.ctrl('Theme', 'int32', '0', 5)
    e = d.err_in()
    num = d.node('Number To Decimal String', [('number', theme), ('width (-)', '')], ['decimal integer string'])['decimal integer string']
    outs, err = [], e
    for suffix in ('', '_dim', '_dark'):
        name = d.node('Concatenate Strings', [('string', d.const('string', 'room_')), ('string', num), ('string', d.const('string', '_')),
                                              ('string', rid), ('string', d.const('string', suffix + '.png'))], ['concatenated string'])['concatenated string']
        il = d.call('Image_Load.vi', [('File name', name), ('error in', err)], ['Image', 'error out'])
        err = il['error out']
        data, = d.unb(il['Image'], ['image'])
        grid = d.node('Reshape Array', [('array', data), ('dimension size', d.i32c(FIELD_H)), ('dimension size', d.i32c(W * 3))],
                      ['output array'])['output array']
        outs.append((grid, il['Image']))
    template = d.bun(outs[0][1], [('image', d.const('array{uint8}', '[]'))])
    d.indic('Lit', GRID, '[]', outs[0][0], 4)
    d.indic('Dim', GRID, '[]', outs[1][0], 6)
    d.indic('Dark', GRID, '[]', outs[2][0], 8)
    d.indic('Template', IMG, IMG_V, template, 10)
    d.err_out(err)
    d.write()


def light_update():
    d = Doc('Light_Update.vi', f'Updates the composite picture of a dark room around Claude: every tile within {LIGHT_R} tiles of the old '
            f'and the new centre comes from the lit (distance^2 <= {LIGHT_IN}), dim (<= {LIGHT_OUT}) or dark picture. Old centre < -50 = '
            'only the new centre. Rect = the renewed tiles (left, top, right, bottom; right/bottom exclusive).')
    comp = d.ctrl('Comp', GRID, '[]', 0)
    lit = d.ctrl('Lit', GRID, '[]', 5)
    dim = d.ctrl('Dim', GRID, '[]', 7)
    dark = d.ctrl('Dark', GRID, '[]', 9)
    ocx = d.ctrl('Old CX', 'int32', '-100', 1)
    ocy = d.ctrl('Old CY', 'int32', '-100', 2)
    cx = d.ctrl('CX', 'int32', '0', 3)
    cy = d.ctrl('CY', 'int32', '0', 13)
    e = d.err_in()
    c = d.i32c
    none = d.lt(ocx, c(-50))
    ox, oy = d.sel(none, cx, ocx), d.sel(none, cy, ocy)
    left = maxv(d, d.sub(minv(d, ox, cx), c(LIGHT_R)), c(0))
    top = maxv(d, d.sub(minv(d, oy, cy), c(LIGHT_R)), c(0))
    right = minv(d, d.add2(maxv(d, ox, cx), c(LIGHT_R + 1)), c(COLS))
    bottom = minv(d, d.add2(maxv(d, oy, cy), c(LIGHT_R + 1)), c(ROWS))
    nrows, ncols = maxv(d, d.sub(bottom, top), c(0)), maxv(d, d.sub(right, left), c(0))
    cn = counter(d, nrows)
    outer = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    ri = f'{outer}i.v'
    d.tunnel_in(1, cn, 'index')
    a = [d.tunnel_in(k + 2, v) for k, v in enumerate((lit, dim, dark, top, left, cx, cy, ncols))]
    g_l, g_r = shiftreg(d, outer, comp)
    r = d.add2(a[3], ri)
    cn2 = counter(d, a[7])
    inner = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    ci = f'{inner}i.v'
    d.tunnel_in(1, cn2, 'index')
    b = [d.tunnel_in(k + 2, v) for k, v in enumerate((a[0], a[1], a[2], r, a[4], a[5], a[6]))]
    h_l, h_r = shiftreg(d, inner, g_l)
    col = d.add2(b[4], ci)
    dxx, dyy = d.sub(col, b[5]), d.sub(b[3], b[6])
    dist = d.add2(d.mul(dxx, dxx), d.mul(dyy, dyy))
    src = d.sel(le(d, dist, c(LIGHT_IN)), c(0), d.sel(le(d, dist, c(LIGHT_OUT)), c(1), c(2)))
    row0, col0 = d.mul(b[3], c(TILE)), d.mul(col, c(TILE * 3))

    def cut(grid):
        return lambda j: [d.node('Array Subset', [('array', j[grid]), ('index', j[3]), ('length', d.i32c(TILE)), ('index', j[4]),
                                                  ('length', d.i32c(TILE * 3))], ['subarray'], extra='dimensions="2"')['subarray']]

    piece, = d.case(src, [b[0], b[1], b[2], row0, col0], [('0', cut(0)), ('1', cut(1)), ('Default', cut(2))], 1)
    h2 = d.node('Replace Array Subset', [('array', h_l), ('new element/subarray', piece), ('index (row)', row0), ('index (col)', col0)],
                ['output array'], extra='dimensions="2"')['output array']
    d.end()
    g2 = close_reg(d, h_r, h2)
    d.end()
    rect = d.bun(d.const(RECT, '[0,0,0,0]'), [('left', w16(d, left)), ('top', w16(d, top)), ('right', w16(d, right)), ('bottom', w16(d, bottom))])
    d.indic('Comp out', GRID, '[]', close_reg(d, g_r, g2), 4)
    d.indic('Rect', RECT, '[0,0,0,0]', rect, 6)
    d.err_out(e)
    d.write()


def grid_block():
    d = Doc('Grid_Block.vi', f'Cuts the tiles Rect (left, top, right, bottom in tiles, right/bottom exclusive, limited to the room) out of a '
            f'room raster and returns them as image data placed on the screen (playfield {HUD_H} px below the top).')
    grid = d.ctrl('Grid', GRID, '[]', 0)
    tmpl = d.ctrl('Template', IMG, IMG_V, 5)
    rect = d.ctrl('Rect', RECT, '[0,0,0,0]', 7)
    e = d.err_in()
    c = d.i32c
    l, t, r, b = (d.i32(v) for v in d.unb(rect, ['left', 'top', 'right', 'bottom']))
    l2, t2 = clampv(d, l, c(0), c(COLS - 1)), clampv(d, t, c(0), c(ROWS - 1))
    r2, b2 = clampv(d, r, d.inc(l2), c(COLS)), clampv(d, b, d.inc(t2), c(ROWS))
    h, w = d.mul(d.sub(b2, t2), c(TILE)), d.mul(d.sub(r2, l2), c(TILE * 3))
    sub = d.node('Array Subset', [('array', grid), ('index', d.mul(t2, c(TILE))), ('length', h), ('index', d.mul(l2, c(TILE * 3))), ('length', w)],
                 ['subarray'], extra='dimensions="2"')['subarray']
    flat = d.node('Reshape Array', [('array', sub), ('dimension size', d.mul(h, w))], ['output array'])['output array']
    rc = d.bun(d.const(RECT, '[0,0,0,0]'), [('left', w16(d, d.mul(l2, c(TILE)))), ('top', w16(d, d.add2(d.mul(t2, c(TILE)), c(HUD_H)))),
                                            ('right', w16(d, d.mul(r2, c(TILE)))), ('bottom', w16(d, d.add2(d.mul(b2, c(TILE)), c(HUD_H))))])
    d.indic('Block', IMG, IMG_V, d.bun(tmpl, [('image', flat), ('Rectangle', rc)]), 4)
    d.err_out(e)
    d.write()


def room_draw():
    d = Doc('Room_Draw.vi', 'Draws the objects of a room inside Region (tiles; two rows more upwards for the doors): vanishing floors '
            '(FloorPhase 0 normal, 1 warning, 2 gone), conveyors, doors (only at their top tile), keys, gold and the torch. Hide = dark '
            f'room: only objects within the light (distance^2 <= {LIGHT_OUT} tiles from CX, CY) are drawn.')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    tiles = d.ctrl('Tiles', TILES, '[]', 7)
    region = d.ctrl('Region', RECT, '[0,0,40,20]', 9)
    fphase = d.ctrl('FloorPhase', 'int32', '0', 1)
    view = d.ctrl('View', VIEW, VIEW_V, 2)
    e = d.err_in()
    c = d.i32c
    n = max(TILE_CODE.values()) + 1
    sprite_of = d.const('array{int32}', lut({k: SPR[v] for k, v in ROOM_SPRITE.items()}, n), 'Sprite per tile value')
    top_of = d.const('array{int32}', lut({k: 1 for k in TOP_ALIGNED}, n), 'Top aligned')
    l, t, r, b = (d.i32(v) for v in d.unb(region, ['left', 'top', 'right', 'bottom']))
    t0 = maxv(d, d.sub(t, c(2)), c(0))
    l0 = maxv(d, l, c(0))
    nrows = maxv(d, d.sub(minv(d, b, c(ROWS)), t0), c(0))
    ncols = maxv(d, d.sub(minv(d, r, c(COLS)), l0), c(0))
    hide, vcx, vcy = d.unb(view, ['Hide', 'CX', 'CY'])
    floor_spr = d.sel(d.eq(fphase, c(1)), c(SPR['floor_1']), d.sel(d.eq(fphase, c(2)), c(-1), c(SPR['floor_0'])))
    sprite_of2 = d.node('Replace Array Subset', [('array', sprite_of), ('new element/subarray', floor_spr), ('index', c(T['~']))], ['output array'])['output array']
    cn = counter(d, nrows)
    outer = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    ri = f'{outer}i.v'
    d.tunnel_in(1, cn, 'index')
    a = [d.tunnel_in(k + 2, v) for k, v in enumerate((tiles, spr, sprite_of2, top_of, t0, l0, ncols, hide, vcx, vcy))]
    p_l, p_r = shiftreg(d, outer, pic)
    e_l, e_r = shiftreg(d, outer, e)
    row = d.add2(a[4], ri)
    cn2 = counter(d, a[6])
    inner = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    ci = f'{inner}i.v'
    d.tunnel_in(1, cn2, 'index')
    bb = [d.tunnel_in(k + 2, v) for k, v in enumerate((a[0], a[1], a[2], a[3], row, a[5], a[7], a[8], a[9]))]
    p2_l, p2_r = shiftreg(d, inner, p_l)
    e2_l, e2_r = shiftreg(d, inner, e_l)
    col = d.add2(bb[5], ci)
    code8 = get_tile(d, bb[0], bb[4], col)
    code = d.i32(code8)
    six = d.idx(bb[2], code)
    above = get_tile(d, bb[0], maxv(d, d.node('Decrement', [('x', bb[4])], ['x-1'])['x-1'], c(0)), col)
    is_door = d.and_(ge(d, code, c(T['R'])), le(d, code, c(T['Y'])))
    lower_door = allb(d, is_door, d.eq(above, code8), d.gt(bb[4], c(0)))
    dxx, dyy = d.sub(col, bb[7]), d.sub(bb[4], bb[8])
    hidden = d.and_(bb[6], d.gt(d.add2(d.mul(dxx, dxx), d.mul(dyy, dyy)), c(LIGHT_OUT)))
    show = allb(d, ge(d, six, c(0)), d.not_(lower_door), d.not_(hidden))

    def draw(i):
        picture, sprites, index, err, rr, cc, top = i
        if BLIT:                        # Blit-Sprites: Hoehe = Zeilen der Pixel
            (pixa,) = d.unb(d.idx(sprites, index), ['Pix'])
            h = d.i32(d.idx(d.node('Array Size', [('array', pixa)], ['size(s)'])['size(s)'], c(0)))
        else:
            (rect,) = d.unb(d.idx(sprites, index), ['Rectangle'])
            tt, bt = d.unb(rect, ['top', 'bottom'])
            h = d.i32(d.sub(bt, tt))
        y0 = d.add2(d.mul(rr, c(TILE)), c(HUD_H))
        y = d.sel(d.eq(top, c(1)), y0, d.sub(d.add2(y0, c(TILE)), h))
        pos = d.bun(d.const(POS, '[0,0]'), [('X', d.mul(cc, c(TILE))), ('Y', y)])
        res = d.call('Sprite_Draw.vi', [('Picture', picture), ('Sprites', sprites), ('Index', index), ('Position', pos), ('error in', err)],
                     ['Picture out', 'error out'])
        return [res['Picture out'], res['error out']]

    pic2, err2 = d.case(show, [p2_l, bb[1], six, e2_l, bb[4], col, d.idx(bb[3], code)], [('True', draw), ('False', lambda i: [i[0], i[3]])], 2)
    d.end()
    pic_row, err_row = close_reg(d, p2_r, pic2), close_reg(d, e2_r, err2)
    d.end()
    d.indic('Picture out', 'picture', '', close_reg(d, p_r, pic_row), 4)
    d.err_out(close_reg(d, e_r, err_row))
    d.write()


def enemies_draw():
    d = Doc('Enemies_Draw.vi', 'Draws all enemies: spider (legs move every 8 ticks), snake (head sways), skull (turns while rolling). Hide = '
            f'dark room: only enemies within the light (distance^2 <= {LIGHT_OUT} tiles).')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    enemies = d.ctrl('Enemies', ENEMIES, '[]', 7)
    tick = d.ctrl('Tick', 'uint32', '0', 9)
    view = d.ctrl('View', VIEW, VIEW_V, 1)
    e = d.err_in()
    c = d.i32c
    hide, vcx, vcy = d.unb(view, ['Hide', 'CX', 'CY'])
    t = d.i32(tick)
    f_spider = d.add2(c(SPR['spider_0']), d.qr(d.qr(t, c(8))[1], c(2))[0])
    f_snake = d.add2(c(SPR['snake_0']), d.idx(table(d, [0, 1, 2, 1], 'Snake frames'), d.qr(d.qr(t, c(12))[1], c(4))[0]))
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    en = d.tunnel_in(1, enemies, 'index')
    a = [d.tunnel_in(k + 2, v) for k, v in enumerate((spr, hide, vcx, vcy, f_spider, f_snake))]
    p_l, p_r = shiftreg(d, lp, pic)
    e_l, e_r = shiftreg(d, lp, e)
    kind, x10, y10 = d.unb(en, ['Kind', 'X10', 'Y10'])
    x, y = px(d, x10), px(d, y10)
    f_skull = d.add2(c(SPR['skull_0']), d.qr(d.qr(x, c(8))[1], c(4))[0])
    index = d.sel(d.eq(kind, c(0)), a[4], d.sel(d.eq(kind, c(1)), a[5], f_skull))
    dxx = d.sub(d.qr(d.add2(x, c(16)), c(TILE))[1], a[2])
    dyy = d.sub(d.qr(d.add2(y, c(16)), c(TILE))[1], a[3])
    hidden = d.and_(a[1], d.gt(d.add2(d.mul(dxx, dxx), d.mul(dyy, dyy)), c(LIGHT_OUT)))
    pos = d.bun(d.const(POS, '[0,0]'), [('X', x), ('Y', d.sel(hidden, c(-2000), d.add2(y, c(HUD_H))))])
    r = d.call('Sprite_Draw.vi', [('Picture', p_l), ('Sprites', a[0]), ('Index', index), ('Position', pos), ('error in', e_l)],
               ['Picture out', 'error out'])
    d.end()
    d.indic('Picture out', 'picture', '', close_reg(d, p_r, r['Picture out']), 4)
    d.err_out(close_reg(d, e_r, r['error out']))
    d.write()


def glyphs_draw():
    d = Doc('Glyphs_Draw.vi', f'Writes Text with the glyph sprites (characters "{CHARSET}", {GLYPH_W} px apart) from Position (top left). '
            'Unknown characters and spaces stay empty.')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    text = d.ctrl('Text', 'string', '', 7)
    pos = d.ctrl('Position', POS, '[0,0]', 9)
    e = d.err_in()
    c = d.i32c
    x0, y0 = d.unb(pos, ['X', 'Y'])
    glyph = {ord(ch): SPR['glyph_%02d' % k] for k, ch in enumerate(CHARSET) if ch != ' '}
    tbl = d.const('array{int32}', lut(glyph, 256), 'Sprite per character')
    bytes_ = d.node('String To Byte Array', [('string', text)], ['unsigned byte array'])['unsigned byte array']
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    bt = d.tunnel_in(1, bytes_, 'index')
    a = [d.tunnel_in(k + 2, v) for k, v in enumerate((tbl, spr, x0, y0))]
    p_l, p_r = shiftreg(d, lp, pic)
    e_l, e_r = shiftreg(d, lp, e)
    ix = d.idx(a[0], d.i32(bt))
    ok = ge(d, ix, c(0))
    gpos = d.bun(d.const(POS, '[0,0]'), [('X', d.add2(a[2], d.mul(i, c(GLYPH_W)))), ('Y', d.sel(ok, a[3], c(-2000)))])
    r = d.call('Sprite_Draw.vi', [('Picture', p_l), ('Sprites', a[1]), ('Index', maxv(d, ix, c(0))), ('Position', gpos), ('error in', e_l)],
               ['Picture out', 'error out'])
    d.end()
    d.indic('Picture out', 'picture', '', close_reg(d, p_r, r['Picture out']), 4)
    d.err_out(close_reg(d, e_r, r['error out']))
    d.write()


def fmt(d, f, *vals):
    ins = [('format string', d.const('string', f)), ('initial string', ''), ('error in', '')]
    ins += [(f'input {k + 1}', v) for k, v in enumerate(vals)]
    return d.node('Format Into String', ins, ['resulting string', '-error out'])['resulting string']


def hud_ops(d, pic, spr, st, e):
    """Zeichenbefehle des HUD (Leben, Schluessel, Fackel, Level, Gold, Zeit) auf pic; das HUD-Bild selbst zeichnet der Aufrufer."""
    c = d.i32c
    lives, k1, k2, k3, torch, level, score, phase, pt = d.unb(st, ['Lives', 'KeyR', 'KeyB', 'KeyY', 'Torch', 'Level', 'Score', 'Phase', 'PhaseTicks'])

    def sprite(p, err, ix, x, y):
        r = d.call('Sprite_Draw.vi', [('Picture', p), ('Sprites', spr), ('Index', ix), ('Position', d.bun(d.const(POS, '[0,0]'), [('X', x), ('Y', y)])),
                                      ('error in', err)], ['Picture out', 'error out'])
        return r['Picture out'], r['error out']

    def text(p, err, s, x, y):
        r = d.call('Glyphs_Draw.vi', [('Picture', p), ('Sprites', spr), ('Text', s), ('Position', d.const(POS, f'[{x},{y}]')), ('error in', err)],
                   ['Picture out', 'error out'])
        return r['Picture out'], r['error out']

    n = clampv(d, lives, c(0), c(MAX_LIVES))
    cn = counter(d, n)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, cn, 'index')
    sp = d.tunnel_in(2, spr)
    p_l, p_r = shiftreg(d, lp, pic)
    e_l, e_r = shiftreg(d, lp, e)
    r = d.call('Sprite_Draw.vi', [('Picture', p_l), ('Sprites', sp), ('Index', c(SPR['life'])),
                                  ('Position', d.bun(d.const(POS, '[0,30]'), [('X', d.add2(c(22), d.mul(i, c(36))))])), ('error in', e_l)],
               ['Picture out', 'error out'])
    d.end()
    pic, err = close_reg(d, p_r, r['Picture out']), close_reg(d, e_r, r['error out'])
    for k, (kv, name) in enumerate(((k1, 'key_r'), (k2, 'key_b'), (k3, 'key_y'))):
        pic, err = sprite(pic, err, c(SPR[name]), c(320 + 84 * k), c(30))
        pic, err = text(pic, err, fmt(d, '%d', minv(d, kv, c(9))), 352 + 84 * k, 30)
    pic, err = sprite(pic, err, c(SPR['torch_0']), c(640), d.sel(torch, c(30), c(-2000)))
    pic, err = text(pic, err, fmt(d, '%d', level), 768, 30)
    pic, err = text(pic, err, fmt(d, '%06d', score), 902, 30)
    limit = d.idx(table(d, LV_TREASURE, 'Treasure time'), lvl_index(d, level))
    secs = d.qr(d.add2(maxv(d, d.sub(limit, pt), c(0)), c(59)), c(60))[1]
    in_t = d.eq(phase, c(PH['Treasure']))
    tstr = d.sel(in_t, fmt(d, '%02d', secs), d.const('string', ''))
    pic, err = text(pic, err, tstr, 1156, 30)
    return pic, err


def hud_draw():
    d = Doc('Hud_Draw.vi', f'Draws the HUD ({W} x {HUD_H} px) as one piece of image data: lives (at most {MAX_LIVES} heads), keys with '
            'their number, the torch, level, gold (score) and in the treasure room the seconds left.')
    spr = d.ctrl('Sprites', SPRITES, '[]', 0)
    hud = d.ctrl('Hud', IMG, IMG_V, 5)
    st = d.ctrl('State', STATE, STATE_V, 7)
    e = d.err_in()
    c = d.i32c
    pic = d.call('Draw Flattened Pixmap.vi', [('image data', hud), ('picture', '')], ['new picture'])['new picture']
    pic, err = hud_ops(d, pic, spr, st, e)
    pm = d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', c(24)), ('rect', d.const(RECT, f'[0,0,{W},{HUD_H}]')), ('picture', pic)],
                ['image data', '-new picture'])['image data']
    d.indic('Piece', IMG, IMG_V, d.bun(pm, [('Rectangle', d.const(RECT, f'[0,0,{W},{HUD_H}]'))]), 4)
    d.err_out(err)
    d.write()


def overlay_draw():
    d = Doc('Overlay_Draw.vi', 'Draws the message of the phase on top: highscore table (title), DEMO - PRESS ENTER, LEVEL n / READY, PAUSE, '
            'TREASURE!, LEVEL CLEAR, GAME OVER and the name entry. Only when its box meets Clip (screen pixels).')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    st = d.ctrl('State', STATE, STATE_V, 7)
    clip = d.ctrl('Clip', RECT, f'[0,0,{W},{H}]', 9)
    e = d.err_in()
    c = d.i32c
    phase, pt, level, start, tab, letters, cur = d.unb(st, ['Phase', 'PhaseTicks', 'Level', 'LevelStart', 'Highscores', 'Name', 'Cursor'])
    S = lambda s: d.const('string', s)
    sw = (SPR['box_small'], BOX_SMALL[0], BOX_SMALL[1], 320, 56)
    ww = (SPR['box_wide'], BOX_WIDE[0], BOX_WIDE[1], 480, 56)
    bw = (SPR['box_big'], BOX_BIG[0], BOX_BIG[1], 560, 300)
    nobox = (-1, 0, -2000, 0, 0)
    LINES, YS = 'array{string}', 'array{int32}'

    def frame(box, lines, ys):
        def body(i):
            boxv = [c(v) for v in box]
            # Text = Konstante, Netzname (z. B. '1092.o0') = schon berechneter Text
            nets = [l if re.fullmatch(r'\d+\.\w+', l) else S(l) for l in lines]
            larr = d.node('Build Array', [('element', l) for l in nets], ['appended array'])['appended array'] if lines else d.const(LINES, '[]')
            yarr = table(d, ys, 'Line y') if ys else d.const(YS, '[]')
            return boxv + [larr, yarr]
        return body

    def small(text_net):
        return lambda i: frame(sw, [text_net(i)], [BOX_SMALL[1] + 12])(i)

    def f_title(i):
        show = ge(d, i[1], c(TITLE_CARD))
        lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
        k = f'{lp}i.v'
        hs = d.tunnel_in(1, i[2], 'index')
        sc, nm = d.unb(hs, ['Score', 'Name'])
        line = fmt(d, '%d. %06d %-9s', d.inc(k), sc, nm)
        lines = d.tunnel_out(1, line, 'index')
        d.end()
        head = d.node('Build Array', [('element', S('HIGH SCORES'))], ['appended array'])['appended array']
        all_lines = d.node('Build Array', [('array', head), ('array', lines)], ['appended array'], extra='concat="true"')['appended array']
        ys = table(d, [BOX_BIG[1] + 16] + [BOX_BIG[1] + 68 + 44 * k for k in range(HS_MAX)], 'Line y')
        boxv = [d.sel(show, c(v), c(n)) for v, n in zip(bw, nobox)]
        return boxv + [all_lines, ys]

    def f_ready(i):
        txt = d.sel(i[3], fmt(d, 'LEVEL %d', i[4]), S('READY'))
        return frame(sw, [txt], [BOX_SMALL[1] + 12])(i)

    def f_treasure(i):
        show = d.lt(i[1], c(TREASURE_MSG))
        boxv = [d.sel(show, c(v), c(n)) for v, n in zip(sw, nobox)]
        return boxv + [d.node('Build Array', [('element', S('TREASURE!'))], ['appended array'])['appended array'],
                       table(d, [BOX_SMALL[1] + 12], 'Line y')]

    def f_name(i):
        name = name_text(d, i[5])
        under = d.node('Replace Array Subset', [('array', d.const('array{int32}', '[' + ','.join(['26'] * NAME_LEN) + ']')),
                                               ('new element/subarray', c(-1)), ('index', i[6])], ['output array'])['output array']
        # Cursor: '-' unter dem gewaehlten Buchstaben (Index -1 -> '-' ueber eine eigene Zeichenfolge)
        dash, empty = d.const('string', '-'), d.const('string', '')
        lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
        u = d.tunnel_in(1, under, 'index')
        ds = d.tunnel_in(2, dash)
        s_l, s_r = shiftreg(d, lp, empty)
        ch = d.sel(d.lt(u, d.i32c(0)), ds, d.const('string', ' '))
        s2 = d.node('Concatenate Strings', [('string', s_l), ('string', ch)], ['concatenated string'])['concatenated string']
        d.end()
        cursor_line = close_reg(d, s_r, s2)
        return frame(bw, ['NEW HIGH SCORE', 'ENTER YOUR NAME', name, cursor_line, 'ENTER = OK'],
                     [BOX_BIG[1] + 16, BOX_BIG[1] + 64, BOX_BIG[1] + 136, BOX_BIG[1] + 168, BOX_BIG[1] + 232])(i)

    ins = [phase, pt, tab, start, level, letters, cur]
    frames = [(str(PH['Title']), f_title),
              (str(PH['Demo']), frame(ww, ['DEMO - PRESS ENTER'], [BOX_WIDE[1] + 12])),
              (str(PH['Ready']), f_ready),
              (str(PH['Paused']), frame(sw, ['PAUSE'], [BOX_SMALL[1] + 12])),
              (str(PH['Treasure']), f_treasure),
              (str(PH['LevelDone']), frame(sw, ['LEVEL CLEAR'], [BOX_SMALL[1] + 12])),
              (str(PH['GameOver']), frame(sw, ['GAME OVER'], [BOX_SMALL[1] + 12])),
              (str(PH['Name']), f_name),
              ('Default', frame(nobox, [], []))]
    bix, bx, by, bwid, bhgt, lines, ys = d.case(phase, ins, frames, 7)
    cl, ct, cr, cb = (d.i32(v) for v in d.unb(clip, ['left', 'top', 'right', 'bottom']))
    meets = allb(d, ge(d, bix, c(0)), d.lt(bx, cr), d.lt(cl, d.add2(bx, bwid)), d.lt(by, cb), d.lt(ct, d.add2(by, bhgt)))

    def draw(j):
        p, sp, ix, x, y, ls, yy, err = j
        r = d.call('Sprite_Draw.vi', [('Picture', p), ('Sprites', sp), ('Index', ix), ('Position', d.bun(d.const(POS, '[0,0]'), [('X', x), ('Y', y)])),
                                      ('error in', err)], ['Picture out', 'error out'])
        lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
        line = d.tunnel_in(1, ls, 'index')
        ly = d.tunnel_in(2, yy, 'index')
        sp2 = d.tunnel_in(3, sp)
        p_l, p_r = shiftreg(d, lp, r['Picture out'])
        e_l, e_r = shiftreg(d, lp, r['error out'])
        n = d.node('String Length', [('string', line)], ['length'])['length']
        lx = d.sub(d.i32c(W // 2), d.mul(n, d.i32c(GLYPH_W // 2)))
        g = d.call('Glyphs_Draw.vi', [('Picture', p_l), ('Sprites', sp2), ('Text', line), ('Position', d.bun(d.const(POS, '[0,0]'), [('X', lx), ('Y', ly)])),
                                      ('error in', e_l)], ['Picture out', 'error out'])
        d.end()
        return [close_reg(d, p_r, g['Picture out']), close_reg(d, e_r, g['error out'])]

    pic2, err2 = d.case(meets, [pic, spr, bix, bx, by, lines, ys, e], [('True', draw), ('False', lambda j: [j[0], j[7]])], 2)
    d.indic('Picture out', 'picture', '', pic2, 4)
    d.err_out(err2)
    d.write()


def piece_compose():
    d = Doc('Piece_Compose.vi', 'Composes one piece of the screen: the tiles Rect of the room raster, the objects in it (Room_Draw), the '
            'enemies, Claude and the message of the phase, rastered invisibly into ONE pixmap (no flicker, no seams).')
    grid = d.ctrl('Grid', GRID, '[]', 0)
    tmpl = d.ctrl('Template', IMG, IMG_V, 5)
    rect = d.ctrl('Rect', RECT, '[0,0,40,20]', 7)
    spr = d.ctrl('Sprites', SPRITES, '[]', 9)
    st = d.ctrl('State', STATE, STATE_V, 1)
    view = d.ctrl('View', VIEW, VIEW_V, 2)
    e = d.err_in()
    c = d.i32c
    gb = d.call('Grid_Block.vi', [('Grid', grid), ('Template', tmpl), ('Rect', rect), ('error in', e)], ['Block', 'error out'])
    (area,) = d.unb(gb['Block'], ['Rectangle'])
    l, t, r, b = (d.i32(v) for v in d.unb(area, ['left', 'top', 'right', 'bottom']))
    region = d.bun(d.const(RECT, '[0,0,0,0]'), [('left', w16(d, d.qr(l, c(TILE))[1])), ('top', w16(d, d.qr(d.sub(t, c(HUD_H)), c(TILE))[1])),
                                                ('right', w16(d, d.qr(r, c(TILE))[1])), ('bottom', w16(d, d.qr(d.sub(b, c(HUD_H)), c(TILE))[1]))])
    tiles, enemies, tick, fphase = d.unb(st, ['Tiles', 'Enemies', 'Tick', 'FloorPhase'])
    p0 = d.call('Draw Flattened Pixmap.vi', [('image data', gb['Block']), ('picture', '')], ['new picture'])['new picture']
    rd = d.call('Room_Draw.vi', [('Picture', p0), ('Sprites', spr), ('Tiles', tiles), ('Region', region), ('FloorPhase', fphase), ('View', view),
                                 ('error in', gb['error out'])], ['Picture out', 'error out'])
    ed = d.call('Enemies_Draw.vi', [('Picture', rd['Picture out']), ('Sprites', spr), ('Enemies', enemies), ('Tick', tick), ('View', view),
                                    ('error in', rd['error out'])], ['Picture out', 'error out'])
    cix, cxp, cyp = d.unb(view, ['ClaudeIdx', 'ClaudeX', 'ClaudeY'])
    cpos = d.bun(d.const(POS, '[0,0]'), [('X', cxp), ('Y', d.sel(ge(d, cix, c(0)), cyp, c(-2000)))])
    cd = d.call('Sprite_Draw.vi', [('Picture', ed['Picture out']), ('Sprites', spr), ('Index', maxv(d, cix, c(0))), ('Position', cpos),
                                   ('error in', ed['error out'])], ['Picture out', 'error out'])
    ov = d.call('Overlay_Draw.vi', [('Picture', cd['Picture out']), ('Sprites', spr), ('State', st), ('Clip', area), ('error in', cd['error out'])],
                ['Picture out', 'error out'])
    pm = d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', c(24)), ('rect', area), ('picture', ov['Picture out'])],
                ['image data', '-new picture'])['image data']
    d.indic('Piece', IMG, IMG_V, d.bun(pm, [('Rectangle', area)]), 4)
    d.err_out(ov['error out'])
    d.write()


def scene_draw():
    d = Doc('Scene_Draw.vi', 'Draws the WHOLE screen as one picture of draw commands (like Pauls Hoehenflug, without rastering): on the '
            'title the title card and the overlay; otherwise the HUD picture with its values, the room raster (Grid, lit or the dark '
            'composite) and on it the objects (Room_Draw), the enemies, Claude and the message of the phase.')
    grid = d.ctrl('Grid', GRID, '[]', 0)
    tmpl = d.ctrl('Template', IMG, IMG_V, 5)
    spr = d.ctrl('Sprites', SPRITES, '[]', 7)
    st = d.ctrl('State', STATE, STATE_V, 9)
    view = d.ctrl('View', VIEW, VIEW_V, 1)
    hud = d.ctrl('Hud', IMG, IMG_V, 2)
    title = d.ctrl('Title', IMG, IMG_V, 3)
    e = d.err_in()
    c = d.i32c
    phase, = d.unb(st, ['Phase'])
    is_title = d.eq(phase, c(PH['Title']))
    full = d.const(RECT, f'[0,0,{W},{H}]', 'Whole screen')

    def f_title(i):
        p0 = d.call('Draw Flattened Pixmap.vi', [('image data', i[0]), ('picture', '')], ['new picture'])['new picture']
        ov = d.call('Overlay_Draw.vi', [('Picture', p0), ('Sprites', i[1]), ('State', i[2]), ('Clip', i[3]), ('error in', i[4])],
                    ['Picture out', 'error out'])
        return [ov['Picture out'], ov['error out']]

    def f_game(i):
        _, sp, s, clip, err, g, tp, vw, hd = i
        p0 = d.call('Draw Flattened Pixmap.vi', [('image data', hd), ('picture', '')], ['new picture'])['new picture']
        p1, err1 = hud_ops(d, p0, sp, s, err)
        gb = d.call('Grid_Block.vi', [('Grid', g), ('Template', tp), ('Rect', d.const(RECT, f'[0,0,{COLS},{ROWS}]')), ('error in', err1)],
                    ['Block', 'error out'])
        p2 = d.call('Draw Flattened Pixmap.vi', [('image data', gb['Block']), ('picture', p1)], ['new picture'])['new picture']
        tiles, enemies, tick, fphase = d.unb(s, ['Tiles', 'Enemies', 'Tick', 'FloorPhase'])
        rd = d.call('Room_Draw.vi', [('Picture', p2), ('Sprites', sp), ('Tiles', tiles), ('Region', d.const(RECT, f'[0,0,{COLS},{ROWS}]')),
                                     ('FloorPhase', fphase), ('View', vw), ('error in', gb['error out'])], ['Picture out', 'error out'])
        ed = d.call('Enemies_Draw.vi', [('Picture', rd['Picture out']), ('Sprites', sp), ('Enemies', enemies), ('Tick', tick), ('View', vw),
                                        ('error in', rd['error out'])], ['Picture out', 'error out'])
        cix, cxp, cyp = d.unb(vw, ['ClaudeIdx', 'ClaudeX', 'ClaudeY'])
        cpos = d.bun(d.const(POS, '[0,0]'), [('X', cxp), ('Y', d.sel(ge(d, cix, c(0)), cyp, c(-2000)))])
        cd = d.call('Sprite_Draw.vi', [('Picture', ed['Picture out']), ('Sprites', sp), ('Index', maxv(d, cix, c(0))), ('Position', cpos),
                                       ('error in', ed['error out'])], ['Picture out', 'error out'])
        ov = d.call('Overlay_Draw.vi', [('Picture', cd['Picture out']), ('Sprites', sp), ('State', s), ('Clip', clip), ('error in', cd['error out'])],
                    ['Picture out', 'error out'])
        return [ov['Picture out'], ov['error out']]

    pic, err = d.case(is_title, [title, spr, st, full, e, grid, tmpl, view, hud],
                      [('True', f_title), ('False', f_game)], 2)
    d.indic('Picture', 'picture', '', pic, 4)
    d.err_out(err)
    d.write()


def frame_draw_full():
    d = Doc('Frame_Draw.vi', 'Draws one frame: the WHOLE screen every frame (Scene_Draw, like Pauls Hoehenflug) - every update of the '
            'picture control is complete, so nothing can stay behind and LabVIEW may skip frames without harm. Memory keeps the room '
            'pictures (loaded on a new room or level) and the composite of a dark room, whose light circle Light_Update moves '
            'incrementally. Pieces stays empty (kept for the interface).')
    st = d.ctrl('State', STATE, STATE_V, 0)
    spr = d.ctrl('Sprites', SPRITES_USED, '[]', 5)
    hud = d.ctrl('Hud', IMG, IMG_V, 7)
    title = d.ctrl('Title', IMG, IMG_V, 9)
    mem = d.ctrl('Memory', RMEM, RMEM_V, 1)
    e = d.err_in()
    c = d.i32c
    room, level, phase, pt, x10, y10, vy, mode, facing, run, tick, torch, world = d.unb(
        st, ['Room', 'Level', 'Phase', 'PhaseTicks', 'X10', 'Y10', 'VY10', 'Mode', 'Facing', 'Run', 'Tick', 'Torch', 'World'])
    m_roomkey, m_lit, m_dim, m_dark, m_comp, m_tmpl, m_cx, m_cy = d.unb(mem, ['RoomKey', 'Lit', 'Dim', 'Dark', 'Comp', 'Template', 'CX', 'CY'])
    li = lvl_index(d, level)
    theme = d.idx(table(d, LV_THEME, 'Theme'), li)
    rid, depth = d.unb(d.idx(world, room), ['ID', 'Depth'])
    is_title = d.eq(phase, c(PH['Title']))
    dark = allb(d, ge(d, depth, d.idx(table(d, LV_DARK, 'Dark from'), li)), d.not_(torch), d.not_(is_title), d.ne(room, c(TREASURE_IDX)))
    roomkey = d.add2(room, d.mul(theme, c(100)))
    load = d.and_(d.ne(roomkey, m_roomkey), d.not_(is_title))
    lit, dim, drk, tmpl, err = d.case(load, [rid, theme, m_lit, m_dim, m_dark, m_tmpl, e], [
        ('True', lambda i: (lambda r: [r['Lit'], r['Dim'], r['Dark'], r['Template'], r['error out']])(
            d.call('Room_Images.vi', [('Room ID', i[0]), ('Theme', i[1]), ('error in', i[6])], ['Lit', 'Dim', 'Dark', 'Template', 'error out']))),
        ('False', lambda i: [i[2], i[3], i[4], i[5], i[6]]),
    ], 5)
    x, y = px(d, x10), px(d, y10)
    cxt, cyt = d.qr(d.add2(x, c(16)), c(TILE))[1], d.qr(d.add2(y, c(24)), c(TILE))[1]
    # Lichtkreis im dunklen Raum: nur neu rechnen, wenn der Raum neu ist oder Claude die Kachel wechselt
    moved = anyb(d, load, d.ne(cxt, m_cx), d.ne(cyt, m_cy))
    comp, err2 = d.case(d.and_(dark, moved), [m_comp, lit, dim, drk, m_cx, m_cy, cxt, cyt, err, load], [
        ('True', lambda q: (lambda r: [r['Comp out'], r['error out']])(
            d.call('Light_Update.vi', [('Comp', d.sel(q[9], q[3], q[0])), ('Lit', q[1]), ('Dim', q[2]), ('Dark', q[3]),
                                       ('Old CX', d.sel(q[9], d.i32c(-100), q[4])), ('Old CY', d.sel(q[9], d.i32c(-100), q[5])),
                                       ('CX', q[6]), ('CY', q[7]), ('error in', q[8])], ['Comp out', '-Rect', 'error out']))),
        ('False', lambda q: [q[0], q[8]]),
    ], 2)
    grid = d.sel(dark, comp, lit)
    # Bild von Claude (wie bisher)
    side = d.mul(facing, c(SPR_SIDE_STEP))
    walk = d.inc(d.qr(d.qr(d.i32(tick), c(6))[1], c(4))[0])
    on_ground = d.add2(side, d.sel(d.ne(run, c(0)), walk, c(0)))
    in_air = d.add2(side, d.sel(d.lt(vy, c(0)), c(5), c(6)))
    climbing = d.sub(d.add2(c(SPR['claude_climb_0']), d.qr(d.qr(y, c(8))[1], c(2))[0]), c(SPR['claude_r_stand']))
    normal = d.add2(c(SPR['claude_r_stand']), d.sel(d.eq(mode, c(0)), on_ground, d.sel(d.eq(mode, c(1)), climbing,
                                                                                        d.sel(d.eq(mode, c(2)), in_air, c(SPR['claude_slide'] - SPR['claude_r_stand'])))))
    dying = anyb(d, d.eq(phase, c(PH['Dying'])), d.eq(phase, c(PH['GameOver'])))
    flash = d.and_(d.lt(pt, c(40)), d.eq(d.qr(d.qr(pt, c(4))[1], c(2))[0], c(0)))
    dead_ix = d.sel(d.and_(d.eq(phase, c(PH['Dying'])), d.lt(pt, c(40))), d.sel(flash, c(SPR['claude_dead_0']), normal), c(SPR['claude_dead_1']))
    cix = d.sel(is_title, c(-1), d.sel(dying, dead_ix, normal))
    view = d.bun(d.const(VIEW, VIEW_V), [('Hide', dark), ('CX', cxt), ('CY', cyt), ('ClaudeIdx', cix), ('ClaudeX', x), ('ClaudeY', d.add2(y, c(HUD_H)))])
    if FULL_BLIT:
        # das ganze Bild entsteht als Pixel-Array (Scene_Blit) und wird mit EINEM Draw Flattened Pixmap gezeichnet
        sb = d.call('Scene_Blit.vi', [('Grid', grid), ('Sprites', spr), ('State', st), ('View', view), ('Hud', hud), ('Title', title),
                                      ('error in', err2)], ['Picture', 'error out'])
        flat = d.node('Reshape Array', [('array', sb['Picture']), ('dimension size', c(H * W * 3))], ['output array'])['output array']
        img = d.bun(title, [('image', flat), ('mask', d.const('array{uint8}', '[]')), ('Rectangle', d.const(RECT, f'[0,0,{W},{H}]'))])
        one = d.call('Draw Flattened Pixmap.vi', [('image data', img), ('picture', '')], ['new picture'])['new picture']
        sd = {'error out': sb['error out']}
    else:
        sd = d.call('Scene_Draw.vi', [('Grid', grid), ('Template', tmpl), ('Sprites', spr), ('State', st), ('View', view), ('Hud', hud), ('Title', title),
                                      ('error in', err2)], ['Picture', 'error out'])
        # EIN Raster des ganzen Bildschirms, dann EIN Zeichenbefehl: der Bildschirm wechselt in einem Zug (kein Flackern)
        pm = d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', c(24)), ('rect', d.const(RECT, f'[0,0,{W},{H}]')), ('picture', sd['Picture'])],
                    ['image data', '-new picture'])['image data']
        one = d.call('Draw Flattened Pixmap.vi', [('image data', pm), ('picture', '')], ['new picture'])['new picture']
    mem2 = d.bun(mem, [('RoomKey', d.sel(is_title, m_roomkey, roomkey)), ('Lit', lit), ('Dim', dim), ('Dark', drk), ('Comp', comp), ('Template', tmpl),
                       ('CX', d.sel(dark, cxt, c(-100))), ('CY', d.sel(dark, cyt, c(-100)))])
    d.indic('Picture', 'picture', '', one, 4)
    d.indic('Pieces', PIECES, '[]', d.const(PIECES, '[]', 'No pieces'), 6)
    d.indic('Memory out', RMEM, RMEM_V, mem2, 8)
    d.err_out(sd['error out'])
    d.write()

def frame_draw():
    if FULL_EVERY_FRAME:
        return frame_draw_full()
    d = Doc('Frame_Draw.vi', 'Draws one frame for a picture control that never erases, as a list of pieces (image data with their screen '
            'rectangle). Full redraw (new room, level, message, floor phase or light mode): the HUD and the whole playfield, on the title '
            'the title card. Otherwise only: the piece around the last three positions of Claude, one piece per enemy, the piece where the '
            'light moved (dark room) and the HUD when a value changed. Memory keeps the room pictures, the composite of the dark room '
            'and the last positions. Picture = all pieces drawn in order.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    hud = d.ctrl('Hud', IMG, IMG_V, 7)
    title = d.ctrl('Title', IMG, IMG_V, 9)
    mem = d.ctrl('Memory', RMEM, RMEM_V, 1)
    e = d.err_in()
    c = d.i32c
    (room, level, phase, pt, x10, y10, vy, mode, facing, run, tick, torch, fphase, world, enemies, letters, cur, lives, k1, k2, k3, score,
     lstart) = d.unb(st, ['Room', 'Level', 'Phase', 'PhaseTicks', 'X10', 'Y10', 'VY10', 'Mode', 'Facing', 'Run', 'Tick', 'Torch', 'FloorPhase',
                          'World', 'Enemies', 'Name', 'Cursor', 'Lives', 'KeyR', 'KeyB', 'KeyY', 'Score', 'LevelStart'])
    (m_roomkey, m_key, m_namekey, m_lit, m_dim, m_dark, m_comp, m_tmpl, m_cx, m_cy, m_x1, m_y1, m_x2, m_y2, m_prev, m_hudkey, m_hudscore,
     m_hudtime, m_full) = d.unb(mem, ['RoomKey', 'Key', 'NameKey', 'Lit', 'Dim', 'Dark', 'Comp', 'Template', 'CX', 'CY', 'X1', 'Y1', 'X2', 'Y2', 'Prev',
                               'HudKey', 'HudScore', 'HudTime', 'Full'])
    li = lvl_index(d, level)
    theme = d.idx(table(d, LV_THEME, 'Theme'), li)
    here = d.idx(world, room)
    rid, depth = d.unb(here, ['ID', 'Depth'])
    is_title = d.eq(phase, c(PH['Title']))
    dark = allb(d, ge(d, depth, d.idx(table(d, LV_DARK, 'Dark from'), li)), d.not_(torch), d.not_(is_title), d.ne(room, c(TREASURE_IDX)))
    roomkey = d.add2(room, d.mul(theme, c(100)))
    load = d.and_(d.ne(roomkey, m_roomkey), d.not_(is_title))
    lit, dim, drk, tmpl, err = d.case(load, [rid, theme, m_lit, m_dim, m_dark, m_tmpl, e], [
        ('True', lambda i: (lambda r: [r['Lit'], r['Dim'], r['Dark'], r['Template'], r['error out']])(
            d.call('Room_Images.vi', [('Room ID', i[0]), ('Theme', i[1]), ('error in', i[6])], ['Lit', 'Dim', 'Dark', 'Template', 'error out']))),
        ('False', lambda i: [i[2], i[3], i[4], i[5], i[6]]),
    ], 5)
    roomkey2 = d.sel(is_title, m_roomkey, roomkey)
    x, y = px(d, x10), px(d, y10)
    cxt, cyt = d.qr(d.add2(x, c(16)), c(TILE))[1], d.qr(d.add2(y, c(24)), c(TILE))[1]
    # Bild von Claude
    side = d.mul(facing, c(SPR_SIDE_STEP))
    walk = d.inc(d.qr(d.qr(d.i32(tick), c(6))[1], c(4))[0])
    on_ground = d.add2(side, d.sel(d.ne(run, c(0)), walk, c(0)))
    in_air = d.add2(side, d.sel(d.lt(vy, c(0)), c(5), c(6)))
    climbing = d.sub(d.add2(c(SPR['claude_climb_0']), d.qr(d.qr(y, c(8))[1], c(2))[0]), c(SPR['claude_r_stand']))
    normal = d.add2(c(SPR['claude_r_stand']), d.sel(d.eq(mode, c(0)), on_ground, d.sel(d.eq(mode, c(1)), climbing,
                                                                                        d.sel(d.eq(mode, c(2)), in_air, c(SPR['claude_slide'] - SPR['claude_r_stand'])))))
    dying = anyb(d, d.eq(phase, c(PH['Dying'])), d.eq(phase, c(PH['GameOver'])))
    flash = d.and_(d.lt(pt, c(40)), d.eq(d.qr(d.qr(pt, c(4))[1], c(2))[0], c(0)))
    dead_ix = d.sel(d.and_(d.eq(phase, c(PH['Dying'])), d.lt(pt, c(40))), d.sel(flash, c(SPR['claude_dead_0']), normal), c(SPR['claude_dead_1']))
    cix = d.sel(is_title, c(-1), d.sel(dying, dead_ix, normal))
    view = d.bun(d.const(VIEW, VIEW_V), [('Hide', dark), ('CX', cxt), ('CY', cyt), ('ClaudeIdx', cix), ('ClaudeX', x), ('ClaudeY', d.add2(y, c(HUD_H)))])
    # Schluessel fuer die volle Neuzeichnung
    ov = d.add2(d.mul(phase, c(10)), d.add2(d.i32(d.b01(d.and_(is_title, ge(d, pt, c(TITLE_CARD))))),
                                           d.i32(d.b01(d.and_(d.eq(phase, c(PH['Treasure'])), d.lt(pt, c(TREASURE_MSG)))))))
    key = d.add2(d.add2(roomkey, d.mul(fphase, c(10000))), d.add2(d.mul(d.i32(d.b01(dark)), c(100000)), d.mul(ov, c(1000000))))
    key = d.add2(key, d.mul(d.i32(d.b01(lstart)), c(7)))
    # alle 120 Ticks (2 s) volle Neuzeichnung: LabVIEW malt das Bild bei jedem Neuzeichnen des Fensters (Klick, Verdecken)
    # nur aus dem letzten Wert - also nur aus den letzten Stuecken. So heilt der Bildschirm nach spaetestens 2 s.
    key = d.add2(key, d.mul(d.qr(d.qr(d.i32(tick), c(REFRESH_TICKS))[1], c(2))[0], c(3)))
    zero_n = c(0)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    lt_ = d.tunnel_in(1, letters, 'index')
    n_l, n_r = shiftreg(d, lp, zero_n)
    n2 = d.add2(n_l, d.mul(lt_, d.add2(d.mul(i, c(29)), c(7))))
    d.end()
    namekey = d.add2(close_reg(d, n_r, n2), d.mul(cur, c(1000)))
    # LabVIEW malt Anzeigen asynchron: kommt ein neuer Wert, bevor der alte gemalt ist, faellt der alte weg. Darum wird
    # eine volle Neuzeichnung in REPEAT_FULL weiteren Bildern wiederholt. Der Zaehler steckt im Feld Key (Bits ab 2^28).
    k_base, k_cnt = d.qr(m_key, c(1 << 28))
    new_full = anyb(d, d.ne(key, k_base), d.ne(namekey, m_namekey), load)
    if FULL_EVERY_FRAME:                # wie Pauls Spiel: jedes Bild ist der ganze Bildschirm
        new_full = d.or_(new_full, d.const('bool', 'true'))
    full = d.or_(new_full, d.gt(k_cnt, c(0)))
    cnt2 = d.sel(new_full, c(REPEAT_FULL), maxv(d, d.sub(k_cnt, c(1)), c(0)))
    key_mem = d.add2(key, d.mul(cnt2, c(1 << 28)))
    hudkey = d.add2(d.add2(lives, d.mul(k1, c(8))), d.add2(d.mul(k2, c(80)), d.add2(d.mul(k3, c(800)), d.add2(
        d.mul(d.i32(d.b01(torch)), c(8000)), d.mul(level, c(16000))))))
    tlimit = d.idx(table(d, LV_TREASURE, 'Treasure time'), li)
    hudtime = d.sel(d.eq(phase, c(PH['Treasure'])), d.qr(maxv(d, d.sub(tlimit, pt), c(0)), c(60))[1], c(-1))
    # HUD ebenso: nach einer Aenderung REPEAT_FULL weitere Bilder lang mitschicken (Zaehler in HudKey ab 2^28)
    h_base, h_cnt = d.qr(m_hudkey, c(1 << 28))
    hud_new = anyb(d, full, d.ne(hudkey, h_base), d.ne(score, m_hudscore), d.ne(hudtime, m_hudtime))
    hud_changed = d.or_(hud_new, d.gt(h_cnt, c(0)))
    hcnt2 = d.sel(hud_new, c(REPEAT_FULL), maxv(d, d.sub(h_cnt, c(1)), c(0)))
    hudkey_mem = d.add2(hudkey, d.mul(hcnt2, c(1 << 28)))

    def f_full(j):
        lit_, dim_, drk_, tmpl_, sp, s, vw, hd, tt, dk, ccx, ccy, ist, err = j
        comp, err2 = d.case(dk, [drk_, lit_, dim_, ccx, ccy, err], [
            ('True', lambda q: (lambda r: [r['Comp out'], r['error out']])(
                d.call('Light_Update.vi', [('Comp', q[0]), ('Lit', q[1]), ('Dim', q[2]), ('Dark', q[0]), ('Old CX', d.i32c(-100)), ('Old CY', d.i32c(-100)),
                                           ('CX', q[3]), ('CY', q[4]), ('error in', q[5])], ['Comp out', '-Rect', 'error out']))),
            ('False', lambda q: [q[1], q[5]]),
        ], 2)

        def title_piece(q):
            p0 = d.call('Draw Flattened Pixmap.vi', [('image data', q[0]), ('picture', '')], ['new picture'])['new picture']
            ovd = d.call('Overlay_Draw.vi', [('Picture', p0), ('Sprites', q[1]), ('State', q[2]), ('Clip', d.const(RECT, f'[0,0,{W},{H}]')), ('error in', q[3])],
                         ['Picture out', 'error out'])
            pm = d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', d.i32c(24)), ('rect', d.const(RECT, f'[0,0,{W},{H}]')),
                                                 ('picture', ovd['Picture out'])], ['image data', '-new picture'])['image data']
            pc = d.bun(pm, [('Rectangle', d.const(RECT, f'[0,0,{W},{H}]'))])
            return [d.node('Build Array', [('element', pc)], ['appended array'])['appended array'], ovd['error out']]

        def game_pieces(q):
            tpl, sp2, s2, vw2, hd2, cp, err3 = q[0], q[1], q[2], q[4], q[5], q[6], q[3]
            pcs = d.call('Piece_Compose.vi', [('Grid', cp), ('Template', tpl), ('Rect', d.const(RECT, f'[0,0,{COLS},{ROWS}]')), ('Sprites', sp2),
                                              ('State', s2), ('View', vw2), ('error in', err3)], ['Piece', 'error out'])
            hp = d.call('Hud_Draw.vi', [('Sprites', sp2), ('Hud', hd2), ('State', s2), ('error in', pcs['error out'])], ['Piece', 'error out'])
            return [d.node('Build Array', [('element', hp['Piece']), ('element', pcs['Piece'])], ['appended array'])['appended array'], hp['error out']]

        pieces, err4 = d.case(ist, [tt, sp, s, err2, vw, hd, comp, tmpl_], [
            ('True', lambda q: title_piece(q)),
            ('False', lambda q: game_pieces([q[7], q[1], q[2], q[3], q[4], q[5], q[6]])),
        ], 2)
        return [pieces, comp, err4]

    def f_part(j):
        lit_, dim_, drk_, tmpl_, sp, s, vw, hd, tt, dk, ccx, ccy, ist, err = j
        x, y = m_xc_t, m_yc_t
        moved_light = allb(d, dk, d.or_(d.ne(ccx, m_cx_t), d.ne(ccy, m_cy_t)))
        comp, lrect, err2 = d.case(moved_light, [m_comp_t, lit_, dim_, drk_, m_cx_t, m_cy_t, ccx, ccy, err, dk], [
            ('True', lambda q: (lambda r: [r['Comp out'], r['Rect'], r['error out']])(
                d.call('Light_Update.vi', [('Comp', q[0]), ('Lit', q[1]), ('Dim', q[2]), ('Dark', q[3]), ('Old CX', q[4]), ('Old CY', q[5]),
                                           ('CX', q[6]), ('CY', q[7]), ('error in', q[8])], ['Comp out', 'Rect', 'error out']))),
            ('False', lambda q: [d.sel(q[9], q[0], q[1]), d.const(RECT, '[0,0,0,0]'), q[8]]),
        ], 3)
        # Rechteck um Claude (letzte drei Positionen, eine Kachel Rand)
        xs = [x, m_x1_t, m_x2_t]
        ys = [y, m_y1_t, m_y2_t]
        mnx, mxx = minv(d, minv(d, xs[0], xs[1]), xs[2]), maxv(d, maxv(d, xs[0], xs[1]), xs[2])
        mny, mxy = minv(d, minv(d, ys[0], ys[1]), ys[2]), maxv(d, maxv(d, ys[0], ys[1]), ys[2])
        crect = d.bun(d.const(RECT, '[0,0,0,0]'), [('left', w16(d, d.sub(d.qr(mnx, c(TILE))[1], c(1)))), ('top', w16(d, d.sub(d.qr(mny, c(TILE))[1], c(1)))),
                                                   ('right', w16(d, d.add2(d.qr(d.add2(mxx, c(CLAUDE_W - 1)), c(TILE))[1], c(2)))),
                                                   ('bottom', w16(d, d.add2(d.qr(d.add2(mxy, c(CLAUDE_H - 1)), c(TILE))[1], c(2))))])
        # Rechtecke der Gegner (alte und neue Position)
        enl, prl = d.unb(s, ['Enemies'])[0], m_prev_t
        lp2 = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
        k = f'{lp2}i.v'
        en = d.tunnel_in(1, enl, 'index')
        pv = d.tunnel_in(2, prl)
        ex10, ey10 = d.unb(en, ['X10', 'Y10'])
        pv_k = d.idx(pv, k)
        pk = d.lt(k, size(d, pv))
        px10, py10 = d.unb(pv_k, ['X10', 'Y10'])
        ox10, oy10 = d.sel(pk, px10, ex10), d.sel(pk, py10, ey10)
        ax, bx_ = minv(d, px(d, ex10), px(d, ox10)), maxv(d, px(d, ex10), px(d, ox10))
        ay, by_ = minv(d, px(d, ey10), px(d, oy10)), maxv(d, px(d, ey10), px(d, oy10))
        er_ = d.bun(d.const(RECT, '[0,0,0,0]'), [('left', w16(d, d.qr(ax, c(TILE))[1])), ('top', w16(d, d.qr(ay, c(TILE))[1])),
                                                 ('right', w16(d, d.inc(d.qr(d.add2(bx_, c(31)), c(TILE))[1]))),
                                                 ('bottom', w16(d, d.inc(d.qr(d.add2(by_, c(31)), c(TILE))[1])))])
        erects = d.tunnel_out(1, er_, 'index')
        d.end()
        first = d.node('Build Array', [('element', crect)], ['appended array'])['appended array']
        with_light = d.sel(moved_light, d.node('Build Array', [('array', first), ('element', lrect)], ['appended array'], extra='concat="true"')['appended array'], first)
        rects0 = d.node('Build Array', [('array', with_light), ('array', erects)], ['appended array'], extra='concat="true"')['appended array']
        rects = d.sel(ist, d.const(f'array{{{RECT}}}', '[]', 'No pieces on the title'), rects0)
        lp3 = d.begin('For Loop', 'count="" maxin="" maxout=""')
        rc = d.tunnel_in(1, rects, 'index')
        a = [d.tunnel_in(n + 2, v) for n, v in enumerate((comp, tmpl_, sp, s, vw))]
        e_l, e_r = shiftreg(d, lp3, err2)
        pc = d.call('Piece_Compose.vi', [('Grid', a[0]), ('Template', a[1]), ('Rect', rc), ('Sprites', a[2]), ('State', a[3]), ('View', a[4]),
                                         ('error in', e_l)], ['Piece', 'error out'])
        pieces = d.tunnel_out(1, pc['Piece'], 'index')
        d.end()
        err3 = close_reg(d, e_r, pc['error out'])
        return [pieces, comp, err3]

    # Werte aus dem Gedaechtnis, die f_part braucht, als Tunnel in die Case-Struktur
    ins = [lit, dim, drk, tmpl, spr, st, view, hud, title, dark, cxt, cyt, is_title, err, m_cx, m_cy, m_comp, m_x1, m_y1, m_x2, m_y2, m_prev, x, y, m_full]

    def wrap(fn):
        def body(i):
            global m_cx_t, m_cy_t, m_comp_t, m_x1_t, m_y1_t, m_x2_t, m_y2_t, m_prev_t, m_xc_t, m_yc_t, m_full_t
            m_cx_t, m_cy_t, m_comp_t, m_x1_t, m_y1_t, m_x2_t, m_y2_t, m_prev_t, m_xc_t, m_yc_t, m_full_t = i[14:]
            return fn(i[:14])
        return body

    def f_repeat(j):
        return [m_full_t, m_comp_t, j[13]]

    # 0 = nur Stuecke, 1 = neue volle Neuzeichnung, 2 = Wiederholung der letzten (aus dem Gedaechtnis, kostet fast nichts)
    mode_ = d.sel(new_full, c(1), d.sel(full, c(2), c(0)))
    pieces, comp, err2 = d.case(mode_, ins, [('1', wrap(f_full)), ('2', wrap(f_repeat)), ('Default', wrap(f_part))], 3)
    full_mem = d.const(PIECES, '[]', 'No full picture kept') if FULL_EVERY_FRAME else d.sel(new_full, pieces, d.sel(full, m_full, d.const(PIECES, '[]', 'No full picture kept')))
    # HUD nur bei einer Aenderung (bei voller Neuzeichnung ist er schon dabei)
    hud_part = allb(d, hud_changed, d.not_(new_full), d.not_(is_title))
    pieces2, err3 = d.case(hud_part, [pieces, spr, hud, st, err2], [
        ('True', lambda q: (lambda r: [d.node('Build Array', [('array', q[0]), ('element', r['Piece'])], ['appended array'], extra='concat="true"')['appended array'],
                                       r['error out']])(
            d.call('Hud_Draw.vi', [('Sprites', q[1]), ('Hud', q[2]), ('State', q[3]), ('error in', q[4])], ['Piece', 'error out']))),
        ('False', lambda q: [q[0], q[4]]),
    ], 2)
    # Bild = alle Stuecke nacheinander
    empty_pic = d.call('Draw Flattened Pixmap.vi', [('image data', d.const(IMG, IMG_V, 'No pixels')), ('picture', '')], ['new picture'])['new picture']
    lp4 = d.begin('For Loop', 'count="" maxin="" maxout=""')
    pc = d.tunnel_in(1, pieces2, 'index')
    p_l, p_r = shiftreg(d, lp4, empty_pic)
    p2 = d.call('Draw Flattened Pixmap.vi', [('image data', pc), ('picture', p_l)], ['new picture'])['new picture']
    d.end()
    picture = close_reg(d, p_r, p2)
    mem2 = d.bun(mem, [('RoomKey', roomkey2), ('Key', key_mem),('NameKey', namekey), ('Lit', lit), ('Dim', dim), ('Dark', drk), ('Comp', comp),
                       ('Template', tmpl), ('CX', cxt), ('CY', cyt), ('X1', x), ('Y1', y), ('X2', d.sel(full, x, m_x1)), ('Y2', d.sel(full, y, m_y1)),
                       ('Prev', enemies), ('HudKey', hudkey_mem),('HudScore', score), ('HudTime', hudtime), ('Full', full_mem)])
    d.indic('Picture', 'picture', '', picture, 4)
    d.indic('Pieces', PIECES, '[]', pieces2, 6)
    d.indic('Memory out', RMEM, RMEM_V, mem2, 8)
    d.err_out(err3)
    d.write()


# ================================================================== Audio
def sound_bank_load():
    d = Doc('Sound_Bank_Load.vi', 'Loads all sound effects once (order = priority: ' + ', '.join(SND_PRIO) + ', then the music): '
            'Resources\\Sounds\\<name>.wav, first channel as samples (-1..1).')
    e = d.err_in()
    files = d.const('array{string}', '[' + ','.join(k + '.wav' for k in SND_PRIO + ['music']) + ']', 'Files')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    fn = d.tunnel_in(1, files, 'index')
    er, rr = shiftreg(d, lp, e)
    rp = d.call('Resource_Path.vi', [('File name', fn), ('Subfolder', d.const('string', 'Sounds')), ('error in', er)], ['Path', 'error out'])
    rd = d.call('Sound File Read Simple.vi', [('path', rp['Path']), ('error in (no error)', rp['error out'])], ['-path out', 'data', '-offset', 'error out'])
    y = d.node('Get Waveform Components', [('waveform', d.idx(rd['data'], d.i32c(0)))], ['Y'], extra='fields="Y"')['Y']
    bank = d.tunnel_out(1, d.bun(d.const('cluster{array{double}.Y}', '[[]]'), [('Y', y)]), 'index')
    d.end()
    d.indic('Bank', BANK, '[]', bank, 4)
    d.err_out(close_reg(d, rr, rd['error out']))
    d.write()


def sound_mix():
    d = Doc('Sound_Mix.vi', f'One audio block ({SND_CHUNK} samples): picks the most important effect of the sound bits; it replaces the '
            'running effect when that one has ended or is not more important. Returns the next samples of the running effect, filled '
            f'with silence, plus the music (bank entry {MUSIC_IDX}, volume {MUSIC_VOL}) from Music Position, looping seamlessly.')
    snd = d.ctrl('Sounds', 'int32', '0', 0)
    bank = d.ctrl('Bank', BANK, '[]', 5)
    cur = d.ctrl('Current', 'array{double}', '[]', 7)
    pos = d.ctrl('Position', 'int32', '0', 9)
    prio = d.ctrl('Priority', 'int32', '99', 1)
    m_on = d.ctrl('Music on', 'bool', 'false', 2, 'recommended')
    m_pos = d.ctrl('Music Position', 'int32', '0', 3, 'recommended')
    e = d.err_in()
    c = d.i32c
    bools = [d.node('Not Equal To 0?', [('x', d.and_(snd, c(SND[k])))], ['x != 0?'])['x != 0?'] for k in SND_PRIO]
    arr = d.node('Build Array', [('element', b) for b in bools], ['appended array'])['appended array']
    ix = d.node('Search 1D Array', [('1D array', arr), ('element', d.const('bool', 'true')), ('start index (0)', '')], ['index of element'])['index of element']
    n = size(d, cur)
    finished = d.not_(d.lt(pos, n))
    take = d.and_(d.not_(d.lt(ix, c(0))), d.or_(finished, d.not_(d.gt(ix, prio))))
    new_y, = d.unb(d.idx(bank, ix), ['Y'])
    cur2 = d.sel(take, new_y, cur)
    pos2 = d.sel(take, c(0), pos)
    prio2 = d.sel(take, ix, d.sel(finished, c(99), prio))
    ch = c(SND_CHUNK)
    part = d.node('Array Subset', [('array', cur2), ('index', pos2), ('length', ch)], ['subarray'])['subarray']
    pad = d.node('Initialize Array', [('element', d.const('double', '0')), ('dimension size', d.sub(ch, size(d, part)))], ['initialized array'])['initialized array']
    block = d.node('Build Array', [('array', part), ('array', pad)], ['appended array'], extra='concat="true"')['appended array']
    my, = d.unb(d.idx(bank, c(MUSIC_IDX)), ['Y'])
    mlen = size(d, my)
    on = d.and_(m_on, d.gt(mlen, c(0)))
    p1 = d.node('Array Subset', [('array', my), ('index', m_pos), ('length', ch)], ['subarray'])['subarray']
    p2 = d.node('Array Subset', [('array', my), ('index', c(0)), ('length', d.sub(ch, size(d, p1)))], ['subarray'])['subarray']
    mb = d.node('Build Array', [('array', p1), ('array', p2)], ['appended array'], extra='concat="true"')['appended array']
    mpad = d.node('Initialize Array', [('element', d.const('double', '0')), ('dimension size', ch)], ['initialized array'])['initialized array']
    mb2 = d.node('Build Array', [('array', mb), ('array', mpad)], ['appended array'], extra='concat="true"')['appended array']
    mb3 = d.node('Array Subset', [('array', mb2), ('index', c(0)), ('length', ch)], ['subarray'])['subarray']
    gain = d.sel(on, d.const('double', repr(MUSIC_VOL)), d.const('double', '0'))
    mix = d.add2(block, d.mul(mb3, gain))
    mpos_next = d.qr(d.add2(m_pos, ch), d.sel(on, mlen, c(1)))[0]
    d.indic('Block', 'array{double}', '[]', mix, 4)
    d.indic('Current out', 'array{double}', '[]', cur2, 6)
    d.indic('Position out', 'int32', '0', d.add2(pos2, ch), 8)
    d.indic('Priority out', 'int32', '0', prio2, 10)
    d.indic('Music Position out', 'int32', '0', d.sel(on, mpos_next, m_pos), 13)
    d.err_out(e)
    d.write()


# ================================================================== App
def status(d, err):
    return d.unb(err, ['status'])[0]


def app_init():
    d = Doc('App_Init.vi', 'Start of Main: creates the key queue (UI to engine), the notifier (game state for the picture loop) and the sound '
            'queue (sound bits for the audio loop) and returns them as Channels.')
    e = d.err_in()
    q = d.node('Obtain Queue', [('element data type', d.const(KEY, '0', 'Key type')), ('error in (no error)', e)], ['queue out', '-created new?', 'error out'])
    nt = d.node('Obtain Notifier', [('notification data type', d.const(STATE, STATE_V, 'State type')), ('error in (no error)', q['error out'])],
                ['notifier out', '-created new?', 'error out'])
    qs = d.node('Obtain Queue', [('element data type', d.const('int32', '0', 'Sound type')), ('error in (no error)', nt['error out'])],
                ['queue out', '-created new?', 'error out'])
    k = d.bun(d.const(CHANNELS, '[,,]'), [('Keys', q['queue out']), ('Frames', nt['notifier out']), ('Sounds', qs['queue out'])])
    d.indic('Channels', CHANNELS, '[,,]', k, 4)
    d.err_out(qs['error out'])
    d.write()


def app_close():
    d = Doc('App_Close.vi', 'End of Main (after the engine and picture loops): releases the queues and the notifier; the audio loop ends '
            'because its queue is gone. Errors of the loops come in through error in and are kept.')
    k = d.ctrl('Channels', CHANNELS, '[,,]', 0)
    e = d.err_in()
    q, nt, qs = d.unb(k, ['Keys', 'Frames', 'Sounds'])
    r1 = d.node('Release Queue', [('queue', q), ('error in (no error)', e)], ['-queue name', '-remaining elements', 'error out'])
    r2 = d.node('Release Notifier', [('notifier', nt), ('error in (no error)', r1['error out'])], ['-notifier name', '-last notification', 'error out'])
    r3 = d.node('Release Queue', [('queue', qs), ('error in (no error)', r2['error out'])], ['-queue name', '-remaining elements', 'error out'])
    d.err_out(r3['error out'])
    d.write()


def window_setup():
    d = Doc('Window_Setup.vi', f'Sets up the window of Main: picture "Screen" at the top left with a fixed drawing area of {W} x {H}, never '
            'erasing; all other controls are moved to the right outside the visible area; the panel is sized to the screen.')
    vi = d.ctrl('VI', 'ref{LV.VI}', '', 0)
    e = d.err_in()
    org = d.node('Property Node', [('reference', vi), ('error in (no error)', e),
                                   ('Front Panel Window\\3AOrigin', d.const('cluster{int16.Horizontal,int16.Vertical}', '[0,0]', 'Origin'))],
                 ['-reference out', 'error out'], extra='fields="write+Front Panel Window\\3AOrigin" type="{LV.VI}"')
    fp = d.node('Property Node', [('reference', vi), ('error in (no error)', org['error out'])], ['Front Panel', '-reference out', 'error out'],
                extra='fields="read+Front Panel" type="{LV.VI}"')
    cs = d.node('Property Node', [('reference', fp['Front Panel']), ('error in (no error)', fp['error out'])],
                ['Controls[]', '-reference out', 'error out'], extra='fields="read+Controls[]" type="{LV.Panel}"')
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    k = f'{lp}i.v'
    c = d.tunnel_in(1, cs['Controls[]'], 'index')
    er, rr = shiftreg(d, lp, cs['error out'])
    lab = d.node('Property Node', [('reference', c), ('error in (no error)', er)], ['Label', '-reference out', 'error out'],
                 extra='fields="read+Label" type="{LV.Control}"')
    txt = d.node('Property Node', [('reference', lab['Label']), ('error in (no error)', lab['error out'])], ['Text', '-reference out', 'error out'],
                 extra='fields="read+Text" type="{LV.Text}"')

    def f_screen(a):
        ref, err, _ = a
        pic = d.node('To More Specific Class', [('reference', ref), ('error in', err), ('target class', d.const('ref{LV.Picture}', '', 'Picture class'))],
                     ['specific class reference', 'error out'])
        w = d.node('Property Node', [('reference', pic['specific class reference']), ('error in (no error)', pic['error out']),
                                     ('Position', d.const('cluster{int32.Left,int32.Top}', '[0,0]', 'Top left')),
                                     ('Draw Area Size', d.const('cluster{int32.Width,int32.Height}', f'[{W},{H}]', 'Screen size')),
                                     ('Erase First', d.const('uint8', '0', 'never erase'))],
                   ['-reference out', 'error out'], extra='fields="write+Position,write+Draw Area Size,write+Erase First" type="{LV.Picture}"')
        return [w['error out']]

    def f_rest(a):
        ref, err, kk = a
        pos = d.bun(d.const('cluster{int32.Left,int32.Top}', f'[{W + 40},40]', 'right of the screen'), [('Top', d.add2(d.i32c(40), d.mul(kk, d.i32c(50))))])
        w = d.node('Property Node', [('reference', ref), ('error in (no error)', err), ('Position', pos)], ['-reference out', 'error out'],
                   extra='fields="write+Position" type="{LV.Control}"')
        return [w['error out']]

    er2, = d.case(txt['Text'], [c, txt['error out'], k], [('&quot;Screen&quot;', f_screen), ('Default', f_rest)], 1)
    d.end()
    er3 = close_reg(d, rr, er2)
    pb = d.node('Property Node', [('reference', vi), ('error in (no error)', er3)], ['Front Panel Window\\3APanel Bounds', '-reference out', 'error out'],
                extra='fields="read+Front Panel Window\\3APanel Bounds" type="{LV.VI}"')
    left, top = d.unb(pb['Front Panel Window\\3APanel Bounds'], ['left', 'top'])
    nb = d.bun(pb['Front Panel Window\\3APanel Bounds'], [('right', d.add2(left, d.const('int16', str(W)))), ('bottom', d.add2(top, d.const('int16', str(H))))])
    wb = d.node('Property Node', [('reference', vi), ('error in (no error)', pb['error out']), ('Front Panel Window\\3APanel Bounds', nb)],
                ['-reference out', 'error out'], extra='fields="write+Front Panel Window\\3APanel Bounds" type="{LV.VI}"')
    d.err_out(wb['error out'])
    d.write()


def key_send():
    d = Doc('Key_Send.vi', 'Translates a key (ScanCode = physical key, independent of the keyboard layout) into a game key and puts it into '
            'the key queue. Pressed: arrows, Space = Jump, Enter/N = Start, Esc/P = Pause; released: arrows = ReleaseL/ReleaseR/ReleaseV. '
            'The Stop button sends Quit. Quit out: the game ends (Stop, or Esc on the title screen - read from the last game state).')
    k = d.ctrl('Channels', CHANNELS, '[,,]', 0)
    sc = d.ctrl('ScanCode', 'int32', '-1', 5)
    up = d.ctrl('Released', 'bool', 'false', 7, 'recommended')
    quit_ = d.ctrl('Quit', 'bool', 'false', 9, 'recommended')
    e = d.err_in()

    def lookup(tbl, name):
        codes = d.const('array{int32}', '[' + ','.join(str(code) for code, _ in tbl) + ']', f'ScanCodes {name}')
        keys = d.const(f'array{{{KEY}}}', '[' + ','.join(str(IN[v]) for _, v in tbl) + ']', f'Keys {name}')
        ix = d.node('Search 1D Array', [('1D array', codes), ('element', sc), ('start index (0)', '')], ['index of element'])['index of element']
        return d.idx(keys, ix)

    t = d.sel(up, lookup(KEYS_UP, 'released'), lookup(KEYS_DOWN, 'pressed'))
    t = d.sel(quit_, d.const(KEY, str(IN['Quit'])), t)
    q, nt = d.unb(k, ['Keys', 'Frames'])
    # letzter Spielzustand (ohne zu warten); kam seit dem letzten Aufruf keiner, gilt er nicht als Titel
    gs = d.node('Wait on Notification', [('notifier', nt), ('timeout in ms (-1)', d.const('int32', '0', 'do not wait')), ('error in (no error)', e)],
                ['-notifier out', 'notification', 'timed out?', 'error out'])
    phase, = d.unb(gs['notification'], ['Phase'])
    enq = d.node('Enqueue Element', [('queue', q), ('element', t), ('error in (no error)', gs['error out'])], ['-queue out', '-timed out?', 'error out'])
    title = d.and_(d.eq(phase, d.i32c(PH['Title'])), d.not_(gs['timed out?']))
    leave = d.or_(d.eq(t, d.const(KEY, str(IN['Quit']))), d.and_(d.eq(t, d.const(KEY, str(IN['Pause']))), title))
    d.indic('Quit out', 'bool', 'false', d.or_(leave, status(d, enq['error out'])), 4)
    d.err_out(enq['error out'])
    d.write()


def engine_tick():
    d = Doc('Engine_Tick.vi', 'One game tick: takes at most one key from the queue, runs Game_Step, sends the sound bits to the audio loop '
            'and the new state to the picture loop. Stop on Quit or on an error.')
    k = d.ctrl('Channels', CHANNELS, '[,,]', 0)
    st = d.ctrl('State', STATE, STATE_V, 5)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 7)
    e = d.err_in()
    q, nt, qs = d.unb(k, ['Keys', 'Frames', 'Sounds'])
    dq = d.node('Dequeue Element', [('queue', q), ('timeout in ms (-1)', d.const('int32', '0', 'do not wait')), ('error in (no error)', e)],
                ['-queue out', 'element', '-timed out?', 'error out'])
    gs = d.call('Game_Step.vi', [('State', st), ('Key', dq['element']), ('Rooms', rooms), ('error in', dq['error out'])], ['State out', 'error out'])
    snd, quit_ = d.unb(gs['State out'], ['Sound', 'Quit'])
    d.node('Enqueue Element', [('queue', qs), ('element', snd)], ['-queue out', '-timed out?', '-error out'])
    sn = d.node('Send Notification', [('notifier', nt), ('notification', gs['State out']), ('error in (no error)', gs['error out'])], ['-notifier out', 'error out'])
    d.indic('State out', STATE, STATE_V, gs['State out'], 4)
    d.indic('Stop', 'bool', 'false', d.or_(quit_, status(d, sn['error out'])), 6)
    d.err_out(sn['error out'])
    d.write()


def frame_pace():
    d = Doc('Frame_Pace.vi', f'Paces the game loop at exactly {FPS} ticks per second (the screen refresh rate): waits until Start + '
            f'(Count + 1) * 1000 / {FPS} ms. Count <= 0 starts the clock now; more than 50 ms behind (a hitch) restarts it, so the game never races '
            'to catch up.')
    start = d.ctrl('Start ms', 'uint32', '0', 0)
    cnt = d.ctrl('Count', 'int32', '0', 1)
    e = d.err_in()
    c = d.i32c
    now = d.node('Tick Count (ms)', [], ['millisecond timer value'])['millisecond timer value']
    first = d.lt(cnt, c(1))
    st = d.sel(first, now, start)
    n1 = d.inc(cnt)
    off = d.qr(d.mul(n1, c(1000)), c(FPS))[1]
    w = d.add2(d.i32(d.sub(st, now)), off)
    behind = d.lt(w, c(-50))
    wt = d.sel(d.lt(w, c(0)), c(0), w)
    d.node('Wait (ms)', [('milliseconds to wait', wt)], ['-millisecond timer value'])
    d.indic('Start out', 'uint32', '0', d.sel(behind, now, st), 4)
    d.indic('Count out', 'int32', '0', d.sel(behind, c(0), n1), 6)
    d.err_out(e)
    d.write()

def render_frame():
    d = Doc('Render_Frame.vi', 'One frame: waits (at most 200 ms) for the next game state and draws it with Frame_Draw. Without a new state '
            'nothing is drawn and Memory stays. FPS from the time since the last frame. Stop on Quit or on an error.')
    k = d.ctrl('Channels', CHANNELS, '[,,]', 0)
    spr = d.ctrl('Sprites', SPRITES_USED, '[]', 5)
    hud = d.ctrl('Hud', IMG, IMG_V, 7)
    title = d.ctrl('Title', IMG, IMG_V, 9)
    mem = d.ctrl('Memory', RMEM, RMEM_V, 1)
    last = d.ctrl('Last ms', 'uint32', '0', 2, 'recommended')
    e = d.err_in()
    nt, = d.unb(k, ['Frames'])
    wn = d.node('Wait on Notification', [('notifier', nt), ('timeout in ms (-1)', d.const('int32', '200', 'Timeout')), ('error in (no error)', e)],
                ['-notifier out', 'notification', 'timed out?', 'error out'])
    st = wn['notification']
    pic, mem2, err = d.case(wn['timed out?'], [st, spr, hud, title, mem, wn['error out']], [
        ('False', lambda i: (lambda r: [r['Picture'], r['Memory out'], r['error out']])(
            d.call('Frame_Draw.vi', [('State', i[0]), ('Sprites', i[1]), ('Hud', i[2]), ('Title', i[3]), ('Memory', i[4]), ('error in', i[5])],
                   ['Picture', '-Pieces', 'Memory out', 'error out']))),
        ('True', lambda i: [d.call('Draw Flattened Pixmap.vi', [('image data', d.const(IMG, IMG_V, 'No pixels')), ('picture', '')], ['new picture'])['new picture'], i[4], i[5]]),
    ], 3)
    quit_, = d.unb(st, ['Quit'])
    now = d.node('Tick Count (ms)', [], ['millisecond timer value'])['millisecond timer value']
    fps = d.node('Divide', [('x', d.const('double', '1000')), ('y', d.sub(now, last))], ['x/y'])['x/y']
    d.indic('Picture', 'picture', '', pic, 4)
    d.indic('Memory out', RMEM, RMEM_V, mem2, 6)
    d.indic('FPS', 'double', '0', fps, 8)
    d.indic('Now ms', 'uint32', '0', now, 10)
    d.indic('Stop', 'bool', 'false', d.or_(d.and_(quit_, d.not_(wn['timed out?'])), status(d, err)), 13)
    d.err_out(err)
    d.write()


def audio_start():
    d = Doc('Audio_Start.vi', f'Loads all sounds (Sound_Bank_Load) and opens a continuous sound channel ({SND_RATE} Hz, mono, 16 bit, buffer '
            f'{SND_BUFFER} samples). Also returns the empty mixer state.')
    e = d.err_in()
    bl = d.call('Sound_Bank_Load.vi', [('error in', e)], ['Bank', 'error out'])
    cf = d.call('Sound Output Configure.vi', [('error in (no error)', bl['error out']), ('sample mode', d.const('int32', '1', 'continuous')),
                                              ('number of samples/ch', d.const('int32', str(SND_BUFFER), 'Buffer')),
                                              ('sound format', d.const('cluster{double.sample rate (S/s),int32.number of channels,int32.bits per sample}',
                                                                       f'[{SND_RATE},1,16]', 'Sound format'))], ['error out', 'task ID'])
    d.indic('Bank', BANK, '[]', bl['Bank'], 4)
    d.indic('Task ID', 'uint32', '0', cf['task ID'], 6)
    d.indic('Mixer', MIXER, MIXER_V, d.const(MIXER, MIXER_V, 'Empty mixer'), 8)
    d.err_out(cf['error out'])
    d.write()


def audio_block():
    d = Doc('Audio_Block.vi', f'One audio block: collects all sound bits from the sound queue, mixes {SND_CHUNK} samples with Sound_Mix and '
            'writes them to the sound channel. Writing waits for room in the buffer - this paces the audio loop. Stop on an error '
            '(queue released = end of the game).')
    k = d.ctrl('Channels', CHANNELS, '[,,]', 0)
    bank = d.ctrl('Bank', BANK, '[]', 5)
    task = d.ctrl('Task ID', 'uint32', '0', 7)
    mx = d.ctrl('Mixer', MIXER, MIXER_V, 9)
    on = d.ctrl('Sound', 'bool', 'true', 1, 'recommended')
    e = d.err_in()
    qs, = d.unb(k, ['Sounds'])
    fl = d.node('Flush Queue', [('queue', qs), ('error in (no error)', e)], ['-queue out', 'remaining elements', 'error out'])
    none = d.i32c(0)
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    bit = d.tunnel_in(1, fl['remaining elements'], 'index')
    acc_l, acc_r = shiftreg(d, lp, none)
    acc2 = d.or_(acc_l, bit)
    d.end()
    bits = close_reg(d, acc_r, acc2)
    snd = d.sel(on, bits, d.i32c(0))
    cur, pos, prio, mus, mpos = d.unb(mx, ['Current', 'Position', 'Priority', 'Music', 'MusicPos'])
    got = d.gt(size(d, fl['remaining elements']), d.i32c(0))
    mus_bit = d.node('Not Equal To 0?', [('x', d.and_(bits, d.i32c(SND['music'])))], ['x != 0?'])['x != 0?']
    mus2 = d.and_(on, d.sel(got, mus_bit, mus))
    sm = d.call('Sound_Mix.vi', [('Sounds', snd), ('Bank', bank), ('Current', cur), ('Position', pos), ('Priority', prio), ('Music on', mus2),
                                 ('Music Position', mpos), ('error in', fl['error out'])],
                ['Block', 'Current out', 'Position out', 'Priority out', 'Music Position out', 'error out'])
    wf = d.node('Build Waveform', [('dt', d.const('double', repr(1.0 / SND_RATE), 'dt')), ('Y', sm['Block'])], ['output waveform'], extra='fields="dt,Y"')['output waveform']
    wr = d.call('Sound Output Write (DBL Single).vi', [('task ID', task), ('error in (no error)', sm['error out']), ('data', wf)], ['error out', '-task ID out'])
    mx2 = d.bun(mx, [('Current', sm['Current out']), ('Position', sm['Position out']), ('Priority', sm['Priority out']), ('Music', mus2),
                     ('MusicPos', sm['Music Position out'])])
    d.indic('Mixer out', MIXER, MIXER_V, mx2, 4)
    d.indic('Stop', 'bool', 'false', status(d, wr['error out']), 6)
    d.err_out(wr['error out'])
    d.write()


def audio_close():
    d = Doc('Audio_Close.vi', 'Closes the sound channel after the audio loop has ended (error in = error of the audio loop; the error of the '
            'released sound queue is normal there).')
    task = d.ctrl('Task ID', 'uint32', '0', 0)
    e = d.err_in()
    clr = d.call('Sound Output Clear.vi', [('error in (no error)', e), ('task ID', task)], ['error out'])
    d.err_out(clr['error out'])
    d.write()


ENGINE = (player_move, enemies_init, room_change, items_collect, door_open, enemies_step, hit_check, respawn, level_setup, game_new,
          keys_apply, game_play, demo_input, highscore_load, highscore_save, highscore_insert, game_start, game_step)
RENDER = (room_images, light_update, grid_block, room_draw, enemies_draw, glyphs_draw, hud_draw, overlay_draw, piece_compose, scene_draw, frame_draw)
AUDIO = (sound_bank_load, sound_mix)
APP = (app_init, app_close, window_setup, key_send, engine_tick, frame_pace, render_frame, audio_start, audio_block, audio_close)
ALL = {f.__name__: f for f in ENGINE + RENDER + AUDIO + APP}


def contract():
    E = {"name": "error in", "type": "@Error", "conIdx": 11, "connection": "required"}
    EO = {"name": "error out", "type": "@Error", "conIdx": 15, "connection": "recommended"}

    def i(n, t, k, conn='required'): return {"name": n, "type": t, "conIdx": k, "connection": conn}
    def o(n, t, k): return {"name": n, "type": t, "conIdx": k, "connection": "recommended"}

    LV, RE, EN, AU, AP = 'Source\\Level\\', 'Source\\Render\\', 'Source\\Engine\\', 'Source\\Audio\\', 'Source\\App\\'
    S, RO = '@State', '@Rooms'
    vis = [
        (LV, 'Resource_Path', [], [i('File name', 'string', 0), i('Subfolder', 'string', 5), E], [o('Path', 'path', 4), EO]),
        (LV, 'Room_Load', [LV + 'Resource_Path.vi'], [i('Room ID', 'string', 0), E], [o('Tiles', '@Tiles', 4), EO]),
        (LV, 'World_Load', [LV + 'Resource_Path.vi', LV + 'Room_Load.vi'], [E], [o('Rooms', RO, 4), o('Grid', 'array.2{string}', 6), EO]),
        (LV, 'Tile_At', [], [i('Tiles', '@Tiles', 0), i('X', 'int32', 5), i('Y', 'int32', 7), E], [o('Tile', 'uint8', 4), EO]),
        (LV, 'Tile_Read', [], [i('Tiles', '@Tiles', 0), i('X', 'int32', 5), i('Y', 'int32', 7), E], [o('Tile', 'uint8', 4), EO]),
        (RE, 'Image_Load', [LV + 'Resource_Path.vi'], [i('File name', 'string', 0), E], [o('Image', '@ImageData', 4), EO]),
        (RE, 'SpriteAtlas_Load', [LV + 'Resource_Path.vi'], [E], [o('Sprites', '@Sprites', 4), EO]),
        (RE, 'Sprite_Draw', [], [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('Index', 'int32', 7), i('Position', '@Position', 9), E],
         [o('Picture out', 'picture', 4), EO]),
        (RE, 'Image_Draw', [], [i('Picture', 'picture', 0), i('Image', '@ImageData', 5), i('Position', '@Position', 7), E], [o('Picture out', 'picture', 4), EO]),
        (RE, 'Tile_Cut', [], [i('Image', '@ImageData', 0), i('Column', 'int32', 5), i('Row', 'int32', 7), i('Offset Y', 'int32', 9), E],
         [o('Tile', '@ImageData', 4), EO]),
        (RE, 'Block_Cut', [], [i('Image', '@ImageData', 0), i('Column', 'int32', 5), i('Row', 'int32', 7), i('Offset Y', 'int32', 9),
                               i('Columns', 'int32', 1), i('Rows', 'int32', 2), E], [o('Block', '@ImageData', 4), EO]),
        # Engine
        (EN, 'Player_Move', [LV + 'Tile_Read.vi'], [i('State', S, 0), i('Jump', 'bool', 5, 'recommended'), E], [o('State out', S, 4), EO]),
        (EN, 'Enemies_Init', [], [i('Tiles', '@Tiles', 0), E], [o('Enemies', '@Enemies', 4), EO]),
        (EN, 'Room_Change', [EN + 'Enemies_Init.vi'], [i('State', S, 0), E], [o('State out', S, 4), o('Changed', 'bool', 6), EO]),
        (EN, 'Items_Collect', [], [i('State', S, 0), E], [o('State out', S, 4), EO]),
        (EN, 'Door_Open', [], [i('State', S, 0), E], [o('State out', S, 4), o('Opened', 'bool', 6), EO]),
        (EN, 'Enemies_Step', [LV + 'Tile_Read.vi'], [i('State', S, 0), E], [o('State out', S, 4), EO]),
        (EN, 'Hit_Check', [], [i('State', S, 0), E], [o('Hit', 'bool', 4), EO]),
        (EN, 'Respawn', [EN + 'Enemies_Init.vi'], [i('State', S, 0), E], [o('State out', S, 4), EO]),
        (EN, 'Level_Setup', [EN + 'Enemies_Init.vi'], [i('State', S, 0), i('Rooms', RO, 5), i('Level', 'int32', 7), E], [o('State out', S, 4), EO]),
        (EN, 'Game_New', [EN + 'Level_Setup.vi'], [i('State', S, 0), i('Rooms', RO, 5), i('Demo', 'bool', 7, 'recommended'), E], [o('State out', S, 4), EO]),
        (EN, 'Keys_Apply', [], [i('State', S, 0), i('Key', 'uint16', 5, 'recommended'), E], [o('State out', S, 4), EO]),
        (EN, 'Game_Play', [EN + n + '.vi' for n in ('Player_Move', 'Items_Collect', 'Door_Open', 'Enemies_Step', 'Hit_Check', 'Room_Change')],
         [i('State', S, 0), i('Jump', 'bool', 5, 'recommended'), E], [o('State out', S, 4), o('Hit', 'bool', 6), o('Died', 'bool', 8), EO]),
        (EN, 'Demo_Input', [], [i('Step', 'int32', 0), E], [o('Key', 'uint16', 4), EO]),
        (EN, 'Highscore_Load', [LV + 'Resource_Path.vi'], [E], [o('Table', '@Highscores', 4), EO]),
        (EN, 'Highscore_Save', [LV + 'Resource_Path.vi'], [i('Table', '@Highscores', 0), E], [EO]),
        (EN, 'Highscore_Insert', [], [i('Table', '@Highscores', 0), i('Score', 'int32', 5), i('Name', 'string', 7), E], [o('Table out', '@Highscores', 4), EO]),
        (EN, 'Game_Start', [LV + 'World_Load.vi', EN + 'Highscore_Load.vi', EN + 'Level_Setup.vi'], [E], [o('State', S, 4), o('Rooms', RO, 6), EO]),
        (EN, 'Game_Step', [EN + n + '.vi' for n in ('Game_New', 'Demo_Input', 'Keys_Apply', 'Game_Play', 'Respawn', 'Level_Setup', 'Highscore_Insert',
                                                     'Highscore_Save')],
         [i('State', S, 0), i('Key', 'uint16', 5, 'recommended'), i('Rooms', RO, 7), E], [o('State out', S, 4), EO]),
        # Render
        (RE, 'Room_Images', [RE + 'Image_Load.vi'], [i('Room ID', 'string', 0), i('Theme', 'int32', 5), E],
         [o('Lit', '@Grid', 4), o('Dim', '@Grid', 6), o('Dark', '@Grid', 8), o('Template', '@ImageData', 10), EO]),
        (RE, 'Light_Update', [], [i('Comp', '@Grid', 0), i('Lit', '@Grid', 5), i('Dim', '@Grid', 7), i('Dark', '@Grid', 9), i('Old CX', 'int32', 1),
                                  i('Old CY', 'int32', 2), i('CX', 'int32', 3), i('CY', 'int32', 13), E], [o('Comp out', '@Grid', 4), o('Rect', '@Rect', 6), EO]),
        (RE, 'Grid_Block', [], [i('Grid', '@Grid', 0), i('Template', '@ImageData', 5), i('Rect', '@Rect', 7), E], [o('Block', '@ImageData', 4), EO]),
        (RE, 'Room_Draw', [RE + 'Sprite_Draw.vi'], [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('Tiles', '@Tiles', 7), i('Region', '@Rect', 9),
                                                    i('FloorPhase', 'int32', 1), i('View', '@View', 2), E], [o('Picture out', 'picture', 4), EO]),
        (RE, 'Enemies_Draw', [RE + 'Sprite_Draw.vi'], [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('Enemies', '@Enemies', 7),
                                                       i('Tick', 'uint32', 9), i('View', '@View', 1), E], [o('Picture out', 'picture', 4), EO]),
        (RE, 'Glyphs_Draw', [RE + 'Sprite_Draw.vi'], [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('Text', 'string', 7), i('Position', '@Position', 9), E],
         [o('Picture out', 'picture', 4), EO]),
        (RE, 'Hud_Draw', [RE + 'Sprite_Draw.vi', RE + 'Glyphs_Draw.vi'], [i('Sprites', '@Sprites', 0), i('Hud', '@ImageData', 5), i('State', S, 7), E],
         [o('Piece', '@ImageData', 4), EO]),
        (RE, 'Overlay_Draw', [RE + 'Sprite_Draw.vi', RE + 'Glyphs_Draw.vi'], [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('State', S, 7),
                                                                              i('Clip', '@Rect', 9), E], [o('Picture out', 'picture', 4), EO]),
        (RE, 'Piece_Compose', [RE + n + '.vi' for n in ('Grid_Block', 'Room_Draw', 'Enemies_Draw', 'Sprite_Draw', 'Overlay_Draw')],
         [i('Grid', '@Grid', 0), i('Template', '@ImageData', 5), i('Rect', '@Rect', 7), i('Sprites', '@Sprites', 9), i('State', S, 1), i('View', '@View', 2), E],
         [o('Piece', '@ImageData', 4), EO]),
        (RE, 'Scene_Draw', [RE + n + '.vi' for n in ('Grid_Block', 'Room_Draw', 'Enemies_Draw', 'Sprite_Draw', 'Glyphs_Draw', 'Overlay_Draw')],
         [i('Grid', '@Grid', 0), i('Template', '@ImageData', 5), i('Sprites', '@Sprites', 7), i('State', S, 9), i('View', '@View', 1),
          i('Hud', '@ImageData', 2), i('Title', '@ImageData', 3), E],
         [o('Picture', 'picture', 4), EO]),
        (RE, 'Frame_Draw', [RE + n + '.vi' for n in ('Room_Images', 'Light_Update', 'Scene_Draw')],
         [i('State', S, 0), i('Sprites', '@Sprites', 5), i('Hud', '@ImageData', 7), i('Title', '@ImageData', 9), i('Memory', '@RenderMemory', 1), E],
         [o('Picture', 'picture', 4), o('Pieces', '@Pieces', 6), o('Memory out', '@RenderMemory', 8), EO]),
        # Audio
        (AU, 'Sound_Bank_Load', [LV + 'Resource_Path.vi'], [E], [o('Bank', '@Bank', 4), EO]),
        (AU, 'Sound_Mix', [], [i('Sounds', 'int32', 0), i('Bank', '@Bank', 5), i('Current', 'array{double}', 7), i('Position', 'int32', 9),
                               i('Priority', 'int32', 1), i('Music on', 'bool', 2, 'recommended'), i('Music Position', 'int32', 3, 'recommended'), E],
         [o('Block', 'array{double}', 4), o('Current out', 'array{double}', 6), o('Position out', 'int32', 8), o('Priority out', 'int32', 10),
          o('Music Position out', 'int32', 13), EO]),
        # App
        (AP, 'App_Init', [], [E], [o('Channels', '@Channels', 4), EO]),
        (AP, 'App_Close', [], [i('Channels', '@Channels', 0), E], [EO]),
        (AP, 'Window_Setup', [], [i('VI', 'ref{LV.VI}', 0), E], [EO]),
        (AP, 'Key_Send', [], [i('Channels', '@Channels', 0), i('ScanCode', 'int32', 5), i('Released', 'bool', 7, 'recommended'), i('Quit', 'bool', 9, 'recommended'), E],
         [o('Quit out', 'bool', 4), EO]),
        (AP, 'Engine_Tick', [EN + 'Game_Step.vi'], [i('Channels', '@Channels', 0), i('State', S, 5), i('Rooms', RO, 7), E],
         [o('State out', S, 4), o('Stop', 'bool', 6), EO]),
        (AP, 'Frame_Pace', [], [i('Start ms', 'uint32', 0), i('Count', 'int32', 1), E], [o('Start out', 'uint32', 4), o('Count out', 'int32', 6), EO]),
        (AP, 'Render_Frame', [RE + 'Frame_Draw.vi'], [i('Channels', '@Channels', 0), i('Sprites', '@Sprites', 5), i('Hud', '@ImageData', 7),
                                                     i('Title', '@ImageData', 9), i('Memory', '@RenderMemory', 1), i('Last ms', 'uint32', 2, 'recommended'), E],
         [o('Picture', 'picture', 4), o('Memory out', '@RenderMemory', 6), o('FPS', 'double', 8), o('Now ms', 'uint32', 10), o('Stop', 'bool', 13), EO]),
        (AP, 'Audio_Start', [AU + 'Sound_Bank_Load.vi'], [E], [o('Bank', '@Bank', 4), o('Task ID', 'uint32', 6), o('Mixer', '@Mixer', 8), EO]),
        (AP, 'Audio_Block', [AU + 'Sound_Mix.vi'], [i('Channels', '@Channels', 0), i('Bank', '@Bank', 5), i('Task ID', 'uint32', 7), i('Mixer', '@Mixer', 9),
                                                   i('Sound', 'bool', 1, 'recommended'), E], [o('Mixer out', '@Mixer', 4), o('Stop', 'bool', 6), EO]),
        (AP, 'Audio_Close', [], [i('Task ID', 'uint32', 0), E], [EO]),
    ]
    data = {
        "application": "Gold Hunter",
        "root": "..",
        "project": "GoldHunter.lvproj",
        "panePattern": 4833,
        "types": {"Error": ERR, "Tiles": TILES, "Position": POS, "ImageData": IMG, "Sprites": SPRITES, "Rooms": ROOMS, "State": STATE,
                  "Enemies": ENEMIES, "Highscores": HSTAB, "Grid": GRID, "Rect": RECT, "View": VIEW, "RenderMemory": RMEM, "Pieces": PIECES,
                  "Bank": BANK, "Mixer": MIXER, "Channels": CHANNELS},
        "vis": [{"path": f + n + '.vi', "builder": f.split('\\')[1].lower(), "purpose": n, "calls": cl, "inputs": ins, "outputs": outs}
                for f, n, cl, ins, outs in vis],
    }
    json.dump(data, open(os.path.join(HERE, 'build-contract.json'), 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('contract:', len(data['vis']), 'VIs')


if __name__ == '__main__':
    for name in (sys.argv[1:] or ALL):
        if name == 'contract':
            continue
        ALL[name]()
    contract()
