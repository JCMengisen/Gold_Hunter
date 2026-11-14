# Gold Hunter - zeichnet alle Grafiken (Pixel-Art im Raster 640 x 360, 2-fach vergroessert gespeichert = 1280 x 720):
#   Resources\Images\room_<schema>_<id>.png        Raum-Hintergrund 1280 x 640, hell
#   Resources\Images\room_<schema>_<id>_dark.png   derselbe Raum ohne Fackel (fast schwarz)
#   Resources\Images\room_<schema>_<id>_dim.png    halbdunkel: Rand des Lichtkreises um Claude
#   Resources\Images\hud.png  title.png            HUD 1280 x 80, Titelbild 1280 x 720
#   Resources\Sprites\<name>.png + sprites.txt     Sprites (Zeile in sprites.txt = Index)
#   Resources\Preview\*.png                        Vorschauen
# Die Geometrie kommt aus gh_levels.py. Aufruf: python make_assets.py
import os
import time
from PIL import Image, ImageDraw, ImageChops
import gh_levels
from gh_levels import ROOMS, WORLD, COLS, ROWS

RES = os.path.join(gh_levels.ROOT, 'Resources')
for _d in ('Images', 'Sprites', 'Preview'):
    os.makedirs(os.path.join(RES, _d), exist_ok=True)
T, S = 16, 2                      # Kachel in Art-Pixeln, Vergroesserung (2-fach = 1280 x 720)
W, RH, HUD_H = COLS * T, ROWS * T, 40


def rgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def rnd(a, b, seed=0):
    v = (a * 73856093) ^ (b * 19349663) ^ (seed * 83492791)
    v = (v ^ (v >> 13)) * 1274126177
    return ((v ^ (v >> 16)) & 0xFFFF) / 65535.0


def big(im):
    return im.resize((im.width * S, im.height * S), Image.NEAREST)


def save(im, *path):
    p = os.path.join(RES, *path)
    for _ in range(20):               # eben gelesene Dateien sind unter Windows manchmal kurz gesperrt
        try:
            im.save(p)
            return
        except OSError:
            time.sleep(0.25)
    im.save(p)


# ------------------------------------------------------------------ Schrift 5 x 7
FONT = {
    'A': '.###.#...##...#######...##...##...#', 'B': '####.#...##...#####.#...##...#####.',
    'C': '.###.#...##....#....#....#...#.###.', 'D': '####.#...##...##...##...##...#####.',
    'E': '######....#....####.#....#....#####', 'F': '######....#....####.#....#....#....',
    'G': '.###.#...##....#.####...##...#.###.', 'H': '#...##...##...#######...##...##...#',
    'I': '.###...#....#....#....#....#...###.', 'J': '..###...#....#....#....#.#..#..##..',
    'K': '#...##..#.#.#..##...#.#..#..#.#...#', 'L': '#....#....#....#....#....#....#####',
    'M': '#...###.###.#.##.#.##...##...##...#', 'N': '#...###..##.#.##..###...##...##...#',
    'O': '.###.#...##...##...##...##...#.###.', 'P': '####.#...##...#####.#....#....#....',
    'Q': '.###.#...##...##...##.#.##..#..##.#', 'R': '####.#...##...#####.#.#..#..#.#...#',
    'S': '.#####....#.....###.....#....#####.', 'T': '#####..#....#....#....#....#....#..',
    'U': '#...##...##...##...##...##...#.###.', 'V': '#...##...##...##...##...#.#.#...#..',
    'W': '#...##...##...##.#.##.#.###.###...#', 'X': '#...##...#.#.#...#...#.#.#...##...#',
    'Y': '#...##...#.#.#...#....#....#....#..', 'Z': '#####....#...#...#...#...#....#####',
    '0': '.###.#...##..###.#.###..##...#.###.', '1': '..#...##....#....#....#....#...###.',
    '2': '.###.#...#....#...#...#...#...#####', '3': '####.....#....#.###.....#....#####.',
    '4': '...#...##..#.#.#..#.#####...#....#.', '5': '######....####.....#....##...#.###.',
    '6': '.###.#....#....####.#...##...#.###.', '7': '#####....#...#...#...#....#....#...',
    '8': '.###.#...##...#.###.#...##...#.###.', '9': '.###.#...##...#.####....#....#.###.',
    ' ': '.' * 35, '.': '.' * 30 + '..#..', ':': '.' * 10 + '..#..' + '.' * 10 + '..#..' + '.' * 5,
    '-': '.' * 15 + '.###.' + '.' * 15, '!': '..#....#....#....#....#.......' + '..#..',
    '=': '.' * 10 + '#####' + '.' * 5 + '#####' + '.' * 10,
}
CHARSET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .:-!='
assert all(len(v) == 35 for v in FONT.values()) and all(c in FONT for c in CHARSET)


def text_w(s, scale=1):
    return len(s) * 6 * scale - scale


def text(im, x, y, s, col, scale=1, shadow=None, col2=None):
    """col2: Farbe der unteren Haelfte (Zweiton)"""
    d = ImageDraw.Draw(im)
    for passes in ((shadow, scale), (None, 0)):
        if passes[0] is None and passes[1]:
            continue
        off = passes[1]
        for i, ch in enumerate(s):
            g = FONT[ch]
            for k in range(35):
                if g[k] == '#':
                    gx, gy = x + (i * 6 + k % 5) * scale + off, y + (k // 5) * scale + off
                    c = passes[0] if off else (col2 if col2 and k // 5 >= 4 else col)
                    d.rectangle([gx, gy, gx + scale - 1, gy + scale - 1], fill=c)


# ------------------------------------------------------------------ Sprites aus Zeichen-Bildern
PAL = {
    'Y': '#F2C230', 'y': '#C8961E', 'W': '#FFF7C0', 'S': '#F0B890', 's': '#C98A66', 'E': '#20181C', 'H': '#5A3620',
    'O': '#D97757', 'o': '#A9502F', 'P': '#6B4A2B', 'T': '#3B5FA8', 't': '#28427A', 'K': '#2A1E1A', 'L': '#3A2A20',
    'V': '#7B3FA0', 'v': '#4E2468', 'p': '#B88AD8', 'R': '#FF4040',
    'B': '#E8E4D0', 'b': '#B0A890', 'D': '#18141C',
    'F': '#E8481C', 'f': '#FF9A1C', 'G': '#FFE860', 'M': '#8A5A2C', 'm': '#5E3A1A',
}
PAL = {k: rgb(v) + (255,) for k, v in PAL.items()}
DARK = (16, 12, 20, 255)


def sprite(rows, pal=None, width=16):
    pal = pal or PAL
    im = Image.new('RGBA', (width, len(rows)), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        assert len(row) == width, (y, row, len(row))
        for x, ch in enumerate(row):
            if ch != '.':
                im.putpixel((x, y), pal[ch])
    return im


def outline(im, col=DARK):
    out = im.copy()
    for y in range(im.height):
        for x in range(im.width):
            if im.getpixel((x, y))[3] == 0:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    if 0 <= x + dx < im.width and 0 <= y + dy < im.height and im.getpixel((x + dx, y + dy))[3]:
                        out.putpixel((x, y), col)
                        break
    return out


def mirror(im):
    return im.transpose(Image.FLIP_LEFT_RIGHT)


# --- Claude: Helm mit Lampe, orange Jacke, Rucksack, blaue Hose. Profil nach rechts, 16 x 24.
HEAD = ['................',
        '.....YYYYY......',
        '....YYYYYYY.....',
        '...yYYYYYYYWW...',
        '...yYYYYYYYWW...',
        '..yyyyyyyyyyyy..',
        '....HSSSSSS.....',
        '....HSSSESSs....',
        '....HSSSSSSS....',
        '.....SSSSSs.....']
TORSO = ['....POOOOOO.....',
         '...PPOOOOOOo....',
         '...PPOOOOOOo....',
         '...PPOOOOOOo....',
         '...PPOOOOOOo....',
         '....POOOOOO.....',
         '....LLLLLLL.....',
         '....TTTTTTT.....']
LEGS = {
    'stand': ['....TTTTTTT.....', '....TTT.TTT.....', '....TTT.TTT.....', '....TTt.TTt.....', '....KKK.KKK.....', '....KKKKKKKK....'],
    'wide': ['....TTTTTTT.....', '...TTTT.TTTT....', '..TTT.....TTT...', '..TTt.....TTt...', '.KKK......KKK...', '.KKKK.....KKKK..'],
    'pass': ['....TTTTTTT.....', '....TTTTTTT.....', '.....TTTTT......', '.....TTtTT......', '.....KKKKK......', '.....KKKKKK.....'],
    'tuck': ['....TTTTTTT.....', '...TTTT.TTTT....', '..TTT....TTTT...', '..KKK.....TTt...', '..........KKK...', '................'],
}
ARMS = {    # (x, y, Farbe) ueber dem Rumpf
    'down': [(7, 11, 'o'), (7, 12, 'o'), (7, 13, 'o'), (7, 14, 'S')],
    'fwd': [(8, 11, 'o'), (9, 12, 'o'), (10, 12, 'o'), (11, 12, 'S'), (12, 12, 'S')],
    'back': [(6, 11, 'o'), (5, 12, 'o'), (4, 13, 'o'), (3, 13, 'S')],
    'up': [(9, 10, 'o'), (10, 10, 'o'), (11, 9, 'o'), (12, 8, 'S'), (12, 7, 'S')],
}
CLIMB = ['................',
         '.....YYYYYY.....',
         '....YYYYYYYY....',
         '....YYYYYYYY....',
         '....yYYYYYYy....',
         '...yyyyyyyyyy...',
         '....HHHHHHHH....',
         '..S.HHHHHHHH....',
         '..o.sHHHHHHs....',
         '..o..ssssss.....',
         '..oOOOOOOOOOO...',
         '...OOPPPPPPOOo..',
         '...OOPPPPPPOOo..',
         '...OOPPPPPPOOo..',
         '...OOPPPPPPOOS..',
         '....OOOOOOOO....',
         '....LLLLLLLL....',
         '....TTTTTTTT....',
         '....TTTTTTTT....',
         '....TTT..TTT....',
         '....TTt..TTT....',
         '....KKK..TTt....',
         '.........KKK....',
         '.........KKK....']
SLIDE = CLIMB[:7] + ['..S.HHHHHHHH.S..', '..o.sHHHHHHs.o..', '..o..ssssss..o..', '..oOOOOOOOOOOo..',
                     '...OOPPPPPPOO...', '...OOPPPPPPOO...', '...OOPPPPPPOO...', '...OOPPPPPPOO...'] + CLIMB[15:19] + \
    ['.....TTTTTT.....', '.....TTttTT.....', '.....TTttTT.....', '.....KKKKKK.....', '.....KKKKKK.....']
DEAD = ['................'] * 17 + ['......W.........',
                                    '..W.......W.....',
                                    '.....YYYYY......',
                                    '....YYYYYYYWW...',
                                    '...yYYYYYYYWW...',
                                    '..yyyyyyyyyyyy..',
                                    '...ssssssssss...']


def claude(legs, arm):
    im = sprite(HEAD + TORSO + LEGS[legs])
    for x, y, ch in ARMS[arm]:
        im.putpixel((x, y), PAL[ch])
    return im


def flash(im):
    out = im.copy()
    for y in range(im.height):
        for x in range(im.width):
            if im.getpixel((x, y))[3]:
                out.putpixel((x, y), (255, 255, 255, 255))
    return out


# --- Gegner
def spider(frame):
    top = ['................'] * 5 + ['..p..........p..',
                                      '.p.p..VVVV..p.p.',
                                      '.p..pVVVVVVp..p.',
                                      'p..ppVRVVRVpp..p',
                                      'p.p..VVVVVV..p.p',
                                      '..p.pvVVVVvp.p..',
                                      '.p..p.vvvv.p..p.']
    legs = [['.p..p......p..p.', '.p..p......p..p.', 'p...p......p...p', 'p..p........p..p'],
            ['p..p........p..p', 'p..p........p..p', '.p.p........p.p.', '.p..p......p..p.']][frame]
    return sprite(top + legs)


def snake(frame):
    g, gd, ye, wh, red = rgb('#3FB54A') + (255,), rgb('#237A30') + (255,), rgb('#E8D44A') + (255,), (255, 255, 255, 255), rgb('#FF4040') + (255,)
    body = ['....GGGGGGGG....', '..GGgGGYGGgGGG..', '.GGGGYGGGGYGGGG.', '.GgGGGGgGGGGGgG.', '..GGGGGGGGGGGG..']
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    pal = {'G': g, 'g': gd, 'Y': ye}
    for y, row in enumerate(body):
        for x, ch in enumerate(row):
            if ch != '.':
                im.putpixel((x, 11 + y), pal[ch])
    shift = (-3, 0, 3)[frame]
    for y in range(5, 11):                      # Hals
        x = 7 + round(shift * (10 - y) / 5)
        im.putpixel((x, y), g)
        im.putpixel((x + 1, y), gd)
    hx = 5 + shift
    d = ImageDraw.Draw(im)
    d.rectangle([hx, 2, hx + 5, 5], fill=g)
    d.rectangle([hx + 1, 1, hx + 4, 1], fill=g)
    im.putpixel((hx + 1, 3), wh)
    im.putpixel((hx + 4, 3), wh)
    d.line([hx + 1, 5, hx + 4, 5], fill=gd)
    tx = hx + (6 if frame != 0 else -1)         # Zunge zur Seite, auf die der Kopf zeigt
    im.putpixel((max(0, min(15, tx)), 5), red)
    im.putpixel((max(0, min(15, tx + (1 if frame != 0 else -1))), 4), red)
    return im


SKULL = ['................',
         '....BBBBBBBB....',
         '...BBBBBBBBBB...',
         '..BBBBBBBBBBBB..',
         '..BBBBBBBBBBBB..',
         '..BDDDBBBBDDDB..',
         '..BDDDBBBBDDDB..',
         '..BDDDBBBBDDDB..',
         '..BBBBBDDBBBBB..',
         '..bBBBBDDBBBBb..',
         '...bBBBBBBBBb...',
         '....BDBDBDBB....',
         '....BBBBBBBB....',
         '....bDBDBDBb....',
         '.....bbbbbb.....',
         '................']


# --- Gegenstaende
def coin(frame):
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    w = (10, 6, 2, 6)[frame]
    x0, x1 = 8 - w // 2, 8 + w // 2 - 1
    gold, edge, hi = rgb('#F8C830'), rgb('#B07A10'), rgb('#FFF0A0')
    if w == 2:
        d.rectangle([x0, 4, x1, 13], fill=gold, outline=None)
        d.line([x0, 4, x0, 13], fill=hi)
    else:
        d.ellipse([x0, 4, x1, 13], fill=gold, outline=edge)
        d.line([x0 + 2, 6, x0 + 2, 10], fill=hi)
        if w == 10:
            d.rectangle([7, 7, 8, 10], fill=edge)
    return im


def hoard(frame):
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    gold, edge, hi = rgb('#F8C830'), rgb('#A86C08'), rgb('#FFF0A0')
    for x0, y0, x1, y1 in ((1, 11, 7, 15), (8, 11, 14, 15), (4, 6, 11, 10)):
        d.rectangle([x0, y0, x1, y1], fill=gold, outline=edge)
        d.line([x0 + 1, y0 + 1, x1 - 1, y0 + 1], fill=hi)
    sx, sy = ((12, 3), (3, 4))[frame]
    for dx, dy in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
        im.putpixel((sx + dx, sy + dy), (255, 255, 255, 255))
    return im


KEY = ['................',
       '.....cCCC.......',
       '....cC..CC......',
       '....C....C......',
       '....C....C......',
       '....CC..CC......',
       '.....CCCC.......',
       '......CC........',
       '......CC........',
       '......CC........',
       '......CCCC......',
       '......CC........',
       '......CCCC......',
       '......CC........',
       '................',
       '................']
COLOURS = {'r': '#E03838', 'b': '#3C78F0', 'y': '#F0C828'}


def key(colour):
    c = rgb(COLOURS[colour])
    im = sprite(KEY, {'C': c + (255,), 'c': shade(c, 1.5) + (255,)})
    big_key = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    big_key.paste(im, (1, 0))
    return outline(big_key)


def door(colour):
    c = rgb(COLOURS[colour])
    im = Image.new('RGBA', (16, 48), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rectangle([1, 0, 14, 47], fill=shade(c, 0.35))
    d.rectangle([2, 1, 13, 46], fill=shade(c, 0.8))
    for y0 in (3, 19, 35):                                  # drei Kassetten
        d.rectangle([4, y0, 11, y0 + 9], fill=c, outline=shade(c, 0.5))
        d.line([5, y0 + 1, 10, y0 + 1], fill=shade(c, 1.4))
    for y0 in (15, 31):                                     # Eisenbaender mit Nieten
        d.rectangle([1, y0, 14, y0 + 1], fill=rgb('#3A3A44'))
        for x in (3, 8, 12):
            im.putpixel((x, y0), rgb('#A8A8B8') + (255,))
    d.rectangle([6, 21, 9, 27], fill=rgb('#F0D060'))        # Schlossblech
    d.rectangle([7, 22, 8, 24], fill=(0, 0, 0))
    im.putpixel((7, 25), (0, 0, 0, 255))
    return im


def torch(frame):
    rows = [['.......F........', '......FFF.......', '......FfF.......', '.....FfGfF......', '.....FfGfF......', '......FGF.......'],
            ['........F.......', '.......FF.......', '......FFfF......', '.....FfGfF......', '.....FfGGF......', '......FGF.......']][frame]
    rows = ['................'] + rows + ['.....MMMMM......', '......MMM.......'] + ['......mM........'] * 6 + ['................']
    return outline(sprite(rows))


def vanish_floor(frame):
    """Schwundboden: schraffierte Platte, Bild 1 = Warnung kurz vor dem Verschwinden"""
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    base = rgb('#58C8DC') if frame == 0 else rgb('#2E6470')
    for y in range(6):
        for x in range(16):
            c = shade(base, 0.45) if (x + y) % 4 < 2 else base
            if y == 0:
                c = shade(base, 1.35)
            if y == 5:
                c = shade(base, 0.3)
            im.putpixel((x, y), c + (255,))
    return im


def belt(frame, right=True):
    """Foerderband 16 x 16: oben das laufende Band (Pfeile wandern), darunter Gehaeuse mit Rollen"""
    im = Image.new('RGBA', (16, 16), rgb('#262A34') + (255,))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, 15, 4], fill=rgb('#3E4452'))
    d.line([0, 0, 15, 0], fill=rgb('#9AA4B8'))
    d.line([0, 4, 15, 4], fill=rgb('#14161C'))
    for x0 in (0, 8):
        x = (x0 + frame * 2) % 16
        for dx, dy in ((0, 1), (1, 2), (0, 3)):
            im.putpixel(((x + dx) % 16, dy), rgb('#F0C050') + (255,))
    for cx in (3, 11):
        d.ellipse([cx - 2, 7, cx + 3, 12], fill=rgb('#7A8498'), outline=rgb('#14161C'))
        px, py = ((0, 0), (1, 0), (1, 1), (0, 1))[frame]
        im.putpixel((cx + px, 9 + py), rgb('#E8F0FF') + (255,))
    d.line([0, 15, 15, 15], fill=rgb('#14161C'))
    return im if right else mirror(im)


def life_icon():
    im = Image.new('RGBA', (16, 16), (0, 0, 0, 0))
    im.paste(sprite(HEAD), (0, 3))
    return outline(im)


def label(s, col, scale=1):
    im = Image.new('RGBA', (text_w(s, scale) + 2, 7 * scale + 2), (0, 0, 0, 0))
    text(im, 1, 1, s, col, scale)
    return outline(im)


frames = {}
for name, legs, arm in (('stand', 'stand', 'down'), ('walk_0', 'wide', 'fwd'), ('walk_1', 'pass', 'down'), ('walk_2', 'wide', 'back'),
                        ('walk_3', 'pass', 'down'), ('jump', 'tuck', 'up'), ('fall', 'wide', 'up')):
    frames['claude_r_' + name] = outline(claude(legs, arm))
for name in [n for n in frames if n.startswith('claude_r_')]:
    frames[name.replace('_r_', '_l_')] = mirror(frames[name])
frames['claude_climb_0'] = outline(sprite(CLIMB))
frames['claude_climb_1'] = mirror(frames['claude_climb_0'])
frames['claude_slide'] = outline(sprite(SLIDE))
frames['claude_dead_0'] = flash(frames['claude_r_stand'])
frames['claude_dead_1'] = outline(sprite(DEAD))
for k in range(2):
    frames['spider_%d' % k] = outline(spider(k))
for k in range(3):
    frames['snake_%d' % k] = outline(snake(k))
_skull = outline(sprite(SKULL))
for k in range(4):
    frames['skull_%d' % k] = _skull.rotate(-90 * k)
for k in range(4):
    frames['gold_%d' % k] = outline(coin(k))
for k in range(2):
    frames['hoard_%d' % k] = outline(hoard(k))
for c in 'rby':
    frames['key_' + c] = key(c)
for c in 'rby':
    frames['door_' + c] = door(c)
for k in range(2):
    frames['torch_%d' % k] = torch(k)
for k in range(2):
    frames['floor_%d' % k] = vanish_floor(k)
for k in range(4):
    frames['belt_r_%d' % k] = belt(k, True)
for k in range(4):
    frames['belt_l_%d' % k] = belt(k, False)
frames['life'] = life_icon()


def box(w, h):
    """Kasten fuer Einblendungen: dunkel mit goldenem Rahmen (Pixel-Art)"""
    im = Image.new('RGBA', (w, h), (12, 8, 18, 255))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, w - 1, h - 1], outline=(0, 0, 0, 255))
    d.rectangle([1, 1, w - 2, h - 2], outline=rgb('#C8961E') + (255,))
    d.line([2, 2, w - 3, 2], fill=rgb('#FFE860') + (255,))
    d.rectangle([3, 3, w - 4, h - 4], outline=rgb('#3A2A12') + (255,))
    for x, y in ((2, 2), (w - 3, 2), (2, h - 3), (w - 3, h - 3)):
        d.point([x, y], fill=(255, 255, 255, 255))
    return im


frames['box_small'] = box(160, 28)
frames['box_wide'] = box(240, 28)
frames['box_big'] = box(280, 150)
for pts in ('100', '500', '1000'):
    frames['pop_' + pts] = label(pts, rgb('#FFE860'))
for i, ch in enumerate(CHARSET):
    frames['glyph_%02d' % i] = label(ch, rgb('#FFE860'), 2)

# --- Fallschirm fuer den Sprung in die Schatzkammer (ueber Claude, 24 x 18): rot-weiss gestreifte Kappe, Leinen zu den Schultern.
# Steht als letztes Sprite, damit kein anderer Index sich verschiebt.
PARACHUTE = [
    '........RRWWRRWW........',
    '.....WWRRWWRRWWRRWW.....',
    '...RRWWRRWWRRWWRRWWRR...',
    '..WRRWWRRWWRRWWRRWWRRW..',
    '.RRWWRRWWRRWWRRWWRRWWRR.',
    'RRWWRRWWRRWWRRWWRRWWRRWW',
    'RRWWRRWWRRWWRRWWRRWWRRWW',
    'r.r...r....rr....r...r.r',
    '.b.b...b...bb...b...b.b.',
    '..b.b...b..bb..b...b.b..',
    '...b.b...b.bb.b...b.b...',
    '....b.b...bbbb...b.b....',
    '.....b.b..bbbb..b.b.....',
    '......b.b.bbbb.b.b......',
    '.......b.bbbbbb.b.......',
    '........bbbbbbbb........',
    '........bb....bb........',
    '........b......b........',
]
frames['parachute'] = outline(sprite(PARACHUTE, dict(PAL, R=rgb('#E83A30') + (255,), r=rgb('#9A2018') + (255,),
                                                    W=rgb('#F8F4E8') + (255,), b=rgb('#C8C0A8') + (255,)), 24))


# ------------------------------------------------------------------ Raeume
THEMES = [
    dict(name='Tempel', brick='#C8642C', mortar='#3E7A3A', trim='#F0B060', back='#2A2230', back_mortar='#15101A'),
    dict(name='Eisgruft', brick='#4A78B8', mortar='#1C2C58', trim='#A8D4F4', back='#1E2836', back_mortar='#0E141E'),
    dict(name='Purpurhort', brick='#9A4A9E', mortar='#3A1848', trim='#F0C050', back='#2C2028', back_mortar='#160E16'),
]
STONE = rgb('#A8A49A')
RAIL, RUNG = rgb('#B87A24'), rgb('#F0C868')
ROPE = [rgb('#E8C890'), rgb('#B88A50'), rgb('#7A5630')]
STEEL = [rgb('#50586A'), rgb('#E8F0FF'), rgb('#A0AABE'), rgb('#3A4050')]


def brick_layer(w, h, bw, bh, base, mortar, seed, var=0.14):
    im = Image.new('RGB', (w, h), mortar)
    d = ImageDraw.Draw(im)
    for j in range(h // bh + 1):
        off = bw // 2 if j % 2 else 0
        for i in range(-1, w // bw + 1):
            x0, y0 = i * bw + off, j * bh
            f = 1 - var + 2 * var * rnd(i, j, seed)
            d.rectangle([x0, y0, x0 + bw - 2, y0 + bh - 2], fill=shade(base, f))
            d.line([x0, y0, x0 + bw - 2, y0], fill=shade(base, f * 1.25))
            if bh >= 6:
                d.line([x0, y0 + bh - 2, x0 + bw - 2, y0 + bh - 2], fill=shade(base, f * 0.75))
    return im


def geometry(lines):
    return [''.join('.' if ch in gh_levels.ENTITIES or ch in gh_levels.DOORS else ch for ch in line) for line in lines]


def draw_room(rid, theme):
    """liefert (hell, dunkel, halbdunkel) als Art-Bilder 640 x 320"""
    th = {k: (rgb(v) if k != 'name' else v) for k, v in THEMES[theme].items()}
    raw = ROOMS[rid].lines()
    g = geometry(raw)
    seed = int(rid) + 100 * theme

    def at(c, r):
        return g[r][c] if 0 <= c < COLS and 0 <= r < ROWS else '#'

    back = brick_layer(W, RH, 16, 8, th['back'], th['back_mortar'], seed + 1, 0.2)
    wall = brick_layer(W, RH, 8, 4, th['brick'], th['mortar'], seed + 2)
    mask = Image.new('L', (W, RH), 0)
    md = ImageDraw.Draw(mask)
    for r in range(ROWS):
        for c in range(COLS):
            if g[r][c] == '#':
                md.rectangle([c * T, r * T, c * T + T - 1, r * T + T - 1], fill=255)
    im = Image.composite(wall, back, mask).convert('RGBA')

    # Kanten der Mauern und Schatten auf der Rueckwand
    sh = Image.new('RGBA', (W, RH), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sh)
    d = ImageDraw.Draw(im)
    for r in range(ROWS):
        for c in range(COLS):
            x, y = c * T, r * T
            if g[r][c] != '#':
                continue
            if at(c, r - 1) != '#':                          # begehbare Oberkante
                d.line([x, y, x + 15, y], fill=th['trim'])
                d.line([x, y + 1, x + 15, y + 1], fill=shade(th['trim'], 0.7))
            if at(c, r + 1) != '#':
                d.line([x, y + 15, x + 15, y + 15], fill=shade(th['mortar'], 0.4))
                for k, a in enumerate((130, 95, 60, 30)):
                    sd.line([x, y + 16 + k, x + 15, y + 16 + k], fill=(0, 0, 0, a))
            if at(c - 1, r) != '#':
                d.line([x, y, x, y + 15], fill=shade(th['brick'], 1.2))
            if at(c + 1, r) != '#':
                d.line([x + 15, y, x + 15, y + 15], fill=shade(th['mortar'], 0.4))
                for k, a in enumerate((90, 50)):
                    sd.line([x + 16 + k, y, x + 16 + k, y + 15], fill=(0, 0, 0, a))
    sh.putalpha(ImageChops.multiply(sh.getchannel('A'), ImageChops.invert(mask)))   # Schatten nur auf der Rueckwand
    im = Image.alpha_composite(im, sh)
    d = ImageDraw.Draw(im)

    for r in range(ROWS):
        for c in range(COLS):
            x, y, ch = c * T, r * T, g[r][c]
            if ch == '=':                                    # duenner Steinboden
                d.rectangle([x, y, x + 15, y + 4], fill=STONE)
                d.line([x, y, x + 15, y], fill=shade(STONE, 1.3))
                d.line([x, y + 4, x + 15, y + 4], fill=shade(STONE, 0.55))
                d.line([x + (5 if c % 2 else 11), y + 1, x + (5 if c % 2 else 11), y + 3], fill=shade(STONE, 0.7))
                d.line([x, y + 5, x + 15, y + 5], fill=(0, 0, 0))
                if at(c - 1, r) != '=':
                    d.line([x, y, x, y + 4], fill=shade(STONE, 0.55))
                if at(c + 1, r) != '=':
                    d.line([x + 15, y, x + 15, y + 4], fill=shade(STONE, 0.55))
            elif ch == 'H':                                  # Leiter
                for rx in (2, 12):
                    d.rectangle([x + rx, y, x + rx + 1, y + 15], fill=RAIL)
                    d.line([x + rx, y, x + rx, y + 15], fill=shade(RAIL, 1.3))
                for ry in (2, 6, 10, 14):
                    d.line([x + 4, y + ry, x + 11, y + ry], fill=RUNG)
                    d.line([x + 4, y + ry + 1, x + 11, y + ry + 1], fill=shade(RAIL, 0.6))
            elif ch == ':':                                  # Seil
                for yy in range(16):
                    k = (yy + r * 16) % 4
                    d.point([x + 6, y + yy], fill=ROPE[1] if k < 2 else ROPE[2])
                    d.point([x + 7, y + yy], fill=ROPE[0] if k < 2 else ROPE[1])
                    d.point([x + 8, y + yy], fill=ROPE[1] if k < 2 else ROPE[2])
                if at(c, r - 1) != ':' and r > 0:            # Ring an der Decke
                    d.rectangle([x + 5, y, x + 10, y + 2], outline=STEEL[2])
                if at(c, r + 1) != ':' and r < ROWS - 1:     # Knoten am Ende
                    d.rectangle([x + 6, y + 11, x + 9, y + 14], fill=ROPE[0])
                    d.line([x + 6, y + 14, x + 9, y + 14], fill=ROPE[2])
            elif ch == '|':                                  # Rutschstange
                for k, col in enumerate(STEEL):
                    d.line([x + 6 + k, y, x + 6 + k, y + 15], fill=col)
                if at(c, r - 1) != '|' and r > 0:            # Halterung an der Decke
                    d.rectangle([x + 3, y, x + 12, y + 2], fill=STEEL[0])
                    d.line([x + 3, y, x + 12, y], fill=STEEL[2])
                if at(c, r + 1) != '|' and r < ROWS - 1:     # Fuss
                    d.rectangle([x + 4, y + 13, x + 11, y + 15], fill=STEEL[0])
                    d.line([x + 4, y + 13, x + 11, y + 13], fill=STEEL[2])
            elif ch == '.':
                web = shade(th['back'], 3.2)
                if at(c, r - 1) == '#' and at(c - 1, r) == '#' and rnd(c, r, seed + 5) < 0.7:      # Spinnweben
                    for pts in ([0, 0, 10, 0], [0, 0, 0, 10], [0, 0, 7, 7], [9, 0, 6, 6], [6, 6, 0, 9], [5, 0, 3, 3], [3, 3, 0, 5]):
                        d.line([x + pts[0], y + pts[1], x + pts[2], y + pts[3]], fill=web)
                if at(c, r - 1) == '#' and at(c + 1, r) == '#' and rnd(c, r, seed + 6) < 0.7:
                    for pts in ([0, 0, 10, 0], [0, 0, 0, 10], [0, 0, 7, 7], [9, 0, 6, 6], [6, 6, 0, 9], [5, 0, 3, 3], [3, 3, 0, 5]):
                        d.line([x + 15 - pts[0], y + pts[1], x + 15 - pts[2], y + pts[3]], fill=web)
    def dimmed(f, add):
        t = im.convert('RGB').point(lambda v: int(v * f) + add)
        tr, tg, tb = t.split()
        return Image.merge('RGB', (tr, tg, tb.point(lambda v: min(255, int(v * 1.5) + add))))
    dark = dimmed(0.035, 1)        # ohne Fackel: fast schwarz
    dim = dimmed(0.30, 2)          # Rand des Lichtkreises um Claude

    lit = im.convert('RGB')      # keine Wandleuchten: die einzige Fackel ist der Gegenstand 'T'
    return lit, dark, dim


LIGHT_NEAR, LIGHT_FAR = 3.3, 5.3      # Lichtkreis um Claude in Kacheln: innen hell, Ring halbdunkel, sonst fast schwarz


def torchless(views, player):
    """Raum ohne Fackel: Kachel fuer Kachel aus hell / halbdunkel / dunkel, je nach Abstand zu Claude (Spalte, Zeile)"""
    lit, dark, dim = views
    out = dark.copy()
    for r in range(ROWS):
        for c in range(COLS):
            dist = ((c - player[0]) ** 2 + (r - (player[1] - 0.5)) ** 2) ** 0.5
            src = lit if dist <= LIGHT_NEAR else dim if dist <= LIGHT_FAR else None
            if src:
                box = (c * T, r * T, c * T + T, r * T + T)
                out.paste(src.crop(box), box)
    return out


def place_sprites(im, rid, player=None):
    """Objekte und Gegner an ihre Startplaetze (nur fuer Vorschauen; im Spiel zeichnet LabVIEW).
    player = (Spalte, Zeile): dunkler Raum, nur Sprites im Lichtkreis sind sichtbar"""
    im = im.convert('RGBA')
    raw = ROOMS[rid].lines()
    name = {'P': 'claude_r_stand', 'g': 'gold_0', 'G': 'hoard_0', 'r': 'key_r', 'b': 'key_b', 'y': 'key_y', 'T': 'torch_0',
            'S': 'spider_0', 'Z': 'snake_1', 'K': 'skull_0', '~': 'floor_0', '<': 'belt_l_0', '>': 'belt_r_0'}
    for r in range(ROWS):
        for c in range(COLS):
            ch = raw[r][c]
            if player and ((c - player[0]) ** 2 + (r - (player[1] - 0.5)) ** 2) ** 0.5 > LIGHT_FAR:
                continue
            if ch in gh_levels.DOORS:
                if raw[r - 1][c] != ch:
                    spr = frames['door_' + gh_levels.DOORS[ch]]
                    im.alpha_composite(spr, (c * T, r * T))
            elif ch in name:
                spr = frames[name[ch]]
                y = r * T if ch in '~<>' else r * T + T - spr.height
                im.alpha_composite(spr, (c * T, y))
    if player:
        spr = frames['claude_r_walk_0']
        im.alpha_composite(spr, (player[0] * T, player[1] * T + T - spr.height))
    return im


# ------------------------------------------------------------------ HUD und Titel
GOLD, GOLD_LO = rgb('#FFE860'), rgb('#E89A1C')
PANELS = [(6, 150, 'LIVES'), (156, 290, 'KEYS'), (296, 360, 'TORCH'), (366, 440, 'LEVEL'), (446, 560, 'GOLD'), (566, 633, 'TIME')]


def draw_hud():
    im = brick_layer(W, HUD_H, 16, 8, rgb('#3A3448'), rgb('#1A1622'), 77, 0.15).convert('RGBA')
    d = ImageDraw.Draw(im)
    d.rectangle([0, HUD_H - 3, W - 1, HUD_H - 2], fill=rgb('#C8961E'))
    d.line([0, HUD_H - 3, W - 1, HUD_H - 3], fill=GOLD)
    d.line([0, HUD_H - 1, W - 1, HUD_H - 1], fill=(0, 0, 0))
    for x0, x1, name in PANELS:
        d.rectangle([x0, 3, x1, 33], fill=(8, 6, 12), outline=rgb('#C8961E'))
        d.line([x0, 3, x1, 3], fill=GOLD)
        text(im, x0 + 5, 6, name, rgb('#C8961E'))
    return im


def hud_sample(hud):
    im = hud.copy()
    for k in range(4):                      # Start mit 4 Leben, Platz fuer 7
        im.alpha_composite(frames['life'], (11 + k * 18, 15))
    for k, (c, n) in enumerate((('b', '1'), ('r', '2'), ('y', '0'))):       # Symbol und Anzahl je Farbe
        im.alpha_composite(frames['key_' + c], (160 + k * 42, 15))
        im.alpha_composite(frames['glyph_%02d' % CHARSET.index(n)], (176 + k * 42, 15))
    im.alpha_composite(frames['torch_0'], (320, 15))
    for x, s in ((384, '1'), (451, '002400'), (578, '15')):
        for i, ch in enumerate(s):
            im.alpha_composite(frames['glyph_%02d' % CHARSET.index(ch)], (x + i * 12, 15))
    return im


def draw_title():
    th = THEMES[0]
    im = brick_layer(W, 360, 16, 8, rgb(th['back']), rgb(th['back_mortar']), 5, 0.2)
    wall = brick_layer(W, 360, 8, 4, rgb(th['brick']), rgb(th['mortar']), 6)
    mask = Image.new('L', (W, 360), 0)
    md = ImageDraw.Draw(mask)
    md.rectangle([0, 0, W - 1, 359], fill=255)
    md.rectangle([16, 16, W - 17, 343], fill=0)
    md.rectangle([96, 240, W - 97, 255], fill=255)             # Sockel fuer die Figuren
    im = Image.composite(wall, im, mask).convert('RGBA')
    d = ImageDraw.Draw(im)
    d.line([96, 240, W - 97, 240], fill=rgb(th['trim']))
    d.rectangle([16, 16, W - 17, 343], outline=(0, 0, 0))
    title = 'GOLD HUNTER'
    text(im, (W - text_w(title, 7)) // 2, 44, title, GOLD, 7, shadow=(60, 24, 0), col2=GOLD_LO)
    sub = 'CLAUDE ON A TREASURE HUNT'
    text(im, (W - text_w(sub, 2)) // 2, 112, sub, rgb('#F0B890'), 2, shadow=(0, 0, 0))
    cast = ['key_r', 'key_b', 'key_y', 'torch_0', 'hoard_0', 'gold_0', 'claude_r_walk_0', 'gold_0', 'hoard_1', 'snake_1', 'spider_0', 'skull_0']
    x = (W - len(cast) * 36) // 2
    for n in cast:
        spr = frames[n]
        k = 3 if n.startswith('claude') else 2
        spr = spr.resize((spr.width * k, spr.height * k), Image.NEAREST)
        im.alpha_composite(spr, (x + (36 - spr.width) // 2, 240 - spr.height))
        x += 36
    start = 'ENTER = START'
    text(im, (W - text_w(start, 3)) // 2, 276, start, (255, 255, 255), 3, shadow=(0, 0, 0))
    for i, line in enumerate(('ARROWS = MOVE AND CLIMB    SPACE = JUMP    ESC = PAUSE',)):
        text(im, (W - text_w(line)) // 2, 316 + i * 12, line, rgb('#C8961E'))
    return im


# ------------------------------------------------------------------ Ausgabe
if __name__ == '__main__':
    names = list(frames)
    for n in names:
        save(big(frames[n]), 'Sprites', n + '.png')
    with open(os.path.join(RES, 'Sprites', 'sprites.txt'), 'w', newline='\r\n') as f:
        f.write('\n'.join(names) + '\n')

    hud = draw_hud()
    save(big(hud).convert('RGB'), 'Images', 'hud.png')
    save(big(draw_title()).convert('RGB'), 'Images', 'title.png')

    for name in os.listdir(os.path.join(RES, 'Images')) + os.listdir(os.path.join(RES, 'Preview')):   # alte Bilder entfernen
        for folder in ('Images', 'Preview'):
            if name.startswith(('room_', 'screen_', 'world_')) and os.path.exists(os.path.join(RES, folder, name)):
                os.remove(os.path.join(RES, folder, name))
    views = {}
    for theme in range(len(THEMES)):
        for rid in ROOMS:
            lit, dark, dim = views[(theme, rid)] = draw_room(rid, theme)
            save(big(lit), 'Images', 'room_%d_%s.png' % (theme, rid))
            save(big(dark), 'Images', 'room_%d_%s_dark.png' % (theme, rid))
            save(big(dim), 'Images', 'room_%d_%s_dim.png' % (theme, rid))

    # Vorschauen: ganzer Bildschirm (HUD + Raum), Weltkarte je Schema, Sprite-Blatt
    def screen(theme, rid, player=None):
        im = Image.new('RGBA', (W, 360), (0, 0, 0, 255))
        im.alpha_composite(hud_sample(hud), (0, 0))
        room = torchless(views[(theme, rid)], player) if player else views[(theme, rid)][0]
        im.alpha_composite(place_sprites(room, rid, player), (0, HUD_H))
        save(big(im).convert('RGB'), 'Preview', 'screen_%d_%s%s.png' % (theme, rid, '_dark' if player else ''))

    for theme, rid in ((0, '005'), (0, '105'), (0, '405'), (0, '104'), (1, '106'), (2, '505'), (0, '605')):
        screen(theme, rid)
    screen(0, '204', (14, 12))
    screen(0, '305', (24, 12))
    for theme in range(len(THEMES)):
        world = Image.new('RGB', (len(WORLD[0]) * (W + 4), len(WORLD) * (RH + 4)), (0, 0, 0))
        for dpt, row in enumerate(WORLD):
            for xx, rid in enumerate(row):
                if rid:
                    world.paste(place_sprites(views[(theme, rid)][0], rid).convert('RGB'), (xx * (W + 4), dpt * (RH + 4)))
        save(world.resize((world.width // 2, world.height // 2), Image.LANCZOS), 'Preview', 'world_%d.png' % theme)
    small = [n for n in names if not n.startswith('glyph') and not n.startswith('door')]
    sheet = Image.new('RGBA', (13 * 22 * 4, 5 * 30 * 4), rgb('#2A2230') + (255,))
    for i, n in enumerate(small):
        spr = frames[n].resize((frames[n].width * 4, frames[n].height * 4), Image.NEAREST)
        sheet.alpha_composite(spr, ((i % 13) * 88 + 8, (i // 13) * 120 + 8 + (96 - spr.height)))
    for i, c in enumerate('rby'):
        spr = frames['door_' + c].resize((32, 96), Image.NEAREST)
        sheet.alpha_composite(spr, (i * 44 + 8, 4 * 120 + 8))
    for i, ch in enumerate(CHARSET):
        sheet.alpha_composite(frames['glyph_%02d' % i], (150 + i * 14, 4 * 120 + 40))
    save(sheet.convert('RGB'), 'Preview', 'sprites.png')
    print(len(names), 'Sprites,', len(views) * 3, 'Raumbilder')
