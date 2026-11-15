# Gold Hunter - AIXML-Quellen der Grund-VIs (Dateien, Kacheln, Bilder). Spiel, Bild und App: gen_play.py (dort auch der Build-Contract).
# Aufruf: python gen_game.py [funktion ...]     ohne Argument: alle
import json
import sys
from gh_lib import *


def lut(values, n):
    """AIXML-Literal eines int32-Arrays der Laenge n aus {Index: Wert}, sonst -1"""
    return '[' + ','.join(str(values.get(k, -1)) for k in range(n)) + ']'


def resource_path():
    d = Doc('Resource_Path.vi', 'Absolute path of a file in the project: project folder\\Resources\\Subfolder\\File name. '
            'The project folder is derived from the path of this VI (Source\\Level).')
    name = d.ctrl('File name', 'string', '', 0)
    sub = d.ctrl('Subfolder', 'string', 'Levels', 5)
    e = d.err_in()
    me = d.node("Current VI's Path", [], ['path'])['path']
    root = d.strip(d.strip(d.strip(me)))
    p = d.build_path(d.build_path(d.build_path(root, d.const('string', 'Resources')), sub), name)
    d.indic('Path', 'path', '', p, 4)
    d.err_out(e)
    d.write()


def read_lines(d, path, err, delimiter='\\09'):
    """Textdatei -> 2D-String-Array (Zeilen x Felder)"""
    rd = d.node('Read from Text File', [('file (use dialog)', path), ('count', ''), ('error in', err), ('prompt (Open existing file)', '')],
                ['-refnum out', 'text', '-cancelled', 'error out'], extra='convertEol="true"')
    arr = d.node('Spreadsheet String To Array', [('format string', d.const('string', '%s')), ('spreadsheet string', rd['text']),
                                                 ('array type (2D Dbl)', d.const('array.2{string}', '[]')),
                                                 ('delimiter (Tab)', d.const('string', delimiter))], ['array'])['array']
    return arr, rd['error out']


def room_load():
    d = Doc('Room_Load.vi', f'Reads Resources\\Levels\\room_<Room ID>.txt into a 2D tile array (row, column), {COLS} x {ROWS} tiles of {TILE} px. '
            'Tile values: . 0 empty, # 1 wall, = 2 thin floor, ~ 3 vanishing floor, H 4 ladder, | 5 pole, : 6 rope, < 7 and > 8 conveyor, '
            'R B Y 10-12 doors, r b y 13-15 keys, g 16 gold coin, G 17 gold hoard, T 18 torch, S 19 spider, Z 20 snake, K 21 skull, P 22 start.')
    rid = d.ctrl('Room ID', 'string', '005', 0)
    e = d.err_in()
    fname = d.node('Concatenate Strings', [('string', d.const('string', 'room_')), ('string', rid), ('string', d.const('string', '.txt'))],
                   ['concatenated string'])['concatenated string']
    r = d.call('Resource_Path.vi', [('File name', fname), ('Subfolder', d.const('string', 'Levels')), ('error in', e)], ['Path', 'error out'])
    arr, err = read_lines(d, r['Path'], r['error out'])
    codes = d.const('array{uint8}', '[' + ','.join(str({ord(c): v for c, v in TILE_CODE.items()}.get(k, 0)) for k in range(256)) + ']',
                    'Tile value per character')
    d.begin('For Loop', 'count="" maxin="" maxout=""')
    row = d.tunnel_in(1, arr, 'index')
    table = d.tunnel_in(2, codes)
    bytes_ = d.node('String To Byte Array', [('string', d.idx(row, d.i32c(0)))], ['unsigned byte array'])['unsigned byte array']
    d.begin('For Loop', 'count="" maxin="" maxout=""')
    ch = d.tunnel_in(1, bytes_, 'index')
    tb = d.tunnel_in(2, table)
    inner_out = d.tunnel_out(1, d.idx(tb, ch), 'index')
    d.end()
    tiles = d.tunnel_out(1, inner_out, 'index')
    d.end()
    d.indic('Tiles', TILES, '[]', tiles, 4)
    d.err_out(err)
    d.write()


def world_load():
    d = Doc('World_Load.vi', 'Loads the whole world: reads Resources\\Levels\\world.txt (room grid, depth x column, --- = no room) and every '
            'room file with Room_Load. Rooms = all rooms in reading order with ID, Depth, Column and Tiles; Grid = the room IDs as in the file.')
    e = d.err_in()
    r = d.call('Resource_Path.vi', [('File name', d.const('string', 'world.txt')), ('Subfolder', d.const('string', 'Levels')), ('error in', e)],
               ['Path', 'error out'])
    grid, err = read_lines(d, r['Path'], r['error out'], ' ')
    none, empty = d.const('string', '---'), d.const(ROOM, ROOM_V)
    outer = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    depth = f'{outer}i.v'
    line = d.tunnel_in(1, grid, 'index')
    none1, empty1 = d.tunnel_in(2, none), d.tunnel_in(3, empty)
    e_l, e_r = shiftreg(d, outer, err)
    inner = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    col = f'{inner}i.v'
    rid = d.tunnel_in(1, line, 'index')
    none2, empty2, depth2 = d.tunnel_in(2, none1), d.tunnel_in(3, empty1), d.tunnel_in(4, depth)
    e2_l, e2_r = shiftreg(d, inner, e_l)
    length = d.node('String Length', [('string', rid)], ['length'])['length']
    is_room = d.and_(d.eq(length, d.i32c(3)), d.ne(rid, none2))
    tiles, err2 = d.case(is_room, [rid, e2_l], [
        ('True', lambda i: (lambda c: [c['Tiles'], c['error out']])(
            d.call('Room_Load.vi', [('Room ID', i[0]), ('error in', i[1])], ['Tiles', 'error out']))),
        ('False', lambda i: [d.const(TILES, '[]'), i[1]]),
    ], 2)
    room = d.bun(empty2, [('ID', rid), ('Depth', depth2), ('Column', col), ('Tiles', tiles)])
    rooms_row = d.tunnel_out(1, room, 'index', cond=is_room)
    d.end()
    err_row = close_reg(d, e2_r, err2)
    rooms = d.tunnel_out(1, rooms_row, 'concat')
    d.end()
    err_all = close_reg(d, e_r, err_row)
    d.indic('Rooms', ROOMS, '[]', rooms, 4)
    d.indic('Grid', 'array.2{string}', '[]', grid, 6)
    d.err_out(err_all)
    d.write()


def tile_at():
    d = Doc('Tile_At.vi', f'Tile value under the point (X, Y) in playfield pixels (tile = {TILE} px). Outside the playfield 0 (empty).')
    tiles = d.ctrl('Tiles', TILES, '[]', 0)
    x = d.ctrl('X', 'int32', '0', 5)
    y = d.ctrl('Y', 'int32', '0', 7)
    e = d.err_in()
    t = d.i32c(TILE)
    _, col = d.qr(x, t)
    _, row = d.qr(y, t)
    k = d.node('Index Array', [('array', tiles), ('index (row)', row), ('index (col)', col)], ['element'], extra='dimensions="2"')['element']
    d.indic('Tile', 'uint8', '0', k, 4)
    d.err_out(e)
    d.write()


def image_load():
    d = Doc('Image_Load.vi', 'Loads a PNG from Resources\\Images as image data (24 bit, no transparency), e.g. a room background or the HUD.')
    name = d.ctrl('File name', 'string', 'hud.png', 0)
    e = d.err_in()
    r = d.call('Resource_Path.vi', [('File name', name), ('Subfolder', d.const('string', 'Images')), ('error in', e)], ['Path', 'error out'])
    png = d.call('Read PNG File.vi', [('Transparency Thresh', ''), ('error in (no error)', r['error out']), ('path to PNG file', r['Path'])],
                 ['error out', 'image data', '-path'])
    d.indic('Image', IMG, IMG_V, png['image data'], 4)
    d.err_out(png['error out'])
    d.write()


def sprite_atlas_load():
    d = Doc('SpriteAtlas_Load.vi', 'Loads the sprite atlas: all PNG files from Resources\\Sprites in the order of sprites.txt '
            '(one name per line, without extension). Transparent pixels are masked by Read PNG File. Index = line in sprites.txt.')
    e = d.err_in()
    r = d.call('Resource_Path.vi', [('File name', d.const('string', 'sprites.txt')), ('Subfolder', d.const('string', 'Sprites')),
                                    ('error in', e)], ['Path', 'error out'])
    folder = d.strip(r['Path'])
    names, err = read_lines(d, r['Path'], r['error out'])
    ext = d.const('string', '.png')
    lp = d.begin('For Loop', 'count="" maxin="" maxout=""')
    row = d.tunnel_in(1, names, 'index')
    dirp = d.tunnel_in(2, folder)
    ex = d.tunnel_in(3, ext)
    e_l, e_r = shiftreg(d, lp, err)
    fname = d.node('Concatenate Strings', [('string', d.idx(row, d.i32c(0))), ('string', ex)], ['concatenated string'])['concatenated string']
    png = d.call('Read PNG File.vi', [('Transparency Thresh', ''), ('error in (no error)', e_l),
                                      ('path to PNG file', d.build_path(dirp, fname))], ['error out', 'image data', '-path'])
    sprites = d.tunnel_out(1, png['image data'], 'index')
    d.end()
    d.indic('Sprites', SPRITES, '[]', sprites, 4)
    d.err_out(close_reg(d, e_r, png['error out']))
    d.write()


def moved(d, img, pos):
    """Bilddaten mit verschobenem Rectangle: linke obere Ecke auf Position; liefert (Bild, Y)"""
    (rect,) = d.unb(img, ['Rectangle'])
    l, t, r, b = d.unb(rect, ['left', 'top', 'right', 'bottom'])
    w, h = d.sub(r, l), d.sub(b, t)
    x, y = d.unb(pos, ['X', 'Y'])
    x16 = d.node('To Word Integer', [('number', x)], ['16bit integer'])['16bit integer']
    y16 = d.node('To Word Integer', [('number', y)], ['16bit integer'])['16bit integer']
    rect2 = d.bun(rect, [('left', x16), ('top', y16), ('right', d.add2(x16, w)), ('bottom', d.add2(y16, h))])
    return d.bun(img, [('Rectangle', rect2)]), y


def sprite_draw():
    d = Doc('Sprite_Draw.vi', 'Draws Sprites[Index] with its transparency mask so that its top left corner is at Position (X, Y) in '
            'screen pixels. The Rectangle of the image data is moved (width and height stay). Sprites with Y < -300 are not drawn.')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    ix = d.ctrl('Index', 'int32', '0', 7)
    pos = d.ctrl('Position', POS, '[0,0]', 9)
    e = d.err_in()
    img2, y = moved(d, d.idx(spr, ix), pos)
    out, = d.case(d.lt(y, d.i32c(-300)), [pic, img2], [
        ('True', lambda i: [i[0]]),
        ('False', lambda i: [d.call('Draw Flattened Pixmap.vi', [('image data', i[1]), ('picture', i[0])], ['new picture'])['new picture']]),
    ], 1)
    d.indic('Picture out', 'picture', '', out, 4)
    d.err_out(e)
    d.write()


def image_draw():
    d = Doc('Image_Draw.vi', 'Draws one image (room background, HUD) so that its top left corner is at Position (X, Y) in screen pixels.')
    pic = d.ctrl('Picture', 'picture', '', 0)
    img = d.ctrl('Image', IMG, IMG_V, 5)
    pos = d.ctrl('Position', POS, '[0,0]', 7)
    e = d.err_in()
    img2, _ = moved(d, img, pos)
    out = d.call('Draw Flattened Pixmap.vi', [('image data', img2), ('picture', pic)], ['new picture'])['new picture']
    d.indic('Picture out', 'picture', '', out, 4)
    d.err_out(e)
    d.write()


def tile_cut():
    d = Doc('Tile_Cut.vi', f'Cuts one tile ({TILE} x {TILE} px) out of a room image (24 bit) directly from its pixel bytes and returns it '
            'as image data that is already placed on the screen: Rectangle = tile position plus Offset Y (height of the HUD). '
            'Much faster than Get Image Subset, which copies the whole image on every call.')
    img = d.ctrl('Image', IMG, IMG_V, 0)
    col = d.ctrl('Column', 'int32', '0', 5)
    row = d.ctrl('Row', 'int32', '0', 7)
    off_y = d.ctrl('Offset Y', 'int32', str(HUD_H), 9)
    e = d.err_in()
    typ, depth, data, rect = d.unb(img, ['image type', 'image depth', 'image', 'Rectangle'])
    top, bottom = d.unb(rect, ['top', 'bottom'])
    height = d.i32(d.sub(bottom, top))
    _, stride = d.qr(d.node('Array Size', [('array', data)], ['size(s)'])['size(s)'], height)
    base = d.add2(d.mul(d.mul(row, d.i32c(TILE)), stride), d.mul(col, d.i32c(TILE * 3)))
    lines = d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', d.i32c(TILE))], ['initialized array'])['initialized array']
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, lines, 'index')
    data1, base1, stride1 = d.tunnel_in(2, data), d.tunnel_in(3, base), d.tunnel_in(4, stride)
    part = d.node('Array Subset', [('array', data1), ('index', d.add2(base1, d.mul(i, stride1))), ('length', d.i32c(TILE * 3))],
                  ['subarray'])['subarray']
    pixels = d.tunnel_out(1, part, 'concat')
    d.end()
    w16 = lambda v: d.node('To Word Integer', [('number', v)], ['16bit integer'])['16bit integer']
    left, up = d.mul(col, d.i32c(TILE)), d.add2(d.mul(row, d.i32c(TILE)), off_y)
    rect2 = d.bun(rect, [('left', w16(left)), ('top', w16(up)), ('right', w16(d.add2(left, d.i32c(TILE)))),
                         ('bottom', w16(d.add2(up, d.i32c(TILE))))])
    tile = d.bun(d.const(IMG, IMG_V), [('image type', typ), ('image depth', depth), ('image', pixels), ('Rectangle', rect2)])
    d.indic('Tile', IMG, IMG_V, tile, 4)
    d.err_out(e)
    d.write()


def block_cut():
    d = Doc('Block_Cut.vi', f'Cuts a block of Columns x Rows tiles ({TILE} px each) out of a room image (24 bit) as ONE piece of image data '
            'that is already placed on the screen (Rectangle = block position plus Offset Y). The renderer renews the area around a '
            'figure with one block, so that no seam between two pieces lies under the figure (with Windows display scaling, pieces '
            'drawn side by side leave thin uncovered lines). Column and Row are limited so that the block stays inside the room.')
    img = d.ctrl('Image', IMG, IMG_V, 0)
    col_in = d.ctrl('Column', 'int32', '0', 5)
    row_in = d.ctrl('Row', 'int32', '0', 7)
    off_y = d.ctrl('Offset Y', 'int32', str(HUD_H), 9)
    ncol = d.ctrl('Columns', 'int32', '1', 1)
    nrow = d.ctrl('Rows', 'int32', '1', 2)
    e = d.err_in()

    def clamp(v, hi):
        lo = d.sel(d.lt(v, d.i32c(0)), d.i32c(0), v)
        return d.sel(d.gt(lo, hi), hi, lo)

    col = clamp(col_in, d.sub(d.i32c(COLS), ncol))
    row = clamp(row_in, d.sub(d.i32c(ROWS), nrow))
    typ, depth, data, rect = d.unb(img, ['image type', 'image depth', 'image', 'Rectangle'])
    top, bottom = d.unb(rect, ['top', 'bottom'])
    height = d.i32(d.sub(bottom, top))
    _, stride = d.qr(d.node('Array Size', [('array', data)], ['size(s)'])['size(s)'], height)
    base = d.add2(d.mul(d.mul(row, d.i32c(TILE)), stride), d.mul(col, d.i32c(TILE * 3)))
    width_px, height_px = d.mul(ncol, d.i32c(TILE)), d.mul(nrow, d.i32c(TILE))
    lines = d.node('Initialize Array', [('element', d.i32c(0)), ('dimension size', height_px)], ['initialized array'])['initialized array']
    row_len = d.mul(width_px, d.i32c(3))
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    d.tunnel_in(1, lines, 'index')
    data1, base1, stride1, len1 = d.tunnel_in(2, data), d.tunnel_in(3, base), d.tunnel_in(4, stride), d.tunnel_in(5, row_len)
    part = d.node('Array Subset', [('array', data1), ('index', d.add2(base1, d.mul(i, stride1))), ('length', len1)], ['subarray'])['subarray']
    pixels = d.tunnel_out(1, part, 'concat')
    d.end()
    w16 = lambda v: d.node('To Word Integer', [('number', v)], ['16bit integer'])['16bit integer']
    left, up = d.mul(col, d.i32c(TILE)), d.add2(d.mul(row, d.i32c(TILE)), off_y)
    rect2 = d.bun(rect, [('left', w16(left)), ('top', w16(up)), ('right', w16(d.add2(left, width_px))), ('bottom', w16(d.add2(up, height_px)))])
    block = d.bun(d.const(IMG, IMG_V), [('image type', typ), ('image depth', depth), ('image', pixels), ('Rectangle', rect2)])
    d.indic('Block', IMG, IMG_V, block, 4)
    d.err_out(e)
    d.write()


def tile_read():
    d = Doc('Tile_Read.vi', f'Tile value under the point (X, Y) in playfield pixels (tile = {TILE} px). Points outside the room read the nearest '
            'tile at the edge, so a ladder, pole or floor that leaves the room continues until the room changes.')
    tiles = d.ctrl('Tiles', TILES, '[]', 0)
    x = d.ctrl('X', 'int32', '0', 5)
    y = d.ctrl('Y', 'int32', '0', 7)
    e = d.err_in()

    def clamp(v, hi):
        lo = d.sel(d.lt(v, d.i32c(0)), d.i32c(0), v)
        return d.sel(d.gt(lo, d.i32c(hi)), d.i32c(hi), lo)

    _, col = d.qr(x, d.i32c(TILE))
    _, row = d.qr(y, d.i32c(TILE))
    k = d.node('Index Array', [('array', tiles), ('index (row)', clamp(row, ROWS - 1)), ('index (col)', clamp(col, COLS - 1))], ['element'],
               extra='dimensions="2"')['element']
    d.indic('Tile', 'uint8', '0', k, 4)
    d.err_out(e)
    d.write()



# tile_at, sprite_atlas_load, sprite_draw, image_draw, tile_cut, block_cut: VIs des alten Bildaufbaus, nicht mehr erzeugt
BASIC = {f.__name__: f for f in (resource_path, room_load, world_load, image_load, tile_read)}
if __name__ == '__main__':
    for name in (sys.argv[1:] or BASIC):
        BASIC[name]()
