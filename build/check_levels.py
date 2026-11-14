# Gold Hunter - Loesbarkeitspruefung.
# Bewegungsmodell auf Kachel-Ebene (passend zu den Physik-Konstanten in ARCHITEKTUR.md):
#   laufen, Leitern und Seile hoch/runter, Stangen nur hinunter, Sprung: bis 2 Kacheln hoch, bis 3 weit (2 weit bei 2 hoch),
#   von unten durch '=' und '~', Sturz ueber mehr als 4 Kacheln = tot (keine Kante). Gegner werden nicht modelliert.
# Die Pruefung laeuft in zwei Stufen und ist damit auch fuer viele Tueren schnell:
#   A. Alle Tueren zu: Die Welt zerfaellt in Gebiete (stark zusammenhaengend: man kommt ueberall hin UND zurueck).
#      Geprueft wird, dass jede Einbahn (Stange, Sprung hinunter) wieder im selben Gebiet endet -
#      niemand kann sich ohne Tuer in eine Ecke ohne Rueckweg bringen.
#   B. Schluesselspiel auf den Gebieten: Tueren verbinden Gebiete, jeder Schluessel oeffnet eine Tuer seiner Farbe
#      und ist dann verbraucht. Durchgerechnet werden ALLE Reihenfolgen, in denen man Tueren oeffnen kann:
#      1. Schatzkammer erreichbar  2. alle Schluessel, die Fackel, alles Gold erreichbar
#      3. keine Sackgasse: aus jedem Stand (Menge offener Tueren) ist die Schatzkammer noch erreichbar
import sys
from collections import deque
from gh_levels import ROOMS, WORLD, START, TREASURE, COLS, ROWS, ENTITIES, DOORS

MAX_FALL = 4
GOAL = 'GOAL'
# ein Seil ':' verhaelt sich im Modell wie eine Leiter
# ein Foerderband '<' '>' ist fester Boden: es schiebt langsamer, als Claude laeuft
GRID = {rid: [[('.' if ch in ENTITIES else 'H' if ch == ':' else '#' if ch in '<>' else ch) for ch in line] for line in room.lines()]
        for rid, room in ROOMS.items()}
RAW = {rid: room.lines() for rid, room in ROOMS.items()}
WHERE = {rid: (d, x) for d, row in enumerate(WORLD) for x, rid in enumerate(row) if rid}


def neighbour(rid, dd, dx):
    d, x = WHERE[rid]
    d, x = d + dd, x + dx
    if 0 <= d < len(WORLD) and 0 <= x < len(WORLD[d]):
        return WORLD[d][x]
    return None


def norm(rid, c, r):
    if c < 0:
        rid, c = neighbour(rid, 0, -1), c + COLS
    elif c >= COLS:
        rid, c = neighbour(rid, 0, 1), c - COLS
    if rid is None:
        return None
    if r < 0:
        rid, r = neighbour(rid, -1, 0), r + ROWS
    elif r >= ROWS:
        rid, r = neighbour(rid, 1, 0), r - ROWS
    return (rid, c, r) if rid else None


def get(p):
    return GRID[p[0]][p[2]][p[1]] if p else '#'


def up(p): return norm(p[0], p[1], p[2] - 1) if p else None
def down(p): return norm(p[0], p[1], p[2] + 1) if p else None
def side(p, dx): return norm(p[0], p[1] + dx, p[2]) if p else None


# Tueren, Schluessel, Gegenstaende
doors, door_tiles, keys, gold, torch, start = [], set(), [], [], None, None
for rid in ROOMS:
    for r in range(ROWS):
        for c in range(COLS):
            ch = RAW[rid][r][c]
            if ch in DOORS and RAW[rid][r - 1][c] != ch:
                tiles = []
                rr = r
                while rr < ROWS and RAW[rid][rr][c] == ch:
                    tiles.append((rid, c, rr))
                    rr += 1
                door_tiles |= set(tiles)
                doors.append((DOORS[ch], tiles))
            elif ch in 'rby':
                keys.append((ch, (rid, c, r)))
            elif ch in 'gG':
                gold.append((rid, c, r))
            elif ch == 'T':
                torch = (rid, c, r)
            elif ch == 'P':
                start = (rid, c, r)


def solid(p):
    return p is None or get(p) == '#' or p in door_tiles


def supp(p):
    return p is None or get(p) in '#=~H' or p in door_tiles


def settle(p, drop):
    while True:
        if p is None or solid(p):
            return None
        if p[0] == TREASURE:
            return GOAL
        below = down(p)
        if get(p) == 'H' or supp(below):
            return p if drop <= MAX_FALL else None
        if get(p) == '|' or get(below) == '|':
            drop = 0                    # an der Stange rutscht man, das ist kein Sturz
        else:
            drop += 1
        p = below


_moves = {}


def moves(p):
    """alle Standplaetze, die man von p aus mit einer Aktion erreicht (alle Tueren zu)"""
    if p in _moves:
        return _moves[p]
    out = set()
    ch = get(p)
    for dx in (-1, 1):                  # laufen
        q = side(p, dx)
        if q and not solid(q) and not solid(up(q)):
            s = settle(q, 0)
            if s:
                out.add(s)
    if down(p) and get(down(p)) == 'H':  # Leiter
        out.add(down(p))
    if ch == 'H':
        u = up(p)
        if u and not solid(u):
            out.add(u)
    if supp(down(p)) or ch == 'H':       # springen
        for dy in (0, 1, 2):
            top, ok = p, True
            for _ in range(dy + 1):      # Kopf beim Steigen
                top = up(top)
                if top is None or solid(top):
                    ok = False
                    break
            if not ok:
                continue
            feet = down(top)             # Fusszeile auf Zielhoehe
            for sgn in (-1, 1):
                q_feet, q_head = feet, top
                for _ in range(2 if dy == 2 else 3):
                    q_feet, q_head = side(q_feet, sgn), side(q_head, sgn)
                    if q_feet is None or q_head is None or solid(q_feet) or solid(q_head) \
                            or get(q_feet) == '|' or get(q_head) == '|':
                        break
                    s = settle(q_feet, -dy)
                    if s:
                        out.add(s)
            if dy == 2:                  # gerade hoch durch eine duenne Plattform
                s = settle(feet, -dy)
                if s:
                    out.add(s)
    out.discard(p)
    _moves[p] = out
    return out


def valid(p):
    return p is not None and p[0] != TREASURE and not solid(p) and not solid(up(p)) and (get(p) == 'H' or supp(down(p)))


def components(nodes):
    """starke Zusammenhangskomponenten (Tarjan, ohne Rekursion); GOAL ist ein eigener Knoten"""
    index, low, comp, stack, on = {}, {}, {}, [], set()
    n = cid = 0
    for s in nodes:
        if s in index:
            continue
        index[s] = low[s] = n
        n += 1
        stack.append(s)
        on.add(s)
        work = [(s, iter(moves(s) if s != GOAL else ()))]
        while work:
            v, it = work[-1]
            for w in it:
                if w not in index:
                    index[w] = low[w] = n
                    n += 1
                    stack.append(w)
                    on.add(w)
                    work.append((w, iter(moves(w) if w != GOAL else ())))
                    break
                elif w in on:
                    low[v] = min(low[v], index[w])
            else:
                work.pop()
                if work:
                    u = work[-1][0]
                    low[u] = min(low[u], low[v])
                if low[v] == index[v]:
                    while True:
                        w = stack.pop()
                        on.discard(w)
                        comp[w] = cid
                        if w == v:
                            break
                    cid += 1
    return comp


def run():
    ok = True

    def report(text, cond):
        nonlocal ok
        ok = ok and cond
        print(('OK    ' if cond else 'FEHLER') + ' ' + text)

    # ---- Stufe A: Gebiete bei geschlossenen Tueren
    nodes = [(rid, c, r) for rid in ROOMS if rid != TREASURE for r in range(1, ROWS) for c in range(COLS) if valid((rid, c, r))]
    comp = components(nodes + [GOAL])
    leaves = {}                                        # Komponente -> Menge der Nachbar-Komponenten
    for p, k in comp.items():
        if p != GOAL:
            for q in moves(p):
                if comp[q] != k:
                    leaves.setdefault(k, set()).add(comp[q])
    sink_cache = {}

    def sinks(k):                                      # Gebiete (Senken), in denen man von k aus landen kann
        if k not in sink_cache:
            sink_cache[k] = frozenset([k]) if k not in leaves else frozenset().union(*[sinks(j) for j in leaves[k]])
        return sink_cache[k]

    def region(p):
        """Gebiet eines Standplatzes oder None, wenn er in mehrere Gebiete abfliessen kann"""
        s = sinks(comp[p])
        return next(iter(s)) if len(s) == 1 else None

    def stand(p):                                      # Standplatz zu einer Kachel (Gegenstand liegt auf Fuss- oder Kopfhoehe)
        for q in (p, down(p)):
            if q in comp:
                return q
        return None

    goal_region = comp[GOAL]
    start_region = region(start)
    report('Start fuehrt in genau ein Gebiet', start_region is not None)

    # Tueren verbinden die Standplaetze links und rechts
    edges = []
    for colour, tiles in doors:
        low = tiles[-1]
        sides = [settle(side(low, -1), 0), settle(side(low, 1), 0)]
        regs = [region(s) if s and s != GOAL else None for s in sides]
        good = all(r is not None for r in regs) and all(comp[s] == r or r == goal_region for s, r in zip(sides, regs))
        if not good:
            report('Tuer %s in Raum %s Spalte %d: beide Seiten liegen fest in einem Gebiet' % (colour, low[0], low[1]), False)
        edges.append((colour, regs[0], regs[1], low))

    # ---- Stufe B: Schluesselspiel ueber alle Mengen offener Tueren
    key_region = []
    for colour, pos in keys:
        s = stand(pos)
        key_region.append((colour, comp[s] if s and comp[s] not in leaves else None))
        report('Schluessel %s in Raum %s (%d,%d) liegt in einem Gebiet' % (colour, pos[0], pos[1], pos[2]), key_region[-1][1] is not None)

    def area(mask):                                    # Gebiete, die bei diesen offenen Tueren zusammenhaengen
        seen = {start_region}
        grew = True
        while grew:
            grew = False
            for i, (_, a, b, _) in enumerate(edges):
                if mask >> i & 1 and (a in seen) != (b in seen):
                    seen |= {a, b}
                    grew = True
        return seen

    def steps(mask, seen):
        out = []
        for i, (colour, a, b, _) in enumerate(edges):
            if not mask >> i & 1 and (a in seen or b in seen):
                have = sum(1 for c, k in key_region if c == colour and k in seen) \
                    - sum(1 for j, e in enumerate(edges) if e[0] == colour and mask >> j & 1)
                if have > 0:
                    out.append(mask | 1 << i)
        return out

    areas, rev, todo = {0: area(0)}, {0: []}, deque([0])
    while todo:
        m = todo.popleft()
        for m2 in steps(m, areas[m]):
            if m2 not in areas:
                areas[m2] = area(m2)
                rev[m2] = []
                todo.append(m2)
            rev[m2].append(m)
    winning = [m for m, a in areas.items() if goal_region in a]
    good = set(winning)
    todo = deque(winning)
    while todo:
        m = todo.popleft()
        for m0 in rev[m]:
            if m0 not in good:
                good.add(m0)
                todo.append(m0)
    everywhere = set().union(*areas.values())
    report('Schatzkammer erreichbar', bool(winning))
    for (colour, pos), (_, k) in zip(keys, key_region):
        if k not in everywhere:
            report('Schluessel %s in Raum %s erreichbar' % (colour, pos[0]), False)
    report('alle %d Schluessel erreichbar' % len(keys), all(k in everywhere for _, k in key_region))
    s = stand(torch)
    report('Fackel in Raum %s erreichbar' % torch[0], s is not None and comp[s] in everywhere)
    outside = [g for g in gold if g[0] != TREASURE]
    missing = [g for g in outside if stand(g) is None or comp[stand(g)] not in everywhere]
    report('Gold erreichbar: %d von %d (dazu %d in der Schatzkammer)' % (len(outside) - len(missing), len(outside),
                                                                      len(gold) - len(outside)), not missing)
    for g in missing[:10]:
        print('       fehlt:', g)
    for colour in 'bry':
        nk, nd = sum(1 for c, _ in keys if c == colour), sum(1 for c, _ in doors if c == colour)
        report('Farbe %s: %d Schluessel, %d Tueren' % (colour, nk, nd), nk == nd)
    bad = [m for m in areas if m not in good]
    report('keine Sackgasse (%d Staende mit offenen Tueren geprueft, %d Tueren, %d Gebiete)'
           % (len(areas), len(doors), len({e[k] for e in edges for k in (1, 2)} | {start_region})), not bad)
    for m in bad[:5]:
        print('       Sackgasse bei offenen Tueren:', [edges[i][3][:2] for i in range(len(edges)) if m >> i & 1])
    # Einbahnen: jeder erreichbare Standplatz darf nur in EIN Gebiet abfliessen
    split = [p for p in nodes if len(sinks(comp[p])) != 1 and any(j in everywhere for j in sinks(comp[p]))]
    report('jede Einbahn endet im selben Gebiet (%d Standplaetze)' % len(nodes), not split)
    for p in split[:10]:
        print('       mehrdeutig:', p)
    points = sum(100 if RAW[g[0]][g[2]][g[1]] == 'g' else 500 for g in gold)
    print('Raeume: %d, Punkte je Level: %d' % (len(ROOMS), points))
    return ok


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
