# Gold Hunter - Test-VIs (Tests\): Snapshot_Room speichert einen Raum als PNG, Test_Bench misst die Zeit je Bild.
# Aufruf: python gen_tests.py [funktion ...]
import sys
from gh_lib import *

SCREEN = f'[0,0,{W},{H}]'


def room_image_name(d, theme, rid, suffix=''):
    num = d.node('Number To Decimal String', [('number', theme), ('width (-)', '')], ['decimal integer string'])['decimal integer string']
    return d.node('Concatenate Strings', [('string', d.const('string', 'room_')), ('string', num), ('string', d.const('string', '_')),
                                          ('string', rid), ('string', d.const('string', suffix + '.png'))],
                  ['concatenated string'])['concatenated string']


def load_all(d, rid, theme, err):
    """Sprites, Kacheln, Raumbild und HUD laden; liefert (sprites, tiles, bg, hud, err)"""
    sa = d.call('SpriteAtlas_Load.vi', [('error in', err)], ['Sprites', 'error out'])
    rl = d.call('Room_Load.vi', [('Room ID', rid), ('error in', sa['error out'])], ['Tiles', 'error out'])
    bg = d.call('Image_Load.vi', [('File name', room_image_name(d, theme, rid)), ('error in', rl['error out'])], ['Image', 'error out'])
    hud = d.call('Image_Load.vi', [('File name', d.const('string', 'hud.png')), ('error in', bg['error out'])], ['Image', 'error out'])
    return sa['Sprites'], rl['Tiles'], bg['Image'], hud['Image'], hud['error out']


def frame(d, spr, tiles, bg, hud, err, sprites=True):
    """ein Bild: HUD, Raum, Objekte; liefert (picture, err, count)"""
    # das HUD liegt bei (0, 0) und beginnt das Bild; der Raum folgt darunter
    p1 = d.call('Draw Flattened Pixmap.vi', [('image data', hud), ('picture', '')], ['new picture'])['new picture']
    p2 = d.call('Image_Draw.vi', [('Picture', p1), ('Image', bg), ('Position', d.const(POS, f'[0,{HUD_H}]')),
                                  ('error in', err)], ['Picture out', 'error out'])
    if not sprites:
        return p2['Picture out'], p2['error out'], None
    p3 = d.call('Room_Draw.vi', [('Picture', p2['Picture out']), ('Sprites', spr), ('Tiles', tiles), ('error in', p2['error out'])],
                ['Picture out', 'Count', 'error out'])
    return p3['Picture out'], p3['error out'], p3['Count']


def to_pixmap(d, pic):
    return d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', d.i32c(24)), ('rect', d.const(RECT, SCREEN)), ('picture', pic)],
                  ['image data', '-new picture'])['image data']


def snapshot_room():
    d = Doc('Snapshot_Room.vi', 'Test: draws one room with LabVIEW (HUD, background of the colour theme, all objects at their start places) '
            f'and saves the {W} x {H} picture as Resources\\Preview\\<File name>. Count = number of sprites drawn.', 5000)
    rid = d.ctrl('Room ID', 'string', '005')
    theme = d.ctrl('Theme', 'int32', '0')
    fn = d.ctrl('File name', 'string', 'lv_room.png')
    e = d.err_in()
    spr, tiles, bg, hud, err = load_all(d, rid, theme, e)
    pic, err, count = frame(d, spr, tiles, bg, hud, err)
    rp = d.call('Resource_Path.vi', [('File name', fn), ('Subfolder', d.const('string', 'Preview')), ('error in', err)], ['Path', 'error out'])
    w = d.call('Write PNG File.vi', [('compression (default)', ''), ('error in (no error)', rp['error out']),
                                     ('image data', to_pixmap(d, pic)), ('path to PNG file', rp['Path'])], ['error out', '-path'])
    d.indic('Count', 'int32', '0', count)
    d.indic('error out', ERR, ERR_V, w['error out'])
    d.write()


def test_world():
    d = Doc('Test_World.vi', 'Test: loads the whole world with World_Load. Rooms = number of rooms, IDs = their IDs in reading order, '
            'Tile sum = sum of all tile values (changes whenever a room file changes).', 6000)
    e = d.err_in()
    wl = d.call('World_Load.vi', [('error in', e)], ['Rooms', '-Grid', 'error out'])
    zero = d.i32c(0)
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    room = d.tunnel_in(1, wl['Rooms'], 'index')
    s_l, s_r = shiftreg(d, lp, zero)
    rid, tiles = d.unb(room, ['ID', 'Tiles'])
    lp2 = d.begin('For Loop', 'count="" maxin="" maxout=""')
    line = d.tunnel_in(1, tiles, 'index')
    q_l, q_r = shiftreg(d, lp2, s_l)
    lp3 = d.begin('For Loop', 'count="" maxin="" maxout=""')
    t = d.tunnel_in(1, line, 'index')
    u_l, u_r = shiftreg(d, lp3, q_l)
    u2 = d.add2(u_l, d.i32(t))
    d.end()
    q2 = close_reg(d, u_r, u2)
    d.end()
    total = close_reg(d, q_r, q2)
    ids = d.tunnel_out(1, rid, 'index')
    d.end()
    d.indic('Rooms', 'int32', '0', d.node('Array Size', [('array', ids)], ['size(s)'])['size(s)'])
    d.indic('IDs', 'array{string}', '[]', ids)
    d.indic('Tile sum', 'int32', '0', close_reg(d, s_r, total))
    d.indic('error out', ERR, ERR_V, wl['error out'])
    d.write()


def test_bench():
    d = Doc('Test_Bench.vi', 'Measurement for one room: Count frames per stage, result in ms per frame. '
            'Images = HUD + room background as picture; Sprites = Images + all objects (Room_Draw); '
            'Full = Sprites + rasterising to one pixmap and drawing it (what the game does per frame). '
            'Load = time to load the three images of one room (lit, dim, dark) once.', 9700)
    rid = d.ctrl('Room ID', 'string', '305')
    theme = d.ctrl('Theme', 'int32', '0')
    n = d.ctrl('Count', 'int32', '30')
    e = d.err_in()
    spr, tiles, bg, hud, err0 = load_all(d, rid, theme, e)

    def tick(dep):
        """Zeitstempel, der erst nach dem Netz dep (int32) gelesen wird"""
        z = d.mul(dep, d.i32c(0))
        return d.node('Wait (ms)', [('milliseconds to wait', z)], ['millisecond timer value'])['millisecond timer value']

    def zero_after(t):
        return d.i32(d.mul(t, d.const('uint32', '0')))

    def stage(t_start, err, sprites, full):
        cnt = d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', d.add2(n, zero_after(t_start)))],
                     ['initialized array'])['initialized array']
        lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
        i = f'{lp}i.v'
        d.tunnel_in(1, cnt, 'index')
        s, t, b, h = d.tunnel_in(2, spr), d.tunnel_in(3, tiles), d.tunnel_in(4, bg), d.tunnel_in(5, hud)
        e_l, e_r = shiftreg(d, lp, err)
        pic, err2, _ = frame(d, s, t, b, h, e_l, sprites)
        if full:
            d.call('Draw Flattened Pixmap.vi', [('image data', to_pixmap(d, pic)), ('picture', '')], ['new picture'])
        last = d.tunnel_out(1, i)
        d.end()
        t_end = tick(last)
        ms = d.node('Divide', [('x', d.sub(t_end, t_start)), ('y', n)], ['x/y'])['x/y']
        return t_end, close_reg(d, e_r, err2), ms

    t0 = tick(d.node('Array Size', [('array', spr)], ['size(s)'])['size(s)'])
    t1, err1, ms_a = stage(t0, err0, False, False)
    t2, err2, ms_b = stage(t1, err1, True, False)
    t3, err3, ms_c = stage(t2, err2, True, True)
    # Laden der drei Raumbilder
    z = zero_after(t3)
    theme2 = d.add2(theme, z)
    a = d.call('Image_Load.vi', [('File name', room_image_name(d, theme2, rid)), ('error in', err3)], ['Image', 'error out'])
    b = d.call('Image_Load.vi', [('File name', room_image_name(d, theme2, rid, '_dim')), ('error in', a['error out'])], ['Image', 'error out'])
    c = d.call('Image_Load.vi', [('File name', room_image_name(d, theme2, rid, '_dark')), ('error in', b['error out'])], ['Image', 'error out'])
    (kind,) = d.unb(c['Image'], ['image depth'])
    t4 = tick(kind)
    d.indic('ms Images', 'double', '0', ms_a)
    d.indic('ms Sprites', 'double', '0', ms_b)
    d.indic('ms Full', 'double', '0', ms_c)
    d.indic('ms Load', 'uint32', '0', d.sub(t4, t3))
    d.indic('error out', ERR, ERR_V, c['error out'])
    d.write()


def test_bench2():
    d = Doc('Test_Bench2.vi', 'Measurement of the dirty-tile idea, ms per frame over Count frames. '
            'Sprites only = all objects of the room drawn into a picture WITHOUT the background in it; '
            'Tiles = Tiles background tiles (48 x 48) cut out of the room image and drawn; '
            'Cut all = cutting the whole room image into its 800 tiles once.', 9900)
    rid = d.ctrl('Room ID', 'string', '405')
    theme = d.ctrl('Theme', 'int32', '0')
    n = d.ctrl('Count', 'int32', '30')
    k_tiles = d.ctrl('Tiles', 'int32', '40')
    e = d.err_in()
    spr, tiles, bg, hud, err0 = load_all(d, rid, theme, e)

    def tick(dep):
        return d.node('Wait (ms)', [('milliseconds to wait', d.mul(dep, d.i32c(0)))], ['millisecond timer value'])['millisecond timer value']

    def zero_after(t):
        return d.i32(d.mul(t, d.const('uint32', '0')))

    def counter(count, t_start):
        return d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', d.add2(count, zero_after(t_start)))],
                      ['initialized array'])['initialized array']

    def cut(image, col, row):
        """eine Kachel aus dem Raumbild"""
        l, t = d.mul(col, d.i32c(TILE)), d.mul(row, d.i32c(TILE))
        w16 = lambda v: d.node('To Word Integer', [('number', v)], ['16bit integer'])['16bit integer']
        rect = d.bun(d.const(RECT, '[0,0,0,0]'), [('left', w16(l)), ('top', w16(t)), ('right', w16(d.add2(l, d.i32c(TILE)))),
                                                   ('bottom', w16(d.add2(t, d.i32c(TILE))))])
        return d.call('Get Image Subset.vi', [('subset rect', rect), ('image data', image)], ['image subset', '-true subset rect'])['image subset']

    t0 = tick(d.node('Array Size', [('array', spr)], ['size(s)'])['size(s)'])
    # A: nur Sprites
    cnt = counter(n, t0)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, cnt, 'index')
    s, t = d.tunnel_in(2, spr), d.tunnel_in(3, tiles)
    e_l, e_r = shiftreg(d, lp, err0)
    start = d.call('Draw Flattened Pixmap.vi', [('image data', d.idx(s, d.i32c(0))), ('picture', '')], ['new picture'])['new picture']
    rd = d.call('Room_Draw.vi', [('Picture', start), ('Sprites', s), ('Tiles', t), ('error in', e_l)], ['-Picture out', '-Count', 'error out'])
    last = d.tunnel_out(1, i)
    d.end()
    err1 = close_reg(d, e_r, rd['error out'])
    t1 = tick(last)
    # B: Kacheln ausschneiden und zeichnen
    cnt = counter(n, t1)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, cnt, 'index')
    b, s, kt = d.tunnel_in(2, bg), d.tunnel_in(3, spr), d.tunnel_in(4, k_tiles)
    e_l, e_r = shiftreg(d, lp, err1)
    start = d.call('Draw Flattened Pixmap.vi', [('image data', d.idx(s, d.i32c(0))), ('picture', '')], ['new picture'])['new picture']
    cnt2 = d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', kt)], ['initialized array'])['initialized array']
    lp2 = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    k = f'{lp2}i.v'
    d.tunnel_in(1, cnt2, 'index')
    b2 = d.tunnel_in(2, b)
    p_l, p_r = shiftreg(d, lp2, start)
    f_l, f_r = shiftreg(d, lp2, e_l)
    col, row = d.qr(k, d.i32c(COLS))
    pos = d.bun(d.const(POS, '[0,0]'), [('X', d.mul(col, d.i32c(TILE))), ('Y', d.add2(d.mul(row, d.i32c(TILE)), d.i32c(HUD_H)))])
    dr = d.call('Image_Draw.vi', [('Picture', p_l), ('Image', cut(b2, col, d.add2(row, d.i32c(7)))), ('Position', pos), ('error in', f_l)],
                ['Picture out', 'error out'])
    d.end()
    close_reg(d, p_r, dr['Picture out'])
    err_in = close_reg(d, f_r, dr['error out'])
    last = d.tunnel_out(1, i)
    d.end()
    err2 = close_reg(d, e_r, err_in)
    t2 = tick(last)
    # C: das ganze Raumbild einmal in 800 Kacheln zerlegen
    cnt = counter(d.i32c(ROWS * COLS), t2)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    k = f'{lp}i.v'
    d.tunnel_in(1, cnt, 'index')
    b = d.tunnel_in(2, bg)
    col, row = d.qr(k, d.i32c(COLS))
    all_tiles = d.tunnel_out(1, cut(b, col, row), 'index')
    d.end()
    t3 = tick(d.node('Array Size', [('array', all_tiles)], ['size(s)'])['size(s)'])
    d.indic('ms Sprites only', 'double', '0', d.node('Divide', [('x', d.sub(t1, t0)), ('y', n)], ['x/y'])['x/y'])
    d.indic('ms Tiles', 'double', '0', d.node('Divide', [('x', d.sub(t2, t1)), ('y', n)], ['x/y'])['x/y'])
    d.indic('ms Cut all', 'uint32', '0', d.sub(t3, t2))
    d.indic('error out', ERR, ERR_V, err2)
    d.write()




def test_bench3():
    d = Doc('Test_Bench3.vi', 'Measurement of the new picture build-up, ms per frame over Count frames: per frame Tiles background tiles are '
            'cut with Tile_Cut and drawn, then all objects of the room are drawn on top (picture without the whole background). '
            'Cut all = cutting all 800 tiles of the room once (ms).', 9900)
    rid = d.ctrl('Room ID', 'string', '405')
    theme = d.ctrl('Theme', 'int32', '0')
    n = d.ctrl('Count', 'int32', '50')
    k_tiles = d.ctrl('Tiles', 'int32', '40')
    e = d.err_in()
    spr, tiles, bg, hud, err0 = load_all(d, rid, theme, e)

    def tick(dep):
        return d.node('Wait (ms)', [('milliseconds to wait', d.mul(dep, d.i32c(0)))], ['millisecond timer value'])['millisecond timer value']

    def counter(count, t_start):
        z = d.i32(d.mul(t_start, d.const('uint32', '0')))
        return d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', d.add2(count, z))], ['initialized array'])['initialized array']

    t0 = tick(d.node('Array Size', [('array', spr)], ['size(s)'])['size(s)'])
    cnt = counter(n, t0)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, cnt, 'index')
    b, s, kt, tl = d.tunnel_in(2, bg), d.tunnel_in(3, spr), d.tunnel_in(4, k_tiles), d.tunnel_in(5, tiles)
    e_l, e_r = shiftreg(d, lp, err0)
    start = d.call('Draw Flattened Pixmap.vi', [('image data', d.idx(s, d.i32c(0))), ('picture', '')], ['new picture'])['new picture']
    cnt2 = d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', kt)], ['initialized array'])['initialized array']
    lp2 = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    k = f'{lp2}i.v'
    d.tunnel_in(1, cnt2, 'index')
    b2 = d.tunnel_in(2, b)
    p_l, p_r = shiftreg(d, lp2, start)
    f_l, f_r = shiftreg(d, lp2, e_l)
    col, row = d.qr(k, d.i32c(COLS))
    tc = d.call('Tile_Cut.vi', [('Image', b2), ('Column', col), ('Row', d.add2(row, d.i32c(7))), ('Offset Y', d.i32c(HUD_H)), ('error in', f_l)],
                ['Tile', 'error out'])
    p2 = d.call('Draw Flattened Pixmap.vi', [('image data', tc['Tile']), ('picture', p_l)], ['new picture'])['new picture']
    d.end()
    pic = close_reg(d, p_r, p2)
    err_t = close_reg(d, f_r, tc['error out'])
    rd = d.call('Room_Draw.vi', [('Picture', pic), ('Sprites', s), ('Tiles', tl), ('error in', err_t)], ['-Picture out', '-Count', 'error out'])
    last = d.tunnel_out(1, i)
    d.end()
    err1 = close_reg(d, e_r, rd['error out'])
    t1 = tick(last)
    cnt = counter(d.i32c(ROWS * COLS), t1)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    k = f'{lp}i.v'
    d.tunnel_in(1, cnt, 'index')
    b = d.tunnel_in(2, bg)
    e_l, e_r = shiftreg(d, lp, err1)
    col, row = d.qr(k, d.i32c(COLS))
    tc = d.call('Tile_Cut.vi', [('Image', b), ('Column', col), ('Row', row), ('Offset Y', d.i32c(HUD_H)), ('error in', e_l)], ['Tile', 'error out'])
    all_tiles = d.tunnel_out(1, tc['Tile'], 'index')
    d.end()
    err2 = close_reg(d, e_r, tc['error out'])
    t2 = tick(d.node('Array Size', [('array', all_tiles)], ['size(s)'])['size(s)'])
    d.indic('ms Frame', 'double', '0', d.node('Divide', [('x', d.sub(t1, t0)), ('y', n)], ['x/y'])['x/y'])
    d.indic('ms Cut all', 'uint32', '0', d.sub(t2, t1))
    d.indic('error out', ERR, ERR_V, err2)
    d.write()


def render_demo():
    d = Doc('Render_Demo.vi', 'Demo of the new picture build-up in a real window: the picture control never erases. The first frame draws '
            'the whole room, every later frame only renews one block of 5 x 4 tiles around Claude (Block_Cut) with all objects and Claude, composed invisibly into one pixmap and drawn in one go, '
            'who walks to and fro on the lowest floor. Stops after Frames frames (0 = until Stop). ms per frame = average time of one '
            'frame including the wait; set Wait ms to 0 to see how fast it can go.', 12000)
    rid = d.ctrl('Room ID', 'string', '405')
    theme = d.ctrl('Theme', 'int32', '0')
    limit = d.ctrl('Frames', 'int32', '600')
    wait = d.ctrl('Wait ms', 'int32', '16')
    e = d.err_in()
    spr, tiles, bg, hud, err0 = load_all(d, rid, theme, e)
    # Fenster: Bild "Screen" nach oben links, feste Zeichenflaeche, nie loeschen; alles andere rechts daneben
    vi = d.node('VI Server Reference', [], ['This VI'], extra='type="{LV.VI}"')['This VI']
    fp = d.node('Property Node', [('reference', vi), ('error in (no error)', err0)], ['Front Panel', '-reference out', 'error out'],
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
        pos = d.bun(d.const('cluster{int32.Left,int32.Top}', f'[{W + 30},40]', 'right of the screen'),
                    [('Top', d.add2(d.i32c(40), d.mul(kk, d.i32c(50))))])
        w = d.node('Property Node', [('reference', ref), ('error in (no error)', err), ('Position', pos)],
                   ['-reference out', 'error out'], extra='fields="write+Position" type="{LV.Control}"')
        return [w['error out']]

    er2, = d.case(txt['Text'], [c, txt['error out'], k], [('&quot;Screen&quot;', f_screen), ('Default', f_rest)], 1)
    d.end()
    err1 = close_reg(d, rr, er2)

    y_claude = HUD_H + (ROWS - 1) * TILE - TILE * 3 // 2
    zero, x0, dx0 = d.i32c(0), d.i32c(96), d.i32c(6)
    t_start = d.node('Tick Count (ms)', [], ['millisecond timer value'])['millisecond timer value']
    lp = d.begin('While Loop', 'count=""', 'Frames')
    spr1, tiles1, bg1, hud1, lim1, wait1, t01 = (d.tunnel_in(n + 1, v) for n, v in enumerate((spr, tiles, bg, hud, limit, wait, t_start)))
    i_l, i_r = shiftreg(d, lp, zero)
    x_l, x_r = shiftreg(d, lp, x0)
    xo_l, xo_r = shiftreg(d, lp, x0)          # Position im vorletzten Bild
    dx_l, dx_r = shiftreg(d, lp, dx0)
    e_l, e_r = shiftreg(d, lp, err1)
    x_try = d.add2(x_l, dx_l)
    turn = d.or_(d.lt(x_try, d.i32c(96)), d.gt(x_try, d.i32c(W - 200)))
    dx = d.sel(turn, d.sub(d.i32c(0), dx_l), dx_l)
    x = d.add2(x_l, dx)

    def full(a):
        sprites, tls, back, head, err, xx, x_old, x_older = a
        p1 = d.call('Draw Flattened Pixmap.vi', [('image data', head), ('picture', '')], ['new picture'])['new picture']
        p2 = d.call('Image_Draw.vi', [('Picture', p1), ('Image', back), ('Position', d.const(POS, f'[0,{HUD_H}]')), ('error in', err)],
                    ['Picture out', 'error out'])
        return [p2['Picture out'], p2['error out'], d.const(RECT, SCREEN, 'Whole screen')]

    def dirty(a):
        sprites, tls, back, head, err, xx, x_old, x_older = a
        lo1 = d.sel(d.lt(xx, x_old), xx, x_old)
        lo = d.sel(d.lt(x_older, lo1), x_older, lo1)
        _, c0 = d.qr(lo, d.i32c(TILE))
        # EIN Stueck von 5 x 4 Kacheln: eine Kachel Rand rund um die drei letzten Positionen, keine Naht unter der Figur
        bc = d.call('Block_Cut.vi', [('Image', back), ('Column', d.node('Decrement', [('x', c0)], ['x-1'])['x-1']), ('Row', d.i32c(ROWS - 4)),
                                     ('Offset Y', d.i32c(HUD_H)), ('Columns', d.i32c(5)), ('Rows', d.i32c(4)), ('error in', err)],
                    ['Block', 'error out'])
        p0 = d.call('Draw Flattened Pixmap.vi', [('image data', bc['Block']), ('picture', '')], ['new picture'])['new picture']
        (area,) = d.unb(bc['Block'], ['Rectangle'])
        return [p0, bc['error out'], area]

    pic, err2, area = d.case(d.eq(i_l, d.i32c(0)), [spr1, tiles1, bg1, hud1, e_l, x, x_l, xo_l], [('True', full), ('False', dirty)], 3)
    rd = d.call('Room_Draw.vi', [('Picture', pic), ('Sprites', spr1), ('Tiles', tiles1), ('error in', err2)], ['Picture out', '-Count', 'error out'])
    _, step = d.qr(i_l, d.i32c(6))
    phase, _ = d.qr(step, d.i32c(4))
    base = d.sel(d.lt(dx, d.i32c(0)), d.i32c(SPR['claude_l_walk_0']), d.i32c(SPR['claude_r_walk_0']))
    pos = d.bun(d.const(POS, f'[0,{y_claude}]'), [('X', x)])
    sd = d.call('Sprite_Draw.vi', [('Picture', rd['Picture out']), ('Sprites', spr1), ('Index', d.add2(base, phase)), ('Position', pos),
                                   ('error in', rd['error out'])], ['Picture out', 'error out'])
    # das Stueck mit allen Figuren unsichtbar zu EINER Pixmap rastern und in einem Zug zeichnen: kein Flackern, keine Naht
    pm = d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', d.i32c(24)), ('rect', area), ('picture', sd['Picture out'])],
                ['image data', '-new picture'])['image data']
    piece = d.bun(pm, [('Rectangle', area)])
    d.indic('Screen', 'picture', '', d.call('Draw Flattened Pixmap.vi', [('image data', piece), ('picture', '')], ['new picture'])['new picture'])
    d.node('Wait Until Next ms Multiple', [('millisecond multiple', wait1)], ['-millisecond timer value'])
    now = d.node('Tick Count (ms)', [], ['millisecond timer value'])['millisecond timer value']
    i2 = d.inc(i_l)
    d.indic('Frame', 'int32', '0', i2)
    d.indic('ms per frame', 'double', '0', d.node('Divide', [('x', d.sub(now, t01)), ('y', i2)], ['x/y'])['x/y'])
    stop_btn = d.ctrl('Stop', 'bool', 'false')
    done = d.or_(stop_btn, d.and_(d.gt(lim1, d.i32c(0)), d.node('Greater Or Equal?', [('x', i2), ('y', lim1)], ['x &gt;= y?'])['x &gt;= y?']))
    d.add(f'<Condition inputs="value:{done}" value="stop" uid="{d.nu()}" uid_parent="{lp}"/>')
    d.end()
    close_reg(d, i_r, i2)
    close_reg(d, x_r, x)
    close_reg(d, xo_r, x_l)
    close_reg(d, dx_r, dx)
    d.indic('error out', ERR, ERR_V, close_reg(d, e_r, sd['error out']))
    d.write()


def snapshot_dirty():
    d = Doc('Snapshot_Dirty.vi', 'Test of the tile renewal in ONE picture: whole room, then Claude at X - 6 and at X on the lowest floor, then the '
            'six tiles that the renderer would renew (Tile_Cut). The result must be identical to the room without Claude. '
            'Saved as Resources\\Preview\\<File name>.', 13000)
    rid = d.ctrl('Room ID', 'string', '405')
    theme = d.ctrl('Theme', 'int32', '0')
    x = d.ctrl('X', 'int32', '144')
    restore = d.ctrl('Renew', 'bool', 'true')
    fn = d.ctrl('File name', 'string', 'lv_dirty.png')
    e = d.err_in()
    spr, tiles, bg, hud, err = load_all(d, rid, theme, e)
    p1 = d.call('Draw Flattened Pixmap.vi', [('image data', hud), ('picture', '')], ['new picture'])['new picture']
    p2 = d.call('Image_Draw.vi', [('Picture', p1), ('Image', bg), ('Position', d.const(POS, f'[0,{HUD_H}]')), ('error in', err)],
                ['Picture out', 'error out'])
    y = HUD_H + (ROWS - 1) * TILE - TILE * 3 // 2
    x_old = d.sub(x, d.i32c(6))
    s1 = d.call('Sprite_Draw.vi', [('Picture', p2['Picture out']), ('Sprites', spr), ('Index', d.i32c(SPR['claude_r_walk_0'])),
                                   ('Position', d.bun(d.const(POS, f'[0,{y}]'), [('X', x_old)])), ('error in', p2['error out'])],
                ['Picture out', 'error out'])
    s2 = d.call('Sprite_Draw.vi', [('Picture', s1['Picture out']), ('Sprites', spr), ('Index', d.i32c(SPR['claude_r_walk_0'])),
                                   ('Position', d.bun(d.const(POS, f'[0,{y}]'), [('X', x)])), ('error in', s1['error out'])],
                ['Picture out', 'error out'])
    _, c0 = d.qr(x_old, d.i32c(TILE))

    def renew(a):
        pic, back, col0, err_in = a
        order = d.const('array{int32}', '[0,1,2,3,4,5]', 'Tiles')
        lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
        kk = d.tunnel_in(1, order, 'index')
        back2, c02 = d.tunnel_in(2, back), d.tunnel_in(3, col0)
        p_l, p_r = shiftreg(d, lp, pic)
        f_l, f_r = shiftreg(d, lp, err_in)
        dc, dr = d.qr(kk, d.i32c(3))
        tc = d.call('Tile_Cut.vi', [('Image', back2), ('Column', d.add2(c02, dc)), ('Row', d.add2(d.i32c(ROWS - 3), dr)),
                                    ('Offset Y', d.i32c(HUD_H)), ('error in', f_l)], ['Tile', 'error out'])
        pn = d.call('Draw Flattened Pixmap.vi', [('image data', tc['Tile']), ('picture', p_l)], ['new picture'])['new picture']
        d.end()
        return [close_reg(d, p_r, pn), close_reg(d, f_r, tc['error out'])]

    pic, err2 = d.case(restore, [s2['Picture out'], bg, c0, s2['error out']], [('True', renew), ('False', lambda a: [a[0], a[3]])], 2)
    rp = d.call('Resource_Path.vi', [('File name', fn), ('Subfolder', d.const('string', 'Preview')), ('error in', err2)], ['Path', 'error out'])
    w = d.call('Write PNG File.vi', [('compression (default)', ''), ('error in (no error)', rp['error out']),
                                     ('image data', to_pixmap(d, pic)), ('path to PNG file', rp['Path'])], ['error out', '-path'])
    d.indic('error out', ERR, ERR_V, w['error out'])
    d.write()


def test_run():
    d = Doc('Test_Run.vi', 'Test: plays a key script. Game_Start, then Ticks ticks of Game_Step; at tick At[k] the key Key[k] is sent '
            '(values see Game_Step: 1 Up, 2 Down, 3 Left, 4 Right, 8 Jump, 9 Release, 10 ReleaseV). Returns where Claude ends: X and Y in '
            'pixels, Mode, Room, Lives, the highest point reached (Min Y) and the number of ticks spent in the air.', 14000)
    at = d.ctrl('At', 'array{int32}', '[]')
    keys = d.ctrl('Key', 'array{uint16}', '[]')
    ticks = d.ctrl('Ticks', 'int32', '60')
    e = d.err_in()
    c = d.i32c
    gs = d.call('Game_Start.vi', [('error in', e)], ['State', 'Rooms', 'error out'])
    big, zero = c(100000), c(0)
    cnt = d.node('Initialize Array', [('element', c(0)), ('dimension size', ticks)], ['initialized array'])['initialized array']
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, cnt, 'index')
    at1, keys1, rooms1 = d.tunnel_in(2, at), d.tunnel_in(3, keys), d.tunnel_in(4, gs['Rooms'])
    s_l, s_r = shiftreg(d, lp, gs['State'])
    e_l, e_r = shiftreg(d, lp, gs['error out'])
    m_l, m_r = shiftreg(d, lp, big)
    a_l, a_r = shiftreg(d, lp, zero)
    hit = d.node('Search 1D Array', [('1D array', at1), ('element', i), ('start index (0)', '')], ['index of element'])['index of element']
    st = d.call('Game_Step.vi', [('State', s_l), ('Key', d.idx(keys1, hit)), ('Rooms', rooms1), ('error in', e_l)], ['State out', 'error out'])
    y10, mode = d.unb(st['State out'], ['Y10', 'Mode'])
    y = d.qr(y10, c(10))[1]
    m2 = d.sel(d.lt(y, m_l), y, m_l)
    a2 = d.add2(a_l, d.i32(d.b01(d.eq(mode, c(2)))))
    d.end()
    final = close_reg(d, s_r, st['State out'])
    x10, y10, mode, room, lives = d.unb(final, ['X10', 'Y10', 'Mode', 'Room', 'Lives'])
    d.indic('X', 'int32', '0', d.qr(x10, c(10))[1])
    d.indic('Y', 'int32', '0', d.qr(y10, c(10))[1])
    d.indic('Mode', 'int32', '0', mode)
    d.indic('Room', 'int32', '0', room)
    d.indic('Lives', 'int32', '0', lives)
    d.indic('Min Y', 'int32', '0', close_reg(d, m_r, m2))
    d.indic('Air ticks', 'int32', '0', close_reg(d, a_r, a2))
    d.indic('error out', ERR, ERR_V, close_reg(d, e_r, st['error out']))
    d.write()


ALL = {f.__name__: f for f in (snapshot_room, test_world, test_bench, test_bench2, test_bench3, render_demo, snapshot_dirty, test_run)}
if __name__ == '__main__':
    for name in (sys.argv[1:] or ALL):
        ALL[name]()
