# Gold Hunter - erzeugt die AIXML-Quellen der SubVIs und den Build-Contract (Stand M1).
# Aufruf: python gen_game.py [funktion ...]     ohne Argument: alle
import json
import sys
from gh_lib import *


def lut(values, n):
    """AIXML-Literal eines int32-Arrays der Laenge n aus {Index: Wert}, sonst -1"""
    return '[' + ','.join(str(values.get(k, -1)) for k in range(n)) + ']'


# ------------------------------------------------------------------ Level
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


# ------------------------------------------------------------------ Render
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


def room_draw():
    d = Doc('Room_Draw.vi', f'Draws all objects of a room at their start places from the tile array: vanishing floors, conveyors, doors, '
            f'keys, gold, torch and enemies (not the start figure). Playfield starts {HUD_H} px below the top (HUD). Floors, conveyors and doors '
            'are aligned to the top of their tile (a door only at its top tile), everything else stands on the floor of its tile. '
            'Count = number of sprites drawn.')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    tiles = d.ctrl('Tiles', TILES, '[]', 7)
    e = d.err_in()
    n = max(TILE_CODE.values()) + 1
    sprite_of = d.const('array{int32}', lut({k: SPR[v] for k, v in ROOM_SPRITE.items()}, n), 'Sprite per tile value')
    top_of = d.const('array{int32}', lut({k: 1 for k in TOP_ALIGNED}, n), 'Top aligned')
    zero = d.i32c(0)                   # Startwert eines Schieberegisters: muss vor der Schleife entstehen
    outer = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    r = f'{outer}i.v'
    row = d.tunnel_in(1, tiles, 'index')
    all1, spr1, sof1, top1 = d.tunnel_in(2, tiles), d.tunnel_in(3, spr), d.tunnel_in(4, sprite_of), d.tunnel_in(5, top_of)
    p_l, p_r = shiftreg(d, outer, pic)
    e_l, e_r = shiftreg(d, outer, e)
    c_l, c_r = shiftreg(d, outer, zero)
    inner = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    c = f'{inner}i.v'
    code8 = d.tunnel_in(1, row, 'index')
    all2, spr2, sof2, top2, r2 = d.tunnel_in(2, all1), d.tunnel_in(3, spr1), d.tunnel_in(4, sof1), d.tunnel_in(5, top1), d.tunnel_in(6, r)
    p2_l, p2_r = shiftreg(d, inner, p_l)
    e2_l, e2_r = shiftreg(d, inner, e_l)
    c2_l, c2_r = shiftreg(d, inner, c_l)
    code = d.i32(code8)
    six = d.idx(sof2, code)
    above = d.node('Index Array', [('array', all2), ('index (row)', d.node('Decrement', [('x', r2)], ['x-1'])['x-1']), ('index (col)', c)], ['element'],
                   extra='dimensions="2"')['element']
    is_door = d.and_(d.node('Greater Or Equal?', [('x', code), ('y', d.i32c(DOOR_CODES[0]))], ['x &gt;= y?'])['x &gt;= y?'],
                     d.node('Less Or Equal?', [('x', code), ('y', d.i32c(DOOR_CODES[1]))], ['x &lt;= y?'])['x &lt;= y?'])
    lower_door = d.and_(is_door, d.eq(above, code8))
    show = d.and_(d.node('Greater Or Equal To 0?', [('x', six)], ['x &gt;= 0?'])['x &gt;= 0?'], d.not_(lower_door))

    def draw(i):
        picture, sprites, index, err, count, rr, cc, top = i
        (rect,) = d.unb(d.idx(sprites, index), ['Rectangle'])
        t, b = d.unb(rect, ['top', 'bottom'])
        h = d.i32(d.sub(b, t))
        y0 = d.add2(d.mul(rr, d.i32c(TILE)), d.i32c(HUD_H))
        y = d.sel(d.eq(top, d.i32c(1)), y0, d.sub(d.add2(y0, d.i32c(TILE)), h))
        pos = d.bun(d.const(POS, '[0,0]'), [('X', d.mul(cc, d.i32c(TILE))), ('Y', y)])
        res = d.call('Sprite_Draw.vi', [('Picture', picture), ('Sprites', sprites), ('Index', index), ('Position', pos), ('error in', err)],
                     ['Picture out', 'error out'])
        return [res['Picture out'], res['error out'], d.inc(count)]

    pic2, err2, cnt2 = d.case(show, [p2_l, spr2, six, e2_l, c2_l, r2, c, d.idx(top2, code)], [
        ('True', draw),
        ('False', lambda i: [i[0], i[3], i[4]]),
    ], 3)
    d.end()
    pic_row, err_row, cnt_row = close_reg(d, p2_r, pic2), close_reg(d, e2_r, err2), close_reg(d, c2_r, cnt2)
    d.end()
    d.indic('Picture out', 'picture', '', close_reg(d, p_r, pic_row), 4)
    d.indic('Count', 'int32', '0', close_reg(d, c_r, cnt_row), 6)
    d.err_out(close_reg(d, e_r, err_row))
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


def player_move():
    d = Doc('Player_Move.vi', 'Moves Claude by one tick. Ground: walk, conveyor push, jump, step onto a ladder or rope, fall off an edge, '
            'grab a pole over its hole. Air: gravity, head bump, landing on walls, thin floors (only from above) and ladder tops, '
            'grabbing a ladder (with Up/Down), a rope or a pole while falling. Ladder/rope: climb, stop at the top, floor or ceiling, '
            'step off sideways, jump off. Pole: slide down. Dead = landed more than the allowed height below the last firm stand. '
            'Positions are tenths of a pixel; all rules are in ARCHITEKTUR.md section 3.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    jump = d.ctrl('Jump', 'bool', 'false', 5, 'recommended')
    e = d.err_in()
    tiles, x10, y10, vy10, mode, facing, run, vert, stand = d.unb(st, ['Tiles', 'X10', 'Y10', 'VY10', 'Mode', 'Facing', 'Run', 'Vert', 'StandY'])
    n = max(TILE_CODE.values()) + 1
    L_SOL = d.const('array{int32}', lut({k: 1 for k in SOLID}, n), 'Solid')
    L_PLA = d.const('array{int32}', lut({k: 1 for k in PLATFORM}, n), 'Thin floor')
    L_LAD = d.const('array{int32}', lut({k: 1 for k in CLIMBABLE}, n), 'Ladder or rope')
    c = d.i32c
    err = [e]

    def tile(x, y):
        r = d.call('Tile_Read.vi', [('Tiles', tiles), ('X', x), ('Y', y), ('error in', err[0])], ['Tile', 'error out'])
        err[0] = r['error out']
        return d.i32(r['Tile'])

    def has(code, table): return d.gt(d.idx(table, code), c(0))
    def sol(code): return has(code, L_SOL)
    def pla(code): return has(code, L_PLA)
    def lad(code): return has(code, L_LAD)
    def pol(code): return d.eq(code, c(T['|']))
    def px(v10): return d.qr(v10, c(10))[1]
    def ge(a, b): return d.node('Greater Or Equal?', [('x', a), ('y', b)], ['x &gt;= y?'])['x &gt;= y?']
    def le(a, b): return d.node('Less Or Equal?', [('x', a), ('y', b)], ['x &lt;= y?'])['x &lt;= y?']

    def any_(*v):
        r = v[0]
        for k in v[1:]:
            r = d.or_(r, k)
        return r

    def all_(*v):
        r = v[0]
        for k in v[1:]:
            r = d.and_(r, k)
        return r

    def row_top(y): return d.mul(d.qr(y, c(TILE))[1], c(TILE))

    x, y = px(x10), px(y10)
    feet = d.add2(y, c(CLAUDE_H))
    m0, m1, m2 = d.eq(mode, c(0)), d.eq(mode, c(1)), d.eq(mode, c(2))
    no_jump = d.not_(jump)
    # ---- waagrecht (Boden und Luft), Foerderband nur am Boden
    under = tile(d.add2(x, c(16)), feet)
    belt = d.sel(d.eq(under, c(T['<'])), c(-BELT10), d.sel(d.eq(under, c(T['>'])), c(BELT10), c(0)))
    dx = d.add2(d.sel(d.or_(m0, m2), d.mul(run, c(WALK10)), c(0)), d.sel(m0, belt, c(0)))
    nx10 = d.add2(x10, dx)
    nx = px(nx10)
    lead = d.sel(d.gt(dx, c(0)), d.add2(nx, c(BOX_R)), d.add2(nx, c(BOX_L)))
    wall = any_(sol(tile(lead, d.add2(y, c(2)))), sol(tile(lead, d.add2(y, c(24)))), sol(tile(lead, d.sub(feet, c(2)))))
    xa10 = d.sel(d.and_(d.ne(dx, c(0)), wall), x10, nx10)
    xa = px(xa10)
    cx, lf, rt = d.add2(xa, c(16)), d.add2(xa, c(BOX_L)), d.add2(xa, c(BOX_R))
    snap10 = d.mul(d.qr(cx, c(TILE))[1], c(TILE * 10))
    # ---- Boden
    gL, gR, gC = tile(lf, feet), tile(rt, feet), tile(cx, feet)
    sup = any_(sol(gL), sol(gR), pla(gL), pla(gR), lad(gC))
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
    ay = px(ay10)
    afeet = d.add2(ay, c(CLAUDE_H))
    rising = d.lt(vy, c(0))
    bump = d.and_(rising, d.or_(sol(tile(lf, ay)), sol(tile(rt, ay))))
    a_top = row_top(afeet)
    crossed = d.and_(le(feet, a_top), ge(afeet, a_top))
    aL, aR, aC = tile(lf, afeet), tile(rt, afeet), tile(cx, afeet)
    lad_top = d.and_(lad(aC), d.not_(lad(tile(cx, d.sub(afeet, c(TILE))))))
    land = all_(d.not_(rising), crossed, any_(sol(aL), sol(aR), pla(aL), pla(aR), lad_top))
    land_y = d.sub(a_top, c(CLAUDE_H))
    mid = tile(cx, d.add2(ay, c(24)))
    falling = d.gt(vy, c(0))
    grab_l = d.and_(lad(mid), d.or_(d.ne(vert, c(0)), d.and_(d.eq(mid, c(T[':'])), falling)))
    grab_p = d.and_(pol(mid), falling)
    grab = d.and_(d.not_(land), d.or_(grab_l, grab_p))
    a_mode = d.sel(land, c(0), d.sel(grab_l, c(1), d.sel(grab_p, c(3), c(2))))
    a_y10 = d.sel(land, d.mul(land_y, c(10)), d.sel(bump, y10, ay10))
    a_vy = d.sel(any_(land, bump, grab), c(0), vy)
    a_x10 = d.sel(grab, snap10, xa10)
    dead = all_(m2, land, d.gt(d.sub(land_y, stand), c(MAX_FALL)))
    # ---- Leiter / Seil
    ly10 = d.add2(y10, d.mul(vert, c(CLIMB10)))
    ly = px(ly10)
    lfeet = d.add2(ly, c(CLAUDE_H))
    up, down = d.eq(vert, c(-1)), d.eq(vert, c(1))
    ceiling = d.and_(up, sol(tile(cx, ly)))
    l_above = d.sub(lfeet, c(2))
    at_top = all_(up, d.not_(ceiling), d.not_(lad(tile(cx, l_above))))
    top_y = d.sub(d.add2(row_top(l_above), c(TILE)), c(CLAUDE_H))
    floor = d.and_(down, sol(tile(cx, lfeet)))
    floor_y = d.sub(row_top(lfeet), c(CLAUDE_H))
    rope_end = all_(down, d.not_(lad(tile(cx, l_above))), d.not_(lad(tile(cx, lfeet))))
    step_off = d.and_(d.ne(run, c(0)), d.eq(vert, c(0)))
    l_mode = d.sel(jump, c(2), d.sel(d.or_(at_top, floor), c(0), d.sel(d.or_(rope_end, step_off), c(2), c(1))))
    l_y10 = d.sel(at_top, d.mul(top_y, c(10)), d.sel(floor, d.mul(floor_y, c(10)), d.sel(ceiling, y10, ly10)))
    l_vy = d.sel(jump, c(JUMP10), c(0))
    # ---- Rutschstange
    py10 = d.add2(y10, c(SLIDE10))
    py = px(py10)
    pfeet = d.add2(py, c(CLAUDE_H))
    p_floor = sol(tile(cx, pfeet))
    p_end = d.and_(d.not_(pol(tile(cx, d.add2(py, c(24))))), d.not_(pol(tile(cx, pfeet))))
    p_mode = d.sel(p_floor, c(0), d.sel(p_end, c(2), c(3)))
    p_y10 = d.sel(p_floor, d.mul(d.sub(row_top(pfeet), c(CLAUDE_H)), c(10)), py10)

    # ---- zusammenfuehren
    def pick(g, l, a, p): return d.sel(m0, g, d.sel(m1, l, d.sel(m2, a, p)))
    n_mode = pick(g_mode, l_mode, a_mode, p_mode)
    n_x10 = pick(g_x10, x10, a_x10, x10)
    n_y10 = pick(g_y10, l_y10, a_y10, p_y10)
    n_vy = pick(g_vy, l_vy, a_vy, c(0))
    n_stand = d.sel(d.eq(n_mode, c(2)), stand, px(n_y10))
    n_face = d.sel(d.gt(run, c(0)), c(0), d.sel(d.lt(run, c(0)), c(1), facing))
    out = d.bun(st, [('X10', n_x10), ('Y10', n_y10), ('VY10', n_vy), ('Mode', n_mode), ('Facing', n_face), ('StandY', n_stand), ('Dead', dead)])
    d.indic('State out', STATE, STATE_V, out, 4)
    d.err_out(err[0])
    d.write()


def room_change():
    d = Doc('Room_Change.vi', 'Changes the room when the middle of Claude leaves the playfield: left/right to the neighbour in the same depth, '
            'up/down to the room above/below. Sets Room and Tiles, moves the position by one room size, keeps the fall height across '
            'rooms and remembers the arrival as restart point. Without a neighbour nothing changes.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 5)
    e = d.err_in()
    c = d.i32c
    x10, y10, room, stand, mode = d.unb(st, ['X10', 'Y10', 'Room', 'StandY', 'Mode'])
    cx = d.add2(d.qr(x10, c(10))[1], c(16))
    cy = d.add2(d.qr(y10, c(10))[1], c(24))
    ge = lambda a, b: d.node('Greater Or Equal?', [('x', a), ('y', b)], ['x &gt;= y?'])['x &gt;= y?']
    dc = d.sel(d.lt(cx, c(0)), c(-1), d.sel(ge(cx, c(W)), c(1), c(0)))
    dd = d.sel(d.lt(cy, c(0)), c(-1), d.sel(ge(cy, c(FIELD_H)), c(1), c(0)))
    depth, column = d.unb(d.idx(rooms, room), ['Depth', 'Column'])
    want_d, want_c = d.add2(depth, dd), d.add2(column, dc)
    none = c(-1)
    lp = d.begin('For Loop', 'count="@i.v" maxin="" maxout=""')
    i = f'{lp}i.v'
    r = d.tunnel_in(1, rooms, 'index')
    wd, wc = d.tunnel_in(2, want_d), d.tunnel_in(3, want_c)
    f_l, f_r = shiftreg(d, lp, none)
    d2, c2 = d.unb(r, ['Depth', 'Column'])
    f2 = d.sel(d.and_(d.eq(d2, wd), d.eq(c2, wc)), i, f_l)
    d.end()
    found = close_reg(d, f_r, f2)
    change = d.and_(d.or_(d.ne(dc, c(0)), d.ne(dd, c(0))), ge(found, c(0)))
    (new_tiles,) = d.unb(d.idx(rooms, found), ['Tiles'])
    nx10 = d.sub(x10, d.mul(dc, c(W * 10)))
    ny10 = d.sub(y10, d.mul(dd, c(FIELD_H * 10)))
    moved = d.bun(st, [('Room', found), ('Tiles', new_tiles), ('X10', nx10), ('Y10', ny10), ('StandY', d.sub(stand, d.mul(dd, c(FIELD_H)))),
                       ('EntryX10', nx10), ('EntryY10', ny10), ('EntryMode', mode)])
    d.indic('State out', STATE, STATE_V, d.sel(change, moved, st), 4)
    d.indic('Changed', 'bool', 'false', change, 6)
    d.err_out(e)
    d.write()


def game_start():
    d = Doc('Game_Start.vi', 'Starts a game: loads the whole world (World_Load) and returns the first state: Claude stands on the start '
            f'tile P of the first room with {LIVES} lives.')
    e = d.err_in()
    c = d.i32c
    wl = d.call('World_Load.vi', [('error in', e)], ['Rooms', '-Grid', 'error out'])
    (tiles,) = d.unb(d.idx(wl['Rooms'], c(0)), ['Tiles'])
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
    st = d.bun(d.const(STATE, STATE_V), [('Tiles', tiles), ('X10', x10), ('Y10', y10), ('StandY', y), ('EntryX10', x10), ('EntryY10', y10),
                                         ('Lives', c(LIVES))])
    d.indic('State', STATE, STATE_V, st, 4)
    d.indic('Rooms', ROOMS, '[]', wl['Rooms'], 6)
    d.err_out(wl['error out'])
    d.write()


def game_step():
    d = Doc('Game_Step.vi', 'One game tick: applies the key (Left/Right/Release set Run, Up/Down/ReleaseV set Vert, Jump, Quit), moves Claude '
            '(Player_Move), handles a deadly fall (one life less, back to the arrival point of the room) and changes the room '
            '(Room_Change). Key values: ' + ', '.join(f'{i} {k}' for i, k in enumerate(KEYS)) + '.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    key = d.ctrl('Key', KEY, '0', 5, 'recommended')
    rooms = d.ctrl('Rooms', ROOMS, '[]', 7)
    e = d.err_in()
    c = d.i32c
    k = d.i32(key)
    is_ = lambda name: d.eq(k, c(IN[name]))
    run, vert, quit_, tick = d.unb(st, ['Run', 'Vert', 'Quit', 'Tick'])
    run2 = d.sel(is_('Left'), c(-1), d.sel(is_('Right'), c(1), d.sel(is_('Release'), c(0), run)))
    vert2 = d.sel(is_('Up'), c(-1), d.sel(is_('Down'), c(1), d.sel(is_('ReleaseV'), c(0), vert)))
    st1 = d.bun(st, [('Run', run2), ('Vert', vert2), ('Quit', d.or_(quit_, is_('Quit'))), ('Tick', d.inc(tick))])
    pm = d.call('Player_Move.vi', [('State', st1), ('Jump', is_('Jump')), ('error in', e)], ['State out', 'error out'])
    dead, ex, ey, em, lives = d.unb(pm['State out'], ['Dead', 'EntryX10', 'EntryY10', 'EntryMode', 'Lives'])
    back = d.bun(pm['State out'], [('X10', ex), ('Y10', ey), ('VY10', c(0)), ('Mode', em), ('StandY', d.qr(ey, c(10))[1]),
                                   ('Lives', d.sub(lives, c(1))), ('Dead', d.const('bool', 'false'))])
    st2 = d.sel(dead, back, pm['State out'])
    rc = d.call('Room_Change.vi', [('State', st2), ('Rooms', rooms), ('error in', pm['error out'])], ['State out', '-Changed', 'error out'])
    d.indic('State out', STATE, STATE_V, rc['State out'], 4)
    d.err_out(rc['error out'])
    d.write()


# ------------------------------------------------------------------ Bild eines Spielzustands
def frame_draw():
    d = Doc('Frame_Draw.vi', 'Draws one frame for a picture control that never erases. New room: loads its background and draws the whole '
            f'screen (HUD, room, objects, Claude). Otherwise: renews one block of {BLOCK_COLS} x {BLOCK_ROWS} tiles around the last three '
            'positions of Claude (Block_Cut) with all objects and Claude. In both cases the result is composed invisibly into one pixmap '
            'and drawn in one go (no flicker, no seams). Memory keeps the drawn room, its background and the last positions.')
    st = d.ctrl('State', STATE, STATE_V, 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 7)
    hud = d.ctrl('Hud', IMG, IMG_V, 9)
    mem = d.ctrl('Memory', RMEM, RMEM_V, 1)
    e = d.err_in()
    c = d.i32c
    room, x10, y10, vy, mode, facing, run, tick, tiles = d.unb(st, ['Room', 'X10', 'Y10', 'VY10', 'Mode', 'Facing', 'Run', 'Tick', 'Tiles'])
    m_room, bg, x1, y1, x2, y2 = d.unb(mem, ['Room', 'Background', 'X1', 'Y1', 'X2', 'Y2'])
    x, y = d.qr(x10, c(10))[1], d.qr(y10, c(10))[1]
    new_room = d.ne(room, m_room)

    def whole(a):
        rooms_, room_, hud_, bg_, err, xs, ys = a
        (rid,) = d.unb(d.idx(rooms_, room_), ['ID'])
        name = d.node('Concatenate Strings', [('string', d.const('string', 'room_0_')), ('string', rid), ('string', d.const('string', '.png'))],
                      ['concatenated string'])['concatenated string']
        il = d.call('Image_Load.vi', [('File name', name), ('error in', err)], ['Image', 'error out'])
        p1 = d.call('Draw Flattened Pixmap.vi', [('image data', hud_), ('picture', '')], ['new picture'])['new picture']
        p2 = d.call('Image_Draw.vi', [('Picture', p1), ('Image', il['Image']), ('Position', d.const(POS, f'[0,{HUD_H}]')),
                                      ('error in', il['error out'])], ['Picture out', 'error out'])
        return [p2['Picture out'], p2['error out'], il['Image'], d.const(RECT, f'[0,0,{W},{H}]', 'Whole screen')]

    def part(a):
        rooms_, room_, hud_, bg_, err, xs, ys = a

        def lowest(v):
            px0, px1, px2 = (d.idx(v, d.i32c(k)) for k in range(3))
            m = d.sel(d.lt(px1, px0), px1, px0)
            return d.sel(d.lt(px2, m), px2, m)

        col = d.node('Decrement', [('x', d.qr(lowest(xs), c(TILE))[1])], ['x-1'])['x-1']
        row = d.node('Decrement', [('x', d.qr(lowest(ys), c(TILE))[1])], ['x-1'])['x-1']
        bc = d.call('Block_Cut.vi', [('Image', bg_), ('Column', col), ('Row', row), ('Offset Y', c(HUD_H)), ('Columns', c(BLOCK_COLS)),
                                     ('Rows', c(BLOCK_ROWS)), ('error in', err)], ['Block', 'error out'])
        p0 = d.call('Draw Flattened Pixmap.vi', [('image data', bc['Block']), ('picture', '')], ['new picture'])['new picture']
        (area,) = d.unb(bc['Block'], ['Rectangle'])
        return [p0, bc['error out'], bg_, area]

    xs = d.node('Build Array', [('element', x), ('element', x1), ('element', x2)], ['appended array'])['appended array']
    ys = d.node('Build Array', [('element', y), ('element', y1), ('element', y2)], ['appended array'])['appended array']
    pic, err, bg2, area = d.case(new_room, [rooms, room, hud, bg, e, xs, ys], [('True', whole), ('False', part)], 4)
    rd = d.call('Room_Draw.vi', [('Picture', pic), ('Sprites', spr), ('Tiles', tiles), ('error in', err)], ['Picture out', '-Count', 'error out'])
    # Bild von Claude
    side = d.mul(facing, c(SPR_SIDE_STEP))
    walk = d.inc(d.qr(d.qr(d.i32(tick), c(6))[1], c(4))[0])
    on_ground = d.add2(side, d.sel(d.ne(run, c(0)), walk, c(0)))
    in_air = d.add2(side, d.sel(d.lt(vy, c(0)), c(5), c(6)))
    climbing = d.add2(c(SPR['claude_climb_0']), d.qr(d.qr(y, c(8))[1], c(2))[0])
    index = d.sel(d.eq(mode, c(0)), on_ground, d.sel(d.eq(mode, c(1)), climbing, d.sel(d.eq(mode, c(2)), in_air, c(SPR['claude_slide']))))
    pos = d.bun(d.const(POS, '[0,0]'), [('X', x), ('Y', d.add2(y, c(HUD_H)))])
    sd = d.call('Sprite_Draw.vi', [('Picture', rd['Picture out']), ('Sprites', spr), ('Index', d.add2(index, c(SPR['claude_r_stand']))),
                                   ('Position', pos), ('error in', rd['error out'])], ['Picture out', 'error out'])
    pm = d.call('Picture to Pixmap.vi', [('Background Color', ''), ('depth', c(24)), ('rect', area), ('picture', sd['Picture out'])],
                ['image data', '-new picture'])['image data']
    out = d.call('Draw Flattened Pixmap.vi', [('image data', d.bun(pm, [('Rectangle', area)])), ('picture', '')], ['new picture'])['new picture']
    mem2 = d.bun(mem, [('Room', room), ('Background', bg2), ('X1', x), ('Y1', y), ('X2', d.sel(new_room, x, x1)), ('Y2', d.sel(new_room, y, y1))])
    d.indic('Picture', 'picture', '', out, 4)
    d.indic('Memory out', RMEM, RMEM_V, mem2, 6)
    d.err_out(sd['error out'])
    d.write()


# ------------------------------------------------------------------ App: Bausteine von Main.vi
def status(d, err):
    return d.unb(err, ['status'])[0]


def app_init():
    d = Doc('App_Init.vi', 'Start of Main: creates the key queue (UI to engine) and the notifier (game state for the picture loop) and '
            'returns both as Channels.')
    e = d.err_in()
    q = d.node('Obtain Queue', [('element data type', d.const(KEY, '0', 'Key type')), ('error in (no error)', e)],
               ['queue out', '-created new?', 'error out'])
    nt = d.node('Obtain Notifier', [('notification data type', d.const(STATE, STATE_V, 'State type')), ('error in (no error)', q['error out'])],
                ['notifier out', '-created new?', 'error out'])
    k = d.bun(d.const(CHANNELS, '[,]'), [('Keys', q['queue out']), ('Frames', nt['notifier out'])])
    d.indic('Channels', CHANNELS, '[,]', k, 4)
    d.err_out(nt['error out'])
    d.write()


def app_close():
    d = Doc('App_Close.vi', 'End of Main (after the engine and picture loops): releases the queue and the notifier. Errors of the loops come '
            'in through error in and are kept.')
    k = d.ctrl('Channels', CHANNELS, '[,]', 0)
    e = d.err_in()
    q, nt = d.unb(k, ['Keys', 'Frames'])
    r1 = d.node('Release Queue', [('queue', q), ('error in (no error)', e)], ['-queue name', '-remaining elements', 'error out'])
    r2 = d.node('Release Notifier', [('notifier', nt), ('error in (no error)', r1['error out'])], ['-notifier name', '-last notification', 'error out'])
    d.err_out(r2['error out'])
    d.write()


def window_setup():
    d = Doc('Window_Setup.vi', f'Sets up the window of Main: picture "Screen" at the top left with a fixed drawing area of {W} x {H}, never '
            'erasing; all other controls are moved to the right outside the visible area; '
            'the panel is sized to the screen.')
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
        pos = d.bun(d.const('cluster{int32.Left,int32.Top}', f'[{W + 40},40]', 'right of the screen'),
                    [('Top', d.add2(d.i32c(40), d.mul(kk, d.i32c(50))))])
        w = d.node('Property Node', [('reference', ref), ('error in (no error)', err), ('Position', pos)],
                   ['-reference out', 'error out'], extra='fields="write+Position" type="{LV.Control}"')
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
            'the key queue. Pressed: arrows, Space = Jump, Enter = Start, Esc = Quit; released: arrows = Release / ReleaseV. '
            'Quit (Stop button) also sends Quit. Quit out is true when the game shall end.')
    k = d.ctrl('Channels', CHANNELS, '[,]', 0)
    sc = d.ctrl('ScanCode', 'int32', '-1', 5)
    up = d.ctrl('Released', 'bool', 'false', 7, 'recommended')
    quit_ = d.ctrl('Quit', 'bool', 'false', 9, 'recommended')
    e = d.err_in()

    def lookup(table, name):
        codes = d.const('array{int32}', '[' + ','.join(str(code) for code, _ in table) + ']', f'ScanCodes {name}')
        keys = d.const(f'array{{{KEY}}}', '[' + ','.join(str(IN[v]) for _, v in table) + ']', f'Keys {name}')
        ix = d.node('Search 1D Array', [('1D array', codes), ('element', sc), ('start index (0)', '')], ['index of element'])['index of element']
        return d.idx(keys, ix)            # nicht gefunden (-1) -> 0 = None

    t = d.sel(up, lookup(KEYS_UP, 'released'), lookup(KEYS_DOWN, 'pressed'))
    t = d.sel(quit_, d.const(KEY, str(IN['Quit'])), t)
    q, = d.unb(k, ['Keys'])
    enq = d.node('Enqueue Element', [('queue', q), ('element', t), ('error in (no error)', e)], ['-queue out', '-timed out?', 'error out'])
    d.indic('Quit out', 'bool', 'false', d.eq(t, d.const(KEY, str(IN['Quit']))), 4)
    d.err_out(enq['error out'])
    d.write()


def engine_tick():
    d = Doc('Engine_Tick.vi', 'One game tick: takes at most one key from the queue, runs Game_Step and sends the new state to the picture '
            'loop. Stop on Quit or on an error.')
    k = d.ctrl('Channels', CHANNELS, '[,]', 0)
    st = d.ctrl('State', STATE, STATE_V, 5)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 7)
    e = d.err_in()
    q, nt = d.unb(k, ['Keys', 'Frames'])
    dq = d.node('Dequeue Element', [('queue', q), ('timeout in ms (-1)', d.const('int32', '0', 'do not wait')), ('error in (no error)', e)],
                ['-queue out', 'element', '-timed out?', 'error out'])
    gs = d.call('Game_Step.vi', [('State', st), ('Key', dq['element']), ('Rooms', rooms), ('error in', dq['error out'])],
                ['State out', 'error out'])
    sn = d.node('Send Notification', [('notifier', nt), ('notification', gs['State out']), ('error in (no error)', gs['error out'])],
                ['-notifier out', 'error out'])
    quit_, = d.unb(gs['State out'], ['Quit'])
    d.indic('State out', STATE, STATE_V, gs['State out'], 4)
    d.indic('Stop', 'bool', 'false', d.or_(quit_, status(d, sn['error out'])), 6)
    d.err_out(sn['error out'])
    d.write()


def render_frame():
    d = Doc('Render_Frame.vi', 'One frame: waits (at most 200 ms) for the next game state and draws it with Frame_Draw. Without a new state '
            'nothing visible is drawn and Memory stays. FPS from the time since the last frame. Stop on Quit or on an error.')
    k = d.ctrl('Channels', CHANNELS, '[,]', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    rooms = d.ctrl('Rooms', ROOMS, '[]', 7)
    hud = d.ctrl('Hud', IMG, IMG_V, 9)
    mem = d.ctrl('Memory', RMEM, RMEM_V, 1)
    last = d.ctrl('Last ms', 'uint32', '0', 2, 'recommended')
    e = d.err_in()
    nt, = d.unb(k, ['Frames'])
    wn = d.node('Wait on Notification', [('notifier', nt), ('timeout in ms (-1)', d.const('int32', '200', 'Timeout')), ('error in (no error)', e)],
                ['-notifier out', 'notification', 'timed out?', 'error out'])
    st = wn['notification']
    fd = d.call('Frame_Draw.vi', [('State', st), ('Sprites', spr), ('Rooms', rooms), ('Hud', hud), ('Memory', mem), ('error in', wn['error out'])],
                ['Picture', 'Memory out', 'error out'])
    # ohne neuen Zustand: ein Sprite weit ausserhalb des Bildes (zeichnet nichts Sichtbares)
    nothing = d.call('Sprite_Draw.vi', [('Picture', fd['Picture']), ('Sprites', spr), ('Index', d.i32c(0)), ('Position', d.const(POS, '[0,-2000]')),
                                        ('error in', fd['error out'])], ['-Picture out', 'error out'])
    idle = wn['timed out?']
    off = d.call('Draw Flattened Pixmap.vi', [('image data', d.bun(d.idx(spr, d.i32c(0)), [('Rectangle', d.const(RECT, '[0,-2000,32,-1952]'))])),
                                              ('picture', '')], ['new picture'])['new picture']
    quit_, = d.unb(st, ['Quit'])
    now = d.node('Tick Count (ms)', [], ['millisecond timer value'])['millisecond timer value']
    fps = d.node('Divide', [('x', d.const('double', '1000')), ('y', d.sub(now, last))], ['x/y'])['x/y']
    d.indic('Picture', 'picture', '', d.sel(idle, off, fd['Picture']), 4)
    d.indic('Memory out', RMEM, RMEM_V, d.sel(idle, mem, fd['Memory out']), 6)
    d.indic('FPS', 'double', '0', fps, 8)
    d.indic('Now ms', 'uint32', '0', now, 10)
    d.indic('Stop', 'bool', 'false', d.or_(d.and_(quit_, d.not_(idle)), status(d, nothing['error out'])), 13)
    d.err_out(nothing['error out'])
    d.write()


ALL = {f.__name__: f for f in (resource_path, room_load, world_load, tile_at, image_load, sprite_atlas_load, sprite_draw, image_draw,
                               room_draw, tile_cut, block_cut, tile_read, player_move, room_change, game_start, game_step,
                               frame_draw, app_init, app_close, window_setup, key_send, engine_tick, render_frame)}
if __name__ == '__main__':
    for name in (sys.argv[1:] or ALL):
        ALL[name]()

    # -------------------------------------------------------------- Build-Contract
    E = {"name": "error in", "type": "@Error", "conIdx": 11, "connection": "required"}
    EO = {"name": "error out", "type": "@Error", "conIdx": 15, "connection": "recommended"}

    def i(n, t, k, conn='required'): return {"name": n, "type": t, "conIdx": k, "connection": conn}
    def o(n, t, k): return {"name": n, "type": t, "conIdx": k, "connection": "recommended"}

    LV, RE, EN, AP = 'Source\\Level\\', 'Source\\Render\\', 'Source\\Engine\\', 'Source\\App\\'
    vis = [
        (LV, 'Resource_Path', 'Path Resources\\Subfolder\\File name', [], [i('File name', 'string', 0), i('Subfolder', 'string', 5), E],
         [o('Path', 'path', 4), EO]),
        (LV, 'Room_Load', 'Room text file -> tiles', [LV + 'Resource_Path.vi'], [i('Room ID', 'string', 0), E], [o('Tiles', '@Tiles', 4), EO]),
        (LV, 'World_Load', 'world.txt and all rooms', [LV + 'Resource_Path.vi', LV + 'Room_Load.vi'], [E],
         [o('Rooms', '@Rooms', 4), o('Grid', 'array.2{string}', 6), EO]),
        (LV, 'Tile_At', 'Tile under a point', [], [i('Tiles', '@Tiles', 0), i('X', 'int32', 5), i('Y', 'int32', 7), E], [o('Tile', 'uint8', 4), EO]),
        (RE, 'Image_Load', 'Load a PNG from Resources\\Images', [LV + 'Resource_Path.vi'], [i('File name', 'string', 0), E],
         [o('Image', '@ImageData', 4), EO]),
        (RE, 'SpriteAtlas_Load', 'Load the sprite atlas', [LV + 'Resource_Path.vi'], [E], [o('Sprites', '@Sprites', 4), EO]),
        (RE, 'Sprite_Draw', 'Draw a sprite at a position', [],
         [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('Index', 'int32', 7), i('Position', '@Position', 9), E],
         [o('Picture out', 'picture', 4), EO]),
        (RE, 'Image_Draw', 'Draw one image at a position', [],
         [i('Picture', 'picture', 0), i('Image', '@ImageData', 5), i('Position', '@Position', 7), E], [o('Picture out', 'picture', 4), EO]),
        (RE, 'Room_Draw', 'Draw the objects of a room from its tiles', [RE + 'Sprite_Draw.vi'],
         [i('Picture', 'picture', 0), i('Sprites', '@Sprites', 5), i('Tiles', '@Tiles', 7), E],
         [o('Picture out', 'picture', 4), o('Count', 'int32', 6), EO]),
        (RE, 'Tile_Cut', 'Cut one tile out of a room image', [],
         [i('Image', '@ImageData', 0), i('Column', 'int32', 5), i('Row', 'int32', 7), i('Offset Y', 'int32', 9), E],
         [o('Tile', '@ImageData', 4), EO]),
        (RE, 'Block_Cut', 'Cut a block of tiles out of a room image as one piece', [],
         [i('Image', '@ImageData', 0), i('Column', 'int32', 5), i('Row', 'int32', 7), i('Offset Y', 'int32', 9),
          i('Columns', 'int32', 1), i('Rows', 'int32', 2), E], [o('Block', '@ImageData', 4), EO]),
        (LV, 'Tile_Read', 'Tile under a point, clamped to the room', [], [i('Tiles', '@Tiles', 0), i('X', 'int32', 5), i('Y', 'int32', 7), E],
         [o('Tile', 'uint8', 4), EO]),
        (EN, 'Player_Move', 'Move Claude by one tick', [LV + 'Tile_Read.vi'], [i('State', '@State', 0), i('Jump', 'bool', 5, 'recommended'), E],
         [o('State out', '@State', 4), EO]),
        (EN, 'Room_Change', 'Change the room at the edge of the playfield', [], [i('State', '@State', 0), i('Rooms', '@Rooms', 5), E],
         [o('State out', '@State', 4), o('Changed', 'bool', 6), EO]),
        (EN, 'Game_Start', 'Load the world, first state', [LV + 'World_Load.vi'], [E], [o('State', '@State', 4), o('Rooms', '@Rooms', 6), EO]),
        (EN, 'Game_Step', 'One game tick', [EN + 'Player_Move.vi', EN + 'Room_Change.vi'],
         [i('State', '@State', 0), i('Key', 'uint16', 5, 'recommended'), i('Rooms', '@Rooms', 7), E], [o('State out', '@State', 4), EO]),
        (RE, 'Frame_Draw', 'Draw one frame of a game state', [RE + 'Image_Load.vi', RE + 'Image_Draw.vi', RE + 'Block_Cut.vi', RE + 'Room_Draw.vi',
                                                         RE + 'Sprite_Draw.vi'],
         [i('State', '@State', 0), i('Sprites', '@Sprites', 5), i('Rooms', '@Rooms', 7), i('Hud', '@ImageData', 9), i('Memory', '@RenderMemory', 1), E],
         [o('Picture', 'picture', 4), o('Memory out', '@RenderMemory', 6), EO]),
        (AP, 'App_Init', 'Create queue and notifier', [], [E], [o('Channels', '@Channels', 4), EO]),
        (AP, 'App_Close', 'Release queue and notifier', [], [i('Channels', '@Channels', 0), E], [EO]),
        (AP, 'Window_Setup', 'Set up the window of Main', [], [i('VI', 'ref{LV.VI}', 0), E], [EO]),
        (AP, 'Key_Send', 'Translate a key and queue it', [],
         [i('Channels', '@Channels', 0), i('ScanCode', 'int32', 5), i('Released', 'bool', 7, 'recommended'), i('Quit', 'bool', 9, 'recommended'), E],
         [o('Quit out', 'bool', 4), EO]),
        (AP, 'Engine_Tick', 'One game tick with queue and notifier', [EN + 'Game_Step.vi'],
         [i('Channels', '@Channels', 0), i('State', '@State', 5), i('Rooms', '@Rooms', 7), E], [o('State out', '@State', 4), o('Stop', 'bool', 6), EO]),
        (AP, 'Render_Frame', 'Wait for a state and draw it', [RE + 'Frame_Draw.vi', RE + 'Sprite_Draw.vi'],
         [i('Channels', '@Channels', 0), i('Sprites', '@Sprites', 5), i('Rooms', '@Rooms', 7), i('Hud', '@ImageData', 9), i('Memory', '@RenderMemory', 1),
          i('Last ms', 'uint32', 2, 'recommended'), E],
         [o('Picture', 'picture', 4), o('Memory out', '@RenderMemory', 6), o('FPS', 'double', 8), o('Now ms', 'uint32', 10), o('Stop', 'bool', 13), EO]),
    ]
    contract = {
        "application": "Gold Hunter",
        "root": "..",
        "project": "GoldHunter.lvproj",
        "panePattern": 4833,
        "types": {"Error": ERR, "Tiles": TILES, "Position": POS, "ImageData": IMG, "Sprites": SPRITES, "Rooms": ROOMS, "State": STATE, "RenderMemory": RMEM, "Channels": CHANNELS},
        "vis": [{"path": f + n + '.vi', "builder": f.split('\\')[1].lower(), "purpose": p, "calls": c, "inputs": ins, "outputs": outs}
                for f, n, p, c, ins, outs in vis],
    }
    json.dump(contract, open(os.path.join(HERE, 'build-contract.json'), 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('contract:', len(contract['vis']), 'VIs')
