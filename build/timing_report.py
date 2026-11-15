# Gold Hunter - wertet das Zeitprotokoll aus (Resources\Data\timing_game.csv und timing_render.csv, von Main.vi beim Beenden
# geschrieben, siehe TIMING_LOG in gh_lib.py).
#   Spiel:  Abstand der Tick-Starts (soll 16.67 ms sein), verspaetete Ticks
#   Bild:   Abstand der Bilder, uebersprungene Ticks (Tick-Sprung > 1 = Claude springt im Bild um 8 statt 4 px), doppelte Bilder
# Aufruf: python timing_report.py
import os
from gh_lib import ROOT, TIMING_GAME, TIMING_RENDER, FPS

DATA = os.path.join(ROOT, 'Resources', 'Data')


def load(name):
    rows = []
    for line in open(os.path.join(DATA, name)).read().splitlines()[1:]:
        if ';' in line:
            ms, tick = line.split(';')
            rows.append((int(ms) & 0xFFFFFFFF, int(tick)))
    rows.sort()
    return rows


def hist(values, edges):
    out = []
    for lo, hi in zip(edges, edges[1:]):
        n = sum(1 for v in values if lo <= v < hi)
        out.append('%3d-%3d ms: %5d' % (lo, hi, n))
    return out


def main():
    period = 1000 / FPS
    g = load(TIMING_GAME)
    r = [x for x in load(TIMING_RENDER) if x[1] >= 0]
    print('Spiel: %d Ticks, %.1f s' % (len(g), (g[-1][0] - g[0][0]) / 1000))
    dg = [b[0] - a[0] for a, b in zip(g, g[1:])]
    print('  Abstand der Tick-Starts: Mittel %.2f ms (Soll %.2f), min %d, max %d' % (sum(dg) / len(dg), period, min(dg), max(dg)))
    for line in hist(dg, [0, 10, 15, 16, 17, 18, 20, 25, 34, 1000]):
        print('   ', line)
    late = [(g[k + 1][1], d) for k, d in enumerate(dg) if d > 25]
    print('  Ticks mehr als 25 ms nach dem vorigen: %d %s' % (len(late), late[:15]))
    print('Bild: %d Bilder' % len(r))
    dr = [b[0] - a[0] for a, b in zip(r, r[1:])]
    jumps = [b[1] - a[1] for a, b in zip(r, r[1:])]
    print('  Abstand der Bilder: Mittel %.2f ms, min %d, max %d' % (sum(dr) / len(dr), min(dr), max(dr)))
    for line in hist(dr, [0, 10, 15, 16, 17, 18, 20, 25, 34, 1000]):
        print('   ', line)
    from collections import Counter
    c = Counter(jumps)
    print('  Tick-Schritt von Bild zu Bild:', dict(sorted(c.items())))
    skips = [(r[k + 1][1], j, r[k + 1][0] - r[k][0]) for k, j in enumerate(jumps) if j > 1]
    print('  uebersprungene Ticks (Tick, Schritt, ms seit dem vorigen Bild): %d %s' % (len(skips), skips[:20]))
    if len(skips) > 2:
        gaps = [b[0] - a[0] for a, b in zip(skips, skips[1:])]
        print('  Abstand zwischen zwei Spruengen (Ticks): %s' % gaps[:20])


if __name__ == '__main__':
    main()
