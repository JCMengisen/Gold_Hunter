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
            'and saves the 1920 x 1080 picture as Resources\\Preview\\<File name>. Count = number of sprites drawn.', 5000)
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




ALL = {f.__name__: f for f in (snapshot_room, test_world, test_bench, test_bench2)}
if __name__ == '__main__':
    for name in (sys.argv[1:] or ALL):
        ALL[name]()
