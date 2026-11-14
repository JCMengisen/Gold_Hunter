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
            f'keys, gold, torch, enemies and the start figure. Playfield starts {HUD_H} px below the top (HUD). Floors, conveyors and doors '
            'are aligned to the top of their tile (a door only at its top tile), everything else stands on the floor of its tile. '
            'Count = number of sprites drawn.')
    pic = d.ctrl('Picture', 'picture', '', 0)
    spr = d.ctrl('Sprites', SPRITES, '[]', 5)
    tiles = d.ctrl('Tiles', TILES, '[]', 7)
    e = d.err_in()
    n = max(TILE_CODE.values()) + 1
    sprite_of = d.const('array{int32}', lut({k: SPR[v] for k, v in TILE_SPRITE.items()}, n), 'Sprite per tile value')
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


ALL = {f.__name__: f for f in (resource_path, room_load, world_load, tile_at, image_load, sprite_atlas_load, sprite_draw, image_draw,
                               room_draw)}
if __name__ == '__main__':
    for name in (sys.argv[1:] or ALL):
        ALL[name]()

    # -------------------------------------------------------------- Build-Contract
    E = {"name": "error in", "type": "@Error", "conIdx": 11, "connection": "required"}
    EO = {"name": "error out", "type": "@Error", "conIdx": 15, "connection": "recommended"}

    def i(n, t, k, conn='required'): return {"name": n, "type": t, "conIdx": k, "connection": conn}
    def o(n, t, k): return {"name": n, "type": t, "conIdx": k, "connection": "recommended"}

    LV, RE = 'Source\\Level\\', 'Source\\Render\\'
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
    ]
    contract = {
        "application": "Gold Hunter",
        "root": "..",
        "project": "GoldHunter.lvproj",
        "panePattern": 4833,
        "types": {"Error": ERR, "Tiles": TILES, "Position": POS, "ImageData": IMG, "Sprites": SPRITES, "Rooms": ROOMS},
        "vis": [{"path": f + n + '.vi', "builder": f.split('\\')[1].lower(), "purpose": p, "calls": c, "inputs": ins, "outputs": outs}
                for f, n, p, c, ins, outs in vis],
    }
    json.dump(contract, open(os.path.join(HERE, 'build-contract.json'), 'w', encoding='utf-8'), indent=2, ensure_ascii=False)
    print('contract:', len(contract['vis']), 'VIs')
