# Gold Hunter - plant die Demo: vom Start ueber die Fackel bis in die Schatzkammer.
#   Stufe 1 (Kacheln): Breitensuche ueber Standplaetze + gesammelte Schluessel + offene Tueren + Fackel
#                      (Bewegungsmodell aus check_levels.py). Ergebnis: Kachel-Weg.
#   Stufe 2 (Ticks):   fuer jeden Schritt des Wegs sucht eine Bestensuche im Python-Nachbau (sim_player.py) die Tastenfolge,
#                      mit der Claude genau auf die naechste Kachel kommt (Schwundboeden, Foerderbaender, Tueren, Stuerze inklusive).
#   Gegner werden nicht beachtet: in der Demo ist Claude unverwundbar (Game_Step).
# Ergebnis: build\demo_events.py (DEMO_EVENTS, DEMO_LEN) - gen_play.py liest es.
# Aufruf: python plan_demo.py
import heapq
import os
import sys
import time
from collections import deque

import check_levels as cl
import gh_lib
import sim_player as sp

HERE = os.path.dirname(os.path.abspath(__file__))
K = gh_lib.IN
TILE, COLS, ROWS = gh_lib.TILE, gh_lib.COLS, gh_lib.ROWS
TREASURE_ROOM = cl.TREASURE
CHAR = {v: k for k, v in gh_lib.TILE_CODE.items()}
Y_WEIGHT = 3.0                                     # Gewicht der Hoehe in der Schaetzung (Stuerze sehen sonst zu gut aus)
CYCLE = gh_lib.LV_ON[0] + gh_lib.LV_OFF[0]          # Rhythmus der Schwundboeden in Level 1 (Ticks)


# ------------------------------------------------------------------ Stufe 1: Kachel-Weg
DOORS = cl.doors                                   # [(Farbe, [Kacheln])]
KEYS = cl.keys                                     # [(Farbe 'r'/'b'/'y', Kachel)]
_move_cache = {}


def closed_tiles(opened):
    return set(t for i, (_, tiles) in enumerate(DOORS) if not opened >> i & 1 for t in tiles)


# Zuege aendern sich nur in der Naehe einer Tuer: dort zaehlt, welche der nahen Tueren offen sind; sonst gilt "alle zu"
NEAR = {}
for _i, (_, _tiles) in enumerate(DOORS):
    for (_rid, _c, _r) in _tiles:
        for _dc in range(-4, 5):
            for _dr in range(-4, 5):
                NEAR.setdefault((_rid, _c + _dc, _r + _dr), set()).add(_i)


def moves(p, opened):
    near = NEAR.get(p) if p != cl.GOAL else None
    sub = 0
    if near:
        for i in near:
            sub |= opened & (1 << i)
    cache = _move_cache.setdefault(sub, {})
    if p not in cache:
        cl.door_tiles = closed_tiles(sub)
        cl._moves = cache
        cl.moves(p)
    return cache[p]


def key_spots():
    out = {}
    for i, (_, pos) in enumerate(KEYS):
        for q in (pos, cl.down(pos)):
            if q:
                out.setdefault(q, []).append(i)
    return out


_bfs_cache = {}


def bfs(p0, opened):
    """Breitensuche ueber Standplaetze bei diesen offenen Tueren; liefert die Vorgaenger (fuer Wege) und damit die Erreichbaren."""
    if (p0, opened) in _bfs_cache:
        return _bfs_cache[(p0, opened)]
    if len(_bfs_cache) > 300:
        _bfs_cache.clear()
    prev = {p0: None}
    todo = deque([p0])
    while todo:
        p = todo.popleft()
        if p == cl.GOAL:
            continue
        for q in moves(p, opened):
            if q not in prev:
                prev[q] = p
                todo.append(q)
    _bfs_cache[(p0, opened)] = prev
    return prev


def walk(prev, q):
    path = []
    while q is not None:
        path.append(q)
        q = prev[q]
    return path[::-1]


def door_sides(i):
    low = DOORS[i][1][-1]
    return [s for s in (cl.side(low, -1), cl.side(low, 1)) if s]


def tile_route():
    """Abstrakte Breitensuche: welche Tueren in welcher Reihenfolge (jede mit dem naechsten erreichbaren Schluessel ihrer Farbe),
    bis Fackel und Schatzkammer erreichbar sind; dann der Kachel-Weg Start -> Schluessel -> Tuer -> ... -> Fackel -> Schatzkammer."""
    torch_spots = [q for q in (cl.torch, cl.down(cl.torch)) if q]
    key_spot = {i: [q for q in (pos, cl.down(pos)) if q] for i, (_, pos) in enumerate(KEYS)}
    start = (cl.start, 0, 0)
    prev_state = {start: None}
    seen_masks = {(0, 0)}
    todo = deque([start])
    while todo:
        st = todo.popleft()
        pos, opened, used = st
        reach = bfs(pos, opened)
        torch = next((q for q in torch_spots if q in reach), None)
        if torch and cl.GOAL in bfs(torch, opened):
            plan = []
            while st:
                plan.append(st)
                st = prev_state[st]
            plan = plan[::-1]
            # Kachel-Weg zusammensetzen
            route, here, have_torch = [cl.start], cl.start, False
            for (p1, op1, us1), (p2, op2, us2) in zip(plan, plan[1:]):
                # die Fackel holen, sobald sie erreichbar ist (dann sind die dunklen Raeume hell)
                tq = next((q for q in torch_spots if q in bfs(here, op1)), None)
                if not have_torch and tq:
                    route += walk(bfs(here, op1), tq)[1:]
                    here, have_torch = tq, True
                k = (us2 & ~us1).bit_length() - 1
                kq = next(q for q in key_spot[k] if q in bfs(here, op1))
                route += walk(bfs(here, op1), kq)[1:]
                route += walk(bfs(kq, op1), p2)[1:]
                here = p2
            if not have_torch:
                route += walk(bfs(here, opened), torch)[1:]
                here = torch
            route += walk(bfs(here, opened), cl.GOAL)[1:]
            doors_used = [(DOORS[(b[1] & ~a[1]).bit_length() - 1][0], (b[1] & ~a[1]).bit_length() - 1) for a, b in zip(plan, plan[1:])]
            print('Tueren in dieser Reihenfolge:', doors_used)
            return route
        for j, (colour, tiles) in enumerate(DOORS):
            if opened >> j & 1:
                continue
            sides = door_sides(j)
            side = next((s for s in sides if s in reach), None)
            if side is None or all(s in reach for s in sides):   # nur Tueren, hinter denen Neues liegt
                continue
            cands = [(len(walk(reach, q)), i, q) for i, (c, _) in enumerate(KEYS) if c == colour and not used >> i & 1
                     for q in key_spot[i] if q in reach]
            if not cands:
                continue
            _, i, q = min(cands)
            if side not in bfs(q, opened):
                continue
            s2 = (side, opened | 1 << j, used | 1 << i)
            if (s2[1], s2[2]) not in seen_masks:
                seen_masks.add((s2[1], s2[2]))
                prev_state[s2] = st
                todo.append(s2)
    raise SystemExit('kein Weg zur Schatzkammer mit Fackel gefunden')

# ------------------------------------------------------------------ Stufe 2: Tasten
class FastSim(sp.Sim):
    """Sim mit Kopieren beim Schreiben: Raeume werden erst kopiert, wenn ein Gegenstand oder eine Tuer darin verschwindet."""

    def clone(self):
        s = FastSim.__new__(FastSim)
        s.__dict__.update(self.__dict__)
        s.grid = dict(self.grid)
        s.keys = self.keys[:]
        s._own = set()
        return s

    def _mine(self):
        if self.room not in getattr(self, '_own', set()):
            self.grid[self.room] = [row[:] for row in self.grid[self.room]]
            self._own = getattr(self, '_own', set()) | {self.room}

    def collect(self):
        self._mine()
        super().collect()

    def door(self):
        self._mine()
        super().door()


def where(s):
    x, y = s.x10 // 10, s.y10 // 10
    return s.room, (x + 16) // TILE, (y + 47) // TILE


ACTIONS = [(k, w) for k in ('None', 'Right', 'Left', 'Release', 'Up', 'Down', 'ReleaseV', 'Jump') for w in (1, 4, 10)] + [('Release', 30), ('Release', 60)]


def reach(s0, target, budget=150000):
    """Bestensuche: Tastenfolge [(Tick, Taste)] vom Zustand s0 bis Claude auf der Kachel target steht (bzw. an der Leiter haengt)."""
    goal_room, gc, gr = target if target != cl.GOAL else (TREASURE_ROOM, None, None)
    ladder = target != cl.GOAL and cl.get(target) == 'H'
    tx, ty = (gc * TILE, (gr + 1) * TILE - 48) if target != cl.GOAL else (0, 0)

    def done(s):
        if target == cl.GOAL:
            return s.room == TREASURE_ROOM          # schon im Fallen: in der Schatzkammer zaehlt ein Sturz nicht (wie im Spiel)
        return where(s) == target and (s.mode == 0 or (ladder and s.mode == 1)) and s.vy == 0

    def h(s):
        if target == cl.GOAL:                    # Schatzkammer: senkrecht unter dem letzten Raum
            d1, c1 = sp.WHERE[s.room]
            d2, c2 = sp.WHERE[TREASURE_ROOM]
            return 0 if s.room == TREASURE_ROOM else abs(c2 - c1) * gh_lib.W + (d2 - d1) * gh_lib.FIELD_H - s.y10 // 10
        # Entfernung in Weltkoordinaten (Raumversatz: Breite und Hoehe eines Raums)
        d1, c1 = sp.WHERE[s.room]
        d2, c2 = sp.WHERE[goal_room]
        gx, gy = tx + (c2 - c1) * gh_lib.W, ty + (d2 - d1) * gh_lib.FIELD_H
        return abs(s.x10 // 10 - gx) + abs(s.y10 // 10 - gy) * Y_WEIGHT

    cnt = 0
    heap = [(h(s0), 0, cnt, s0, [])]
    seen = set()
    while heap and cnt < budget:
        _, g, _, s, ev = heapq.heappop(heap)
        if done(s):
            return s, ev
        # Zeit im Rhythmus der Schwundboeden gehoert dazu - sonst gilt Warten als schon gesehen
        key = (s.room, s.x10 // 10, s.y10 // 10, s.mode, s.vy, s.run, s.vert, (s.tick % CYCLE) // 15)
        if key in seen:
            continue
        seen.add(key)
        for k, w in ACTIONS:
            if k == 'None' and w == 1:
                continue
            t = s.clone()
            evs = ev + ([(t.tick, k)] if k != 'None' else [])
            dead = False
            for i in range(w):
                t.step(K[k] if i == 0 and k != 'None' else 0)
                if getattr(t, 'dead', False):
                    dead = True
                    break
                if done(t):
                    break
            if dead:
                continue
            cnt += 1
            heapq.heappush(heap, (g + w + h(t) * 1.5, g + w, cnt, t, evs))
    return None, None


def main():
    t0 = time.time()
    # Kachel-Weg zwischenspeichern (dauert ~2.5 min); neu rechnen mit: python plan_demo.py neu
    cache = os.path.join(HERE, 'demo_route.json')
    import json
    if os.path.exists(cache) and 'neu' not in sys.argv:
        route = [tuple(p) if isinstance(p, list) else p for p in json.load(open(cache))]
    else:
        route = tile_route()
        json.dump(route, open(cache, 'w'))
    print('Kachel-Weg: %d Schritte, Raeume %s' % (len(route), ' '.join(dict.fromkeys(p[0] if p != cl.GOAL else 'GOAL' for p in route))))
    # Zwischenziele nur auf festem Boden: auf einem Schwundboden ('~' darunter) darf ein Teilstueck nicht enden
    route = [p for k, p in enumerate(route) if k == 0 or p == cl.GOAL or cl.get(cl.down(p)) != '~']
    print('Zwischenziele auf festem Boden:', len(route))
    s = FastSim()
    events = []
    for i, (st, nx) in enumerate(zip(route, route[1:])):
        global Y_WEIGHT
        for wy in (3.0, 0.7, 6.0):                  # klappt es nicht, mit anderer Gewichtung noch einmal
            Y_WEIGHT = wy
            s2, ev = reach(s, nx)
            if s2 is not None:
                break
        if s2 is None:
            print('Schritt %d: %s -> %s nicht gefunden (Tick %d)' % (i, st, nx, s.tick))
            print('  Claude', where(s), 'x,y', s.x10 // 10, s.y10 // 10, 'Modus', s.mode, 'Schluessel r/b/y', s.keys, 'Fackel', s.torch)
            import json
            json.dump(events, open(os.path.join(HERE, 'demo_partial.json'), 'w'))
            g = s.grid[s.room]
            print('  Raum', s.room); [print('   ', ''.join(CHAR.get(v, '?') for v in row)) for row in g]
            sys.exit(1)
        events += ev
        s = s2
        if i % 50 == 0:
            print('  Schritt %d/%d, Tick %d, Raum %s' % (i, len(route), s.tick, s.room), flush=True)
    # in der Schatzkammer am Fallschirm hinunterschweben, dann nach rechts durchs Gold laufen
    entered = s.tick
    while s.mode != 0 and s.tick < entered + 900:
        s.step(0)
    events.append((s.tick, 'Right'))
    end = s.tick + 240
    # doppelte Ticks zusammenlegen (letzte Taste gilt)
    merged = {}
    for t, k in events:
        merged[t] = k
    events = sorted(merged.items())
    print('Demo: %d Tasten, Ende bei Tick %d (%.0f s), Schluessel %s, Fackel %s, Punkte %d, %.1f s gerechnet'
          % (len(events), end, end / gh_lib.FPS, s.keys, s.torch, s.score, time.time() - t0))
    with open(os.path.join(HERE, 'demo_events.py'), 'w') as f:
        f.write('# erzeugt von plan_demo.py - Demo vom Start ueber die Fackel bis in die Schatzkammer\n')
        f.write('DEMO_EVENTS = %r\n' % events)
        f.write('DEMO_LEN = %d\n' % end)
        f.write('DEMO_TREASURE_TICK = %d\n' % entered)


if __name__ == '__main__':
    main()
