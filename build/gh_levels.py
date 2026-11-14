# Gold Hunter - Welt und Raeume. Einzige Quelle der Geometrie:
#   Resources\Levels\room_<id>.txt   20 Zeilen x 40 Zeichen (Kacheln 32 px), id = Tiefe + Spalte (2 Stellen)
#   Resources\Levels\world.txt       Raumgitter (Tiefe x Spalte)
#   Resources\Levels\levels.txt      Schwierigkeit je Level
# Aufruf: python gh_levels.py   (schreibt die Dateien)      Pruefung: python check_levels.py
#
# Zeichen:  . leer        # Mauer          = duenner Steinboden (von unten durchspringbar)
#           ~ Schwundboden (verschwindet im Rhythmus, von unten durchspringbar)
#           H Leiter      | Rutschstange (nur abwaerts)      : Seil (haengt von der Decke, hoch und runter)
#           < > Foerderband nach links / rechts (fester Boden, schiebt Claude)
#           R B Y Tuer rot/blau/gelb       r b y Schluessel      T Fackel
#           g Goldmuenze (100)   G Goldschatz (500)
#           S Spinne      Z Schlange       K Totenkopf           P Start
# Raster: Decke Zeile 0, Boeden auf den Zeilen 7, 13, 19 (drei Etagen je Raum).
#         Duenne Plattformen liegen 2 bzw. 4 Kacheln ueber einem Boden (Sprunghoehe gut 2 Kacheln).
import os

COLS, ROWS = 40, 20
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..'))
LEVEL_DIR = os.path.join(ROOT, 'Resources', 'Levels')
SUPPORT = '#=~H<>'
ENTITIES = 'PgGrbyTSZK'
DOORS = {'R': 'r', 'B': 'b', 'Y': 'y'}


class Room:
    def __init__(self, name):
        self.name = name
        self.g = [['.'] * COLS for _ in range(ROWS)]
        self.floor(0, 0, 39)
        self.floor(19, 0, 39)
        for r in range(ROWS):
            self.g[r][0] = self.g[r][39] = '#'

    def floor(self, row, c0=1, c1=38, ch='#'):
        for c in range(c0, c1 + 1):
            self.g[row][c] = ch
        return self

    def thin(self, row, c0, c1):
        return self.floor(row, c0, c1, '=')

    def hatch(self, row, c0, c1):
        return self.floor(row, c0, c1, '~')

    def hole(self, row, c0, c1):
        return self.floor(row, c0, c1, '.')

    def block(self, c0, r0, c1, r1):
        for r in range(r0, r1 + 1):
            self.floor(r, c0, c1)
        return self

    def ladder(self, col, r0, r1):
        for r in range(r0, r1 + 1):
            self.g[r][col] = 'H'
        return self

    def rope(self, col, r0, r1):
        for r in range(r0, r1 + 1):
            self.g[r][col] = ':'
        return self

    def pole(self, col, r0, r1):
        for r in range(r0, r1 + 1):
            self.g[r][col] = '|'
        return self

    def door(self, col, F, ch):
        """Tuer 3 Kacheln hoch auf dem Boden F, darueber Mauer bis zur Decke"""
        ceil = F - 6 if F > 7 else 0
        for r in range(ceil + 1, F - 3):
            self.g[r][col] = '#'
        for r in range(F - 3, F):
            self.g[r][col] = ch
        return self

    def exit(self, side, F):
        col = 0 if side == 'L' else 39
        for r in range(F - 3, F):
            self.g[r][col] = '.'
        return self

    def put(self, ch, *cells):
        for c, r in cells:
            assert self.g[r][c] == '.', (self.name, ch, c, r, self.g[r][c])
            assert self.g[r + 1][c] in SUPPORT, (self.name, ch, c, r, 'ohne Boden')
            self.g[r][c] = ch
        return self

    def lines(self):
        return [''.join(r) for r in self.g]


# ====================================================================== Weltplan (von Hand)
# Pyramide: Tiefe d = 0..5, Spalte x = 0..10, Raum vorhanden wenn |x - 5| <= d. Schatzkammer unter (5,5).
DEPTHS, CENTER = 6, 5
ST = {7: 0, 13: 1, 19: 2}            # Boden-Zeile -> Etage im Raum
FEET = [6, 12, 18]


def rid(d, x):
    return '%d%02d' % (d, x)


# Verbindung nach unten von (d,x) zu (d+1,x): 'L' Leiter oder 'P' Rutschstange (nur abwaerts), Spalte
VLINK = {(0, 5): ('L', 20),
         (1, 4): ('P', 3), (1, 5): ('L', 8), (1, 6): ('L', 30),
         (2, 3): ('L', 14), (2, 6): ('L', 26), (2, 7): ('P', 36),
         (3, 2): ('P', 3), (3, 4): ('L', 20), (3, 6): ('L', 8), (3, 8): ('L', 26),
         (4, 1): ('L', 14), (4, 3): ('L', 30), (4, 5): ('L', 28), (4, 6): ('P', 3), (4, 7): ('L', 20), (4, 9): ('L', 10)}
# Durchgang von (d,x) nach rechts zu (d,x+1) auf dem Boden 7, 13 oder 19
HLINK = {(1, 4): 13, (1, 5): 13,
         (2, 3): 19, (2, 4): 13, (2, 6): 13,
         (3, 2): 13, (3, 3): 19, (3, 4): 13, (3, 5): 13, (3, 6): 19, (3, 7): 13,
         (4, 1): 13, (4, 2): 19, (4, 3): 13, (4, 4): 19, (4, 6): 13, (4, 7): 19, (4, 8): 13,
         (5, 0): 13, (5, 1): 19, (5, 2): 13, (5, 3): 19, (5, 6): 13, (5, 7): 19, (5, 8): 13, (5, 9): 19}
# Tuer im Durchgang (steht im linken Raum, Spalte 35)
LINKDOOR = {(1, 5): 'B', (2, 3): 'B', (4, 4): 'B', (5, 8): 'B',
            (3, 4): 'R', (4, 1): 'R', (3, 7): 'R', (5, 9): 'R',
            (5, 1): 'Y', (3, 5): 'Y', (4, 7): 'Y', (5, 3): 'Y'}
# zweite Tuer hintereinander im selben Durchgang (steht im rechten Raum, Spalte 4)
LINKDOOR2 = {(1, 5): 'R', (5, 9): 'Y'}
# Goldnische hinter einer Tuer: Seite, Boden, Farbe
NOOK = {(2, 6): ('L', 7, 'Y'), (5, 7): ('R', 7, 'R')}
# Besondere Raeume: Tuer im Raum, Loch zur Schatzkammer, erlaubte Spalten der Leiter Mitte-unten
SPECIAL = {(4, 5): dict(door=(18, 19, 'Y'), door2=(22, 19, 'R'), b=(6, 14), nohatch=True),
           (5, 5): dict(door=(10, 19, 'Y'), hole=(5, 6), b=(14, 32), nohatch=True)}
# Schluessel und Fackel. Regel gegen Sackgassen: blaue Schluessel liegen vor allen Tueren,
# rote hoechstens hinter blauen Tueren, gelbe nie nur hinter gelben.
ITEMS = {(1, 4): 'b', (2, 5): 'b', (1, 5): 'b',
         (2, 4): 'r', (3, 2): 'r', (4, 3): 'r', (2, 7): 'r', (4, 6): 'r', (5, 3): 'r', (3, 3): 'r', (3, 4): 'r',
         (5, 0): 'y', (4, 8): 'y', (3, 5): 'y', (4, 9): 'y', (5, 2): 'y', (3, 7): 'y', (4, 2): 'y', (4, 4): 'y',
         (1, 6): 'T'}


def rnd(a, b=0):
    v = ((a * 73856093) ^ (b * 19349663) ^ 0x5BD1E995) & 0xFFFFFFFF
    v = ((v ^ (v >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((v ^ (v >> 16)) & 0xFFFF) / 65536.0


def start_room():
    a = Room(rid(0, 5))
    a.floor(7).floor(13)
    a.pole(3, 1, 18)                                   # Abkuerzung von ganz oben nach ganz unten
    a.ladder(30, 7, 12).ladder(24, 13, 18).ladder(20, 19, 19)
    a.thin(5, 17, 22)
    a.hatch(13, 14, 19).thin(17, 13, 20)               # Schwundboden, darunter Fangplattform
    a.door(34, 13, 'R')                                # Goldnische
    a.rope(8, 0, 5)                                    # Einstieg: Claude klettert am Seil von oben herein
    a.put('P', (8, 6))
    a.put('g', (12, 6), (14, 6), (24, 6), (26, 6), (19, 4), (20, 4), (10, 12), (27, 12),
          (15, 16), (17, 16), (8, 18), (28, 18), (32, 18), (36, 12))
    a.put('G', (37, 12))
    a.put('b', (7, 12))
    a.put('Z', (12, 18))
    return a


def treasure_room():
    t = Room(rid(6, 5))
    t.hole(0, 5, 6)
    for row, spans in ((17, [(4, 12), (16, 24), (28, 36)]), (15, [(9, 19), (22, 32)]), (13, [(4, 12), (16, 24), (28, 36)]),
                       (11, [(9, 19), (22, 32)]), (9, [(14, 26)])):
        for c0, c1 in spans:
            t.thin(row, c0, c1)
            t.put('g', *[(c, row - 1) for c in range(c0 + 1, c1, 2)])
    t.put('g', *[(c, 18) for c in range(3, 38, 2) if c not in (19, 21)])
    t.put('G', (19, 18), (21, 18), (20, 8), (18, 8), (22, 8))
    return t


def gen_room(d, x):
    """baut einen Raum aus dem Weltplan; Einzelheiten (Leitern, Plattformen, Gegner, Gold) folgen fest aus (d, x)"""
    key = (d, x)
    R = Room(rid(d, x))
    R.floor(7).floor(13)
    sp = SPECIAL.get(key, {})

    def rs(k):
        return rnd(d * 100 + x, k)

    res = [set(), set(), set()]        # Spalten, die Leitern, Schwundboeden und Plattformen meiden
    blocked = [set(), set(), set()]    # Spalten ohne Gegenstaende und Gegner
    entry = [set(), set(), set()]      # Eingaenge je Etage (Gegner halten Abstand)
    used = [set(), set(), set()]
    left, right = HLINK.get((d, x - 1)), HLINK.get(key)
    if left:
        R.exit('L', left)
        entry[ST[left]].add(0)
    if right:
        R.exit('R', right)
        entry[ST[right]].add(39)
    up, down = VLINK.get((d - 1, x)), VLINK.get(key)
    for link, st, r0, r1 in ((up, 0, 0, 6), (down, 2, 19, 19)):
        if not link:
            continue
        kind, c = link
        if kind == 'L':
            R.ladder(c, r0, r1)
        else:
            R.pole(c, 0 if st == 0 else 14, r1)
            blocked[st] |= set(range(1, c + 2) if c < 20 else range(c - 1, 39))
        res[st] |= set(range(c - 2, c + 3))
        entry[st].add(c)
    if key in LINKDOOR:
        st = ST[right]
        R.door(35, right, LINKDOOR[key])
        blocked[st] |= set(range(33, 39))
        res[st] |= set(range(33, 39))
    if (d, x - 1) in LINKDOOR2:
        st = ST[left]
        R.door(4, left, LINKDOOR2[(d, x - 1)])
        blocked[st] |= set(range(1, 7))
        res[st] |= set(range(1, 7))
    if key in NOOK:
        side, F, colour = NOOK[key]
        st = ST[F]
        cols = list(range(34, 39)) if side == 'R' else list(range(1, 6))
        guard = set(range(31, 39)) if side == 'R' else set(range(1, 9))
        R.door(33 if side == 'R' else 6, F, colour)
        blocked[st] |= guard
        res[st] |= guard
        R.put('G', (cols[1], FEET[st]), (cols[3], FEET[st]))
        R.put('g', (cols[2], FEET[st]))
    for name in ('door', 'door2'):
        if name in sp:
            c, F, colour = sp[name]
            R.door(c, F, colour)
            res[ST[F]] |= set(range(c - 2, c + 3))
            blocked[ST[F]] |= set(range(c - 1, c + 2))
    if 'hole' in sp:
        R.hole(19, *sp['hole'])
        blocked[2] |= set(range(1, sp['door'][0] + 2))

    # zwei Aufstiege im Raum: oben-Mitte (a) und Mitte-unten (b), je Leiter oder Seil
    ca = [c for c in range(6, 33) if c not in res[0] and c not in res[1]]
    a = ca[int(rs(1) * len(ca))]
    if rs(70) < 0.4:
        R.rope(a, 1, 12)                               # Seil von der Decke durch ein Loch im Boden
    else:
        R.ladder(a, 7, 12)
    b_lo, b_hi = sp.get('b', (6, 32))
    cb = [c for c in range(b_lo, b_hi + 1) if c not in res[1] and c not in res[2] and abs(c - a) >= 6]
    b = cb[int(rs(2) * len(cb))]
    if rs(71) < 0.4:
        R.rope(b, 8, 18)
    else:
        R.ladder(b, 13, 18)
    for st, c in ((0, a), (1, a), (1, b), (2, b)):
        res[st] |= set(range(c - 2, c + 3))
        entry[st].add(c)

    plats = []
    if not sp.get('nohatch') and rs(3) < 0.8:          # Schwundboden mit Fangplattform 4 Kacheln tiefer
        w = 4 + int(rs(5) * 3)
        for F in ((7, 13) if rs(4) < 0.5 else (13, 7)):
            sa, sb = ST[F], ST[F] + 1
            cand = [c0 for c0 in range(6, 33 - w)
                    if all(c not in res[sa] and c not in res[sb] and c not in blocked[sa] and c not in blocked[sb]
                           for c in range(c0 - 2, c0 + w + 2))
                    and all(R.g[F + 4][c] == '.' for c in range(c0 - 1, c0 + w + 1))]
            if cand:
                c0 = cand[int(rs(6) * len(cand))]
                R.hatch(F, c0, c0 + w - 1)
                R.thin(F + 4, c0 - 1, c0 + w)
                plats.append((F + 4, c0 - 1, c0 + w))
                break

    def platform(row, st, k):
        w = 4 + int(rs(k) * 3)
        cand = [c0 for c0 in range(4, 35 - w)
                if all(c not in res[st] and c not in blocked[st] and all(R.g[row + dr][c] == '.' for dr in (-2, -1, 0, 1))
                       for c in range(c0 - 1, c0 + w + 1))]
        if cand:
            c0 = cand[int(rs(k + 1) * len(cand))]
            R.thin(row, c0, c0 + w - 1)
            plats.append((row, c0, c0 + w - 1))

    if rs(7) < 0.7:
        platform(5, 0, 8)
    if rs(10) < 0.6:
        platform(*((11, 1) if rs(11) < 0.5 else (17, 2)), 12)

    def spots(st):
        f = FEET[st]
        return [c for c in range(2, 38) if R.g[f][c] == '.' and R.g[f - 1][c] == '.' and R.g[f + 1][c] == '#'
                and c not in blocked[st] and c not in used[st]]

    def place(ch, st, c):
        R.put(ch, (c, FEET[st]))
        used[st] |= {c - 1, c, c + 1}

    if key in ITEMS:                                   # Schluessel / Fackel: moeglichst weit weg von den Eingaengen
        for i in range(3):
            st = (int(rs(20) * 3) + i) % 3
            cand = spots(st)
            if cand:
                place(ITEMS[key], st, max(cand, key=lambda c: min(abs(c - e) for e in entry[st])))
                break
        else:
            raise AssertionError(('kein Platz fuer', ITEMS[key], key))
    kinds = 'ZKS'
    for i in range(2 if d <= 1 else 3):                # Gegner, hoechstens einer je Etage
        st = (int(rs(30) * 3) + i) % 3
        cand = [c for c in spots(st) if 3 <= c <= 36 and all(abs(c - e) >= 5 for e in entry[st])]
        if cand:
            place(kinds[(int(rs(31) * 3) + i) % 3], st, cand[int(rs(32 + i) * len(cand))])
    for row, c0, c1 in plats:                          # Gold
        for c in range(c0 + 1, c1, 2):
            if R.g[row - 1][c] == '.':
                R.g[row - 1][c] = 'g'
    degree = sum(1 for v in (left, right, up, down) if v)
    for st in range(3):
        for i in range(2 + int(rs(40 + st) * 2)):
            cand = spots(st)
            if cand:
                place('g', st, cand[int(rs(50 + st * 5 + i) * len(cand))])
    for i in range(2 if degree == 1 else (1 if rs(60) < 0.35 else 0)):
        st = (int(rs(61) * 3) + i) % 3
        cand = spots(st)
        if cand:
            place('G', st, cand[int(rs(62 + i) * len(cand))])
    if rs(80) < 0.55:                                  # Foerderband: ein Stueck Boden, das Claude schiebt
        st = int(rs(81) * 3)
        F, w = (7, 13, 19)[st], 5 + int(rs(82) * 3)
        cand = [c0 for c0 in range(4, 35 - w)
                if all(R.g[F][c] == '#' and R.g[F - 1][c] in '.g' and c not in res[st] and c not in blocked[st]
                       and (st == 2 or c not in res[st + 1]) for c in range(c0 - 1, c0 + w + 1))]
        if cand:
            c0 = cand[int(rs(83) * len(cand))]
            R.floor(F, c0, c0 + w - 1, '<' if rs(84) < 0.5 else '>')
    return R


def build():
    R = {}
    for d in range(DEPTHS):
        for x in range(CENTER - d, CENTER + d + 1):
            R[rid(d, x)] = start_room() if d == 0 else gen_room(d, x)
    R[rid(DEPTHS, CENTER)] = treasure_room()
    return R


# Raumgitter: WORLD[tiefe][spalte] = Raum-ID oder None
WORLD = [[rid(d, x) if abs(x - CENTER) <= d else None for x in range(2 * CENTER + 1)] for d in range(DEPTHS)]
WORLD.append([rid(DEPTHS, x) if x == CENTER else None for x in range(2 * CENTER + 1)])
START, TREASURE = rid(0, CENTER), rid(DEPTHS, CENTER)
# Level; Farbschema; dunkel ab Tiefe; Tempo Spinne; Tempo Totenkopf (px/Tick); Schwundboden an/aus (Ticks); Schatzkammer (s)
LEVELS = [(1, 0, 5, 2, 3, 150, 90, 15),
          (2, 1, 1, 3, 4, 120, 90, 15),
          (3, 2, 1, 3, 5, 100, 100, 13)]

ROOMS = build()


def write():
    os.makedirs(LEVEL_DIR, exist_ok=True)
    for name in os.listdir(LEVEL_DIR):                 # alte Raumdateien entfernen
        if name.startswith('room_') and name.endswith('.txt') and name[5:-4] not in ROOMS:
            os.remove(os.path.join(LEVEL_DIR, name))
    for r_id, room in ROOMS.items():
        lines = room.lines()
        assert len(lines) == ROWS and all(len(x) == COLS for x in lines)
        with open(os.path.join(LEVEL_DIR, 'room_%s.txt' % r_id), 'w', newline='\r\n') as f:
            f.write('\n'.join(lines) + '\n')
    with open(os.path.join(LEVEL_DIR, 'world.txt'), 'w', newline='\r\n') as f:
        for row in WORLD:
            f.write(' '.join(x or '---' for x in row) + '\n')
    with open(os.path.join(LEVEL_DIR, 'levels.txt'), 'w', newline='\r\n') as f:
        f.write('# Level;Schema;DunkelAbTiefe;TempoSpinne;TempoKopf;SchwundAn;SchwundAus;SchatzSekunden\n')
        for lv in LEVELS:
            f.write(';'.join(str(v) for v in lv) + '\n')


if __name__ == '__main__':
    write()
    for r_id, room in ROOMS.items():
        print('--- Raum', r_id)
        print('\n'.join(room.lines()))
