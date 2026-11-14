# Gold Hunter - rechnet die Demo-Tastenfolge (DEMO_EVENTS) fuer neue Laufwerte um.
#   Spielt die alte Folge mit den alten Werten ab und merkt sich Claudes Lage bei jedem Ereignis. Dann wird mit den
#   aktuellen Werten (gh_lib) jedes Ereignis gefeuert, sobald Claude dieselbe Lage erreicht. Vor jeder neuen Bewegung
#   wird, wenn noetig, die kleinste Pause eingefuegt, mit der das naechste Ziel erreicht wird (Schwundboeden im Rhythmus).
# Aufruf: python retime_demo.py <alter WALK10> <alter BELT10>
import copy
import sys
import gh_lib
import sim_player
from gen_play import DEMO_EVENTS

old_walk, old_belt = int(sys.argv[1]), int(sys.argv[2])
new_walk, new_belt = gh_lib.WALK10, gh_lib.BELT10
K = gh_lib.IN
MOVES = ('Right', 'Left', 'Down', 'Up')


def lage(s):
    return (s.x10 // 10, s.y10 // 10, s.mode, s.room)


def trace(walk, belt, events, upto):
    sim_player.WALK10, sim_player.BELT10 = walk, belt
    s = sim_player.Sim()
    ev = dict((t, K[k]) for t, k in events)
    out = []
    for t in range(upto):
        out.append(lage(s))
        s.step(ev.get(t, 0))
    return out


def reached(here, target, move):
    x, y, m, r = target
    if here[3] != r or here[2] != m:
        return False
    if move == 'Right':
        return here[0] >= x and here[1] == y
    if move == 'Left':
        return here[0] <= x and here[1] == y
    if move in ('Down', 'Up'):
        return here[1] == y
    return True


def failed(here, target):
    return here[3] != target[3] or here[1] > target[1] + 2 * gh_lib.TILE   # falscher Raum oder tief gefallen


old = trace(old_walk, old_belt, DEMO_EVENTS, gh_lib.DEMO_LEN)
targets = [(k, old[t]) for t, k in DEMO_EVENTS]

sim_player.WALK10, sim_player.BELT10 = new_walk, new_belt
s, t, out = sim_player.Sim(), 0, []
i = 0
while i < len(targets):
    k, tgt = targets[i]
    if k not in MOVES:                          # Loslassen: sofort
        s.step(K[k]); out.append((t, k)); t += 1; i += 1
        continue
    # Bewegung k bis zum Ziel des naechsten Ereignisses; kleinste Pause davor suchen
    goal = targets[i + 1][1] if i + 1 < len(targets) else None
    for pause in range(0, 400):
        trial = copy.deepcopy(s)
        for _ in range(pause):
            trial.step(0)
        trial.step(K[k])
        n, ok = 0, goal is None
        while not ok and n < 900:
            if failed(lage(trial), goal) or getattr(trial, 'dead', False):
                break
            if reached(lage(trial), goal, k):
                ok = True
                break
            trial.step(0)
            n += 1
        if ok:
            break
    else:
        raise SystemExit('kein Weg fuer Ereignis %d (%s)' % (i, k))
    for _ in range(pause):
        s.step(0); t += 1
    s.step(K[k]); out.append((t, k)); t += 1
    if goal is not None:
        while not reached(lage(s), goal, k):
            s.step(0); t += 1
    i += 1
print('old:', DEMO_EVENTS)
print('new:', out)
chk = trace(new_walk, new_belt, out, gh_lib.DEMO_LEN)
print('positions old:', [o for _, o in targets])
print('positions new:', [chk[t] for t, _ in out])
print('last tick', out[-1][0], 'of', gh_lib.DEMO_LEN)
