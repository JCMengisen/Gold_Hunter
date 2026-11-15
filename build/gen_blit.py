# Gold Hunter - Zeichnen ohne Picture to Pixmap ("Blit"): das ganze Bild entsteht in einem Pixel-Array (Zeilen x Breite*3, RGB),
#   Sprites werden mit ihrer Maske hineinkopiert, am Ende EIN Draw Flattened Pixmap. Kein Flackern, gleichmaessige Kosten.
#   Blit_Load      liest sprites.bin / sprites_blit.txt (make_blit.py)
#   Sprite_Blit    kopiert ein Sprite mit Maske ins Bild (abgeschnitten am Bildrand)
#   Glyphs_Blit, Room_Blit, Enemies_Blit, Overlay_Blit   dieselben Generatoren wie die Picture-VIs, nur umbenannt und umgetypt
#   Scene_Blit     der ganze Bildschirm (Titel oder HUD + Raum + Objekte + Gegner + Claude + Meldung)
# Aufruf: python gen_blit.py [Name ...]
import sys
from gh_lib import *
import gen_play as gp
from gen_game import read_lines
from gen_play import allb

FRAME, FRAME_V = 'array.2{uint8}', '[]'
BSPR = 'cluster{array.2{uint8}.Pix,array.2{uint8}.Mask}'      # Maske: 255 = sichtbar, 0 = durchsichtig
BSPRITES = f'array{{{BSPR}}}'
NAMES = {'Sprite_Draw.vi': 'Sprite_Blit.vi', 'Glyphs_Draw.vi': 'Glyphs_Blit.vi', 'Room_Draw.vi': 'Room_Blit.vi',
         'Enemies_Draw.vi': 'Enemies_Blit.vi', 'Overlay_Draw.vi': 'Overlay_Blit.vi'}


def variants_on():
    gp.BLIT = True
    Doc.RENAME = dict(NAMES)
    Doc.SUBST = [('type="picture" value=""', f'type="{FRAME}" value="{FRAME_V}"'), (SPRITES, BSPRITES)]


def variants_off():
    gp.BLIT = False
    Doc.RENAME, Doc.SUBST = {}, []


def blit_load():
    d = Doc('Blit_Load.vi', 'Loads all sprites as raw pixels for Sprite_Blit: Resources\\Sprites\\sprites_blit.txt (Width;Height;Offset per '
            'sprite, order of sprites.txt) and sprites.bin (per sprite Height*Width*3 bytes RGB, then as many mask bytes, 255 = visible). '
            'Written by build\\make_blit.py.')
    e = d.err_in()
    c = d.i32c
    r = d.call('Resource_Path.vi', [('File name', d.const('string', 'sprites_blit.txt')), ('Subfolder', d.const('string', 'Sprites')),
                                    ('error in', e)], ['Path', 'error out'])
    rows, err = read_lines(d, r['Path'], r['error out'], ';')
    rb = d.call('Resource_Path.vi', [('File name', d.const('string', 'sprites.bin')), ('Subfolder', d.const('string', 'Sprites')),
                                     ('error in', err)], ['Path', 'error out'])
    bn = d.node('Read from Binary File', [('file (use dialog)', rb['Path']), ('count', c(-1)), ('byte order (0\\3Abig-endian\\2C network order)', ''),
                                          ('error in', rb['error out']), ('prompt (Open existing file)', ''), ('data type', d.const('uint8', '0', 'Bytes'))],
                ['-refnum out', 'data', '-cancelled', 'error out'])
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    row = d.tunnel_in(1, rows, 'index')
    blob = d.tunnel_in(2, bn['data'])

    def num(k):
        return d.node('Decimal String To Number', [('string', d.idx(row, c(k))), ('offset', ''), ('default (0L)', c(0))],
                      ['-offset past number', 'number'])['number']
    w, h, off = num(0), num(1), num(2)
    n = d.mul(d.mul(w, h), c(3))
    pix = d.node('Array Subset', [('array', blob), ('index', off), ('length', n)], ['subarray'])['subarray']
    msk = d.node('Array Subset', [('array', blob), ('index', d.add2(off, n)), ('length', n)], ['subarray'])['subarray']
    pix2 = d.node('Reshape Array', [('array', pix), ('dimension size', h), ('dimension size', d.mul(w, c(3)))], ['output array'])['output array']
    msk2 = d.node('Reshape Array', [('array', msk), ('dimension size', h), ('dimension size', d.mul(w, c(3)))], ['output array'])['output array']
    one = d.bun(d.const(BSPR, '[[],[]]'), [('Pix', pix2), ('Mask', msk2)])
    sprites = d.tunnel_out(1, one, 'index')
    d.end()
    d.indic('Sprites', BSPRITES, '[]', sprites, 4)
    d.err_out(bn['error out'])
    d.write()


def sprite_blit():
    d = Doc('Sprite_Blit.vi', f'Copies Sprites[Index] with its mask (bytes 255/0, mixed bitwise) into the screen raster ({H} rows x {W}*3 bytes RGB) so that its top '
            'left corner is at Position (X, Y); the part outside the screen is cut off (Y = -2000 hides a sprite).')
    pic = d.ctrl('Picture', FRAME, FRAME_V, 0)
    spr = d.ctrl('Sprites', BSPRITES, '[]', 5)
    ix = d.ctrl('Index', 'int32', '0', 7)
    pos = d.ctrl('Position', POS, '[0,0]', 9)
    e = d.err_in()
    c = d.i32c
    pix, msk = d.unb(d.idx(spr, ix), ['Pix', 'Mask'])
    dims = d.node('Array Size', [('array', pix)], ['size(s)'])['size(s)']
    h, w3 = d.i32(d.idx(dims, c(0))), d.i32(d.idx(dims, c(1)))
    w = d.qr(w3, c(3))[1]
    x, y = d.unb(pos, ['X', 'Y'])
    x0, y0 = gp.maxv(d, x, c(0)), gp.maxv(d, y, c(0))
    x1, y1 = gp.minv(d, d.add2(x, w), c(W)), gp.minv(d, d.add2(y, h), c(H))
    cw, ch = d.sub(x1, x0), d.sub(y1, y0)
    visible = d.and_(d.gt(cw, c(0)), d.gt(ch, c(0)))

    def f_draw(i):
        fr, p, m, xx0, yy0, sx, sy, ww, hh = i
        sub = lambda a, r0, c0: d.node('Array Subset', [('array', a), ('index', r0), ('length', hh), ('index', c0), ('length', d.mul(ww, d.i32c(3)))],
                                       ['subarray'], extra='dimensions="2"')['subarray']
        ps, ms, fs = sub(p, sy, d.mul(sx, d.i32c(3))), sub(m, sy, d.mul(sx, d.i32c(3))), sub(fr, yy0, d.mul(xx0, d.i32c(3)))
        # bitweise mischen (Maske 255/0): Sprite, wo sichtbar, sonst Hintergrund - ohne Select, das nur einen Skalar waehlt
        mix = d.or_(d.and_(ps, ms), d.and_(fs, d.not_(ms)))
        out = d.node('Replace Array Subset', [('array', fr), ('new element/subarray', mix), ('index (row)', yy0), ('index (col)', d.mul(xx0, d.i32c(3)))],
                     ['output array'], extra='dimensions="2"')['output array']
        return [out]

    out, = d.case(visible, [pic, pix, msk, x0, y0, d.sub(x0, x), d.sub(y0, y), cw, ch],
                  [('True', f_draw), ('False', lambda i: [i[0]])], 1)
    d.indic('Picture out', FRAME, FRAME_V, out, 4)
    d.err_out(e)
    d.write()


def scene_blit():
    d = Doc('Scene_Blit.vi', 'Builds the WHOLE screen in one raster (rows x width*3 RGB), without any picture drawing: on the title the '
            'title image and the overlay; otherwise the HUD image with its values on top of the room raster (Grid, lit or the dark '
            'composite), the objects (Room_Blit), the enemies, Claude and the message of the phase.')
    grid = d.ctrl('Grid', GRID, '[]', 0)
    spr = d.ctrl('Sprites', BSPRITES, '[]', 7)
    st = d.ctrl('State', STATE, STATE_V, 9)
    view = d.ctrl('View', VIEW, VIEW_V, 1)
    hud = d.ctrl('Hud', IMG, IMG_V, 2)
    title = d.ctrl('Title', IMG, IMG_V, 3)
    e = d.err_in()
    c = d.i32c
    phase, = d.unb(st, ['Phase'])
    is_title = d.eq(phase, c(PH['Title']))
    full = d.const(RECT, f'[0,0,{W},{H}]', 'Whole screen')

    def raster(img, rows):
        data, = d.unb(img, ['image'])
        return d.node('Reshape Array', [('array', data), ('dimension size', d.i32c(rows)), ('dimension size', d.i32c(W * 3))], ['output array'])['output array']

    def f_title(i):
        tt, sp, s, clip, err = i[:5]
        # title.png hat zwei Seiten untereinander: Titelbild, darunter die Kurzanleitung (nach dem Titelbild TITLE_HELP Ticks lang)
        pt, = d.unb(s, ['PhaseTicks'])
        help_page = d.and_(gp.ge(d, pt, c(TITLE_CARD)), d.lt(pt, c(TITLE_CARD + TITLE_HELP)))
        data, = d.unb(tt, ['image'])
        page = d.node('Array Subset', [('array', data), ('index', d.sel(help_page, c(H * W * 3), c(0))), ('length', c(H * W * 3))],
                      ['subarray'])['subarray']
        rast = d.node('Reshape Array', [('array', page), ('dimension size', c(H)), ('dimension size', c(W * 3))], ['output array'])['output array']
        ov = d.call('Overlay_Blit.vi', [('Picture', rast), ('Sprites', sp), ('State', s), ('Clip', clip), ('error in', err)],
                    ['Picture out', 'error out'])
        return [ov['Picture out'], ov['error out']]

    def f_game(i):
        _, sp, s, clip, err, g, vw, hd = i
        fr = d.node('Build Array', [('array', raster(hd, HUD_H)), ('array', g)], ['appended array'], extra='concat="true"')['appended array']
        Doc.RENAME = dict(NAMES)        # hud_ops ruft Sprite_Draw/Glyphs_Draw -> hier die Blit-VIs
        try:
            p1, err1 = gp.hud_ops(d, fr, sp, s, err)
        finally:
            Doc.RENAME = {}
        tiles, enemies, tick, fphase = d.unb(s, ['Tiles', 'Enemies', 'Tick', 'FloorPhase'])
        rd = d.call('Room_Blit.vi', [('Picture', p1), ('Sprites', sp), ('Tiles', tiles), ('Region', d.const(RECT, f'[0,0,{COLS},{ROWS}]')),
                                     ('FloorPhase', fphase), ('View', vw), ('error in', err1)], ['Picture out', 'error out'])
        ed = d.call('Enemies_Blit.vi', [('Picture', rd['Picture out']), ('Sprites', sp), ('Enemies', enemies), ('Tick', tick), ('View', vw),
                                        ('error in', rd['error out'])], ['Picture out', 'error out'])
        cix, cxp, cyp = d.unb(vw, ['ClaudeIdx', 'ClaudeX', 'ClaudeY'])
        cpos = d.bun(d.const(POS, '[0,0]'), [('X', cxp), ('Y', d.sel(gp.ge(d, cix, c(0)), cyp, c(-2000)))])
        cd = d.call('Sprite_Blit.vi', [('Picture', ed['Picture out']), ('Sprites', sp), ('Index', gp.maxv(d, cix, c(0))), ('Position', cpos),
                                       ('error in', ed['error out'])], ['Picture out', 'error out'])
        # Fallschirm ueber Claude, solange er in der Schatzkammer faellt
        rm, md, vy = d.unb(s, ['Room', 'Mode', 'VY10'])
        chute = allb(d, d.eq(rm, c(TREASURE_IDX)), d.eq(md, c(2)), d.gt(vy, c(0)))
        ppos = d.bun(d.const(POS, '[0,0]'), [('X', d.sub(cxp, c(8))), ('Y', d.sel(chute, d.sub(cyp, c(30)), c(-2000)))])
        pc = d.call('Sprite_Blit.vi', [('Picture', cd['Picture out']), ('Sprites', sp), ('Index', c(SPR['parachute'])), ('Position', ppos),
                                       ('error in', cd['error out'])], ['Picture out', 'error out'])
        cd = pc
        ov = d.call('Overlay_Blit.vi', [('Picture', cd['Picture out']), ('Sprites', sp), ('State', s), ('Clip', clip), ('error in', cd['error out'])],
                    ['Picture out', 'error out'])
        return [ov['Picture out'], ov['error out']]

    pic, err = d.case(is_title, [title, spr, st, full, e, grid, view, hud], [('True', f_title), ('False', f_game)], 2)
    d.indic('Picture', FRAME, FRAME_V, pic, 4)
    d.err_out(err)
    d.write()


def glyphs_blit():
    variants_on()
    try:
        gp.glyphs_draw()
    finally:
        variants_off()


def room_blit():
    variants_on()
    try:
        gp.room_draw()
    finally:
        variants_off()


def enemies_blit():
    variants_on()
    try:
        gp.enemies_draw()
    finally:
        variants_off()


def overlay_blit():
    variants_on()
    try:
        gp.overlay_draw()
    finally:
        variants_off()


ALL = {f.__name__: f for f in (blit_load, sprite_blit, glyphs_blit, room_blit, enemies_blit, overlay_blit, scene_blit)}
if __name__ == '__main__':
    for name in (sys.argv[1:] or ALL):
        ALL[name]()
