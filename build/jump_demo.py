# Gold Hunter - Demo ohne Gegnerberuehrung: setzt in die geplante Demo (demo_events.py) Spruenge ueber die Gegner ein.
#   Python-Nachbau mit Gegnern (sim_enemies.py, gleiche Zufallszahlen wie LabVIEW). Fuer jede Beruehrung wird ein Sprung kurz davor
#   gesucht, nach dem Claude wieder genau im alten Zustand ankommt (gleicher Ort, gleicher Tick) - der Rest der Demo bleibt dann
#   gleich, denn die Gegner bewegen sich unabhaengig von Claude (nur Raum und Zeit zaehlen).
# Aufruf: python jump_demo.py   (nach plan_demo.py; schreibt demo_events.py neu, mit JUMPED = True)
import copy
import os
import sys

from gh_lib import IN
import demo_events as de
from sim_enemies import EnemySim

HERE = os.path.dirname(os.path.abspath(__file__))
LOOK_BACK = 40          # so viele Ticks vor der Beruehrung darf der Sprung beginnen
REJOIN = 150            # innerhalb so vieler Ticks muss Claude wieder im alten Zustand sein


def key_of(s):
    # Punkte und Leben zaehlen nicht: eine Muenze mehr (z. B. auf einer Plattform beim Sprung) aendert Claudes Weg nicht
    return (s.room, s.x10, s.y10, s.mode, s.vy, s.run, s.vert, tuple(s.keys), s.torch)


def baseline(events, end):
    """ganze Demo: Zustand je Tick und die Ticks mit Beruehrung"""
    s = EnemySim()
    states, hits = [], []
    for t in range(end):
        s.step(IN[events.get(t, 'None')])
        states.append(key_of(s))
        if s.hit:
            hits.append(t)
        if s.dead and s.room != de_room_treasure():
            print('toedlicher Sturz bei Tick', t)
    return states, hits


def de_room_treasure():
    import sim_player as sp
    return sp.TREASURE_ID


def checkpoint(events, tick):
    s = EnemySim()
    for t in range(tick):
        s.step(IN[events.get(t, 'None')])
    return s


def try_patch(events, states, cp, cp_tick, patch, th):
    """zusaetzliche Tasten patch {Tick: Taste}: Tick der Rueckkehr, wenn Claude ohne Beruehrung und Tod wieder genau im alten
    Zustand ist (nach der letzten zusaetzlichen Taste und nach der Beruehrung), sonst None"""
    s = copy.deepcopy(cp)
    first, last = min(patch), max(patch)
    for t in range(cp_tick, min(len(states), last + REJOIN)):
        s.step(IN[patch.get(t) or events.get(t, 'None')])
        if t >= first:
            if s.dead or s.hit:
                return None
            if t > th and t > last and key_of(s) == states[t]:
                return t
    return None


VERT_KEY = {-1: 'Up', 1: 'Down'}


def candidates(events, states, tj):
    """Sprung bei tj; haelt Claude dabei eine Pfeiltaste hoch/runter, wuerde er im Sprung eine Leiter packen - dann die Taste
    davor loslassen und nach der Landung wieder druecken"""
    yield {tj: 'Jump'}
    vert = states[tj - 1][6] if tj > 0 else 0
    if vert and tj - 1 not in events:
        for dly in (40, 44, 48, 52, 36, 56, 60, 70, 80):
            t3 = tj + dly
            if t3 not in events and not any(tj < t < t3 for t in events):
                yield {tj - 1: 'ReleaseV', tj: 'Jump', t3: VERT_KEY[vert]}


RUN_KEY = {-1: 'Left', 1: 'Right'}


def resync(events, states, tj):
    """Sprung ueber einem Foerderband: in der Luft traegt das Band nicht, Claude ist nach der Landung voraus - kurz stehen bleiben,
    bis der alte Weg ihn eingeholt hat, dann weiter"""
    run, vert = states[tj - 1][5], states[tj - 1][6]
    if not run or (vert and tj - 1 in events):
        return
    for land in range(36, 52, 2):
        tw = tj + land
        for k in range(1, 24):
            if not any(tj <= t <= tw + k + 1 for t in events):
                p = {tj: 'Jump', tw: 'Release', tw + k: RUN_KEY[run]}
                if vert:                        # Pfeil hoch/runter fuer den Sprung loslassen, danach wieder druecken
                    p[tj - 1] = 'ReleaseV'
                    p[tw + k + 1] = VERT_KEY[vert]
                yield p


def find_jumps(events, states, cp, cp_tick, th):
    """spaet springen sieht natuerlicher aus: vom letzten moeglichen Tick rueckwaerts"""
    for gen in (candidates, resync):
        for tj in range(th, max(cp_tick, th - LOOK_BACK) + 1, -1):
            if tj in events:
                continue
            for patch in gen(events, states, tj):
                t = try_patch(events, states, cp, cp_tick, patch, th)
                if t is not None:
                    return patch, t
    return None


def main():
    events = dict(de.DEMO_EVENTS)
    end = de.DEMO_LEN
    states, hits = baseline(events, end)
    print('Beruehrungen vorher: %d Ticks' % len(hits))
    treasure = de.DEMO_TREASURE_TICK
    fixed, paused, failed, done_upto = 0, 0, [], -1
    while True:
        rest = [t for t in hits if t > done_upto]
        if not rest:
            break
        th = rest[0]
        best = fix_one(events, states, th)
        if best:
            events.update(best[0])
            fixed += 1
            states, hits = baseline(events, end)
            done_upto = best[1]
            print('  Beruehrung Tick %5d: %s, wieder auf der alten Bahn bei %5d' % (th, sorted(best[0].items()), best[1]), flush=True)
            continue
        pz = pause_fix(events, states, end, th)
        if pz:
            events, states, hits, dl, done_upto = pz
            end += dl
            treasure += dl
            paused += 1
            continue
        failed.append(th)
        # diese Beruehrung (die ganze Strecke) ueberspringen
        run_end = th
        while run_end + 1 in hits:
            run_end += 1
        done_upto = run_end
        print('  Beruehrung Tick %5d: weder Sprung noch Warten hilft' % th, flush=True)
    states, hits = baseline(events, end)
    print('Spruenge eingesetzt: %d, Wartepausen: %d, nicht loesbar: %s, Beruehrungs-Ticks danach: %d, Demo %d Ticks'
          % (fixed, paused, failed, len(hits), end))
    ev = sorted(events.items())
    with open(os.path.join(HERE, 'demo_events.py'), 'w') as f:
        f.write('# erzeugt von plan_demo.py und jump_demo.py - Demo vom Start ueber die Fackel bis in die Schatzkammer, Spruenge ueber die Gegner\n')
        f.write('DEMO_EVENTS = %r\n' % ev)
        f.write('DEMO_LEN = %d\n' % end)
        f.write('DEMO_TREASURE_TICK = %d\n' % treasure)
        f.write('JUMPED = True\n')


def fix_one(events, states, th):
    cp_tick = max(th - LOOK_BACK, 0)
    return find_jumps(events, states, checkpoint(events, cp_tick), cp_tick, th)


PAUSES = (20, 40, 60, 90, 120, 160, 200, 240)


def pause_fix(events, states, end, th):
    """Claude bleibt vor der Beruehrung eine Weile stehen (Gegner laufen weiter), danach laeuft die Demo um die Pause verschoben
    weiter. Gilt nur, wenn Claudes Weg danach genau gleich bleibt (Schwundboeden haben ihren eigenen Rhythmus) und alle
    Beruehrungen in der Naehe sich mit Spruengen loesen lassen (auch Spruenge auf der Stelle waehrend der Pause)."""
    for dl in PAUSES:
        for tp in range(th - 4, max(th - 200, 1), -6):
            if any(t in events for t in range(tp - 1, tp + 3)):
                continue
            st = states[tp - 1]
            room, x10, y10, mode, vy, run, vert = st[:7]
            # stehen bleiben auf festem Boden, oder auf einer Leiter anhalten (Klettern ohne seitliche Bewegung)
            if vy != 0 or not (mode == 0 or (mode == 1 and run == 0 and vert != 0)):
                continue
            new = {t: k for t, k in events.items() if t < tp}
            if run:
                new[tp] = 'Release'
                if vert:
                    new[tp + 1] = 'ReleaseV'
                new[tp + dl] = RUN_KEY[run]
                if vert:
                    new[tp + dl + 1] = VERT_KEY[vert]
            elif vert:
                new[tp] = 'ReleaseV'
                new[tp + dl] = VERT_KEY[vert]
            # steht er schon still (keine Taste), verschiebt sich nur der Rest
            for t, k in events.items():
                if t >= tp + 3:
                    new[t + dl] = k
            # Claudes Weg: bis tp gleich, ab tp+dl+2 der alte, um dl verschoben
            s = checkpoint(new, tp)
            ok = True
            for t in range(tp, end + dl):
                s.step(IN[new.get(t, 'None')])
                if s.dead and s.room != de_room_treasure():
                    ok = False
                    break
                if t >= tp + dl + 2 and key_of(s) != states[t - dl]:
                    ok = False
                    break
            if not ok:
                continue
            # Beruehrungen von der Pause bis kurz nach der alten Stelle: alle mit Spruengen loesbar?
            n_states, n_hits = baseline(new, end + dl)
            done, trial = tp - 1, dict(new)
            good = True
            while True:
                near = [t for t in n_hits if done < t <= th + dl + 120]
                if not near:
                    break
                b = fix_one(trial, n_states, near[0])
                if not b:
                    good = False
                    break
                trial.update(b[0])
                n_states, n_hits = baseline(trial, end + dl)
                done = b[1]
            if good:
                print('  Beruehrung Tick %5d: %d Ticks warten ab Tick %d, dann um %d verschoben weiter' % (th, dl, tp, dl), flush=True)
                return trial, n_states, n_hits, dl, max(done, th + dl)
    return None


if __name__ == '__main__':
    if getattr(de, 'JUMPED', False) and 'nochmal' not in sys.argv:
        sys.exit('demo_events.py hat schon Spruenge (python jump_demo.py nochmal, um weitere zu suchen)')
    main()
