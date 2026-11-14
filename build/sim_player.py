# Gold Hunter - Python-Nachbau von Player_Move, Room_Change und Game_Step (gleiche Regeln, gleiche Zahlen).
# Liefert die Sollwerte fuer Tests\Test_Run.vi:   python sim_player.py
from gh_lib import *
from gh_levels import ROOMS, WORLD

T_ = TILE_CODE
ORDER = [rid for row in WORLD for rid in row if rid]
GRID = {rid: [[T_.get(ch, 0) for ch in line] for line in ROOMS[rid].lines()] for rid in ORDER}
WHERE = {rid: (d, x) for d, row in enumerate(WORLD) for x, rid in enumerate(row) if rid}


def fdiv(a, b):
    return a // b


class Sim:
    def __init__(self):
        self.room = ORDER[0]
        g = GRID[self.room]
        prow = next(r for r in range(ROWS) if T_['P'] in g[r])
        pcol = g[prow].index(T_['P'])
        self.y10 = ((prow + 1) * TILE - CLAUDE_H) * 10
        self.x10 = pcol * TILE * 10
        self.vy, self.mode, self.run, self.vert, self.facing = 0, 0, 0, 0, 0
        self.stand = self.y10 // 10
        self.entry = (self.x10, self.y10, 0)
        self.lives, self.tick = LIVES, 0
        self.min_y, self.air = 100000, 0

    def tile(self, x, y):
        col = min(max(fdiv(x, TILE), 0), COLS - 1)
        row = min(max(fdiv(y, TILE), 0), ROWS - 1)
        return GRID[self.room][row][col]

    def move(self, jump):
        sol = lambda c: c in SOLID
        pla = lambda c: c in PLATFORM
        lad = lambda c: c in CLIMBABLE
        pol = lambda c: c == T_['|']
        top = lambda y: fdiv(y, TILE) * TILE
        x10, y10, mode, run, vert, stand = self.x10, self.y10, self.mode, self.run, self.vert, self.stand
        x, y = fdiv(x10, 10), fdiv(y10, 10)
        feet = y + CLAUDE_H
        under = self.tile(x + 16, feet)
        belt = -BELT10 if under == T_['<'] else BELT10 if under == T_['>'] else 0
        dx = (run * WALK10 if mode in (0, 2) else 0) + (belt if mode == 0 else 0)
        nx10 = x10 + dx
        nx = fdiv(nx10, 10)
        lead = nx + BOX_R if dx > 0 else nx + BOX_L
        wall = sol(self.tile(lead, y + 2)) or sol(self.tile(lead, y + 24)) or sol(self.tile(lead, feet - 2))
        xa10 = x10 if (dx != 0 and wall) else nx10
        xa = fdiv(xa10, 10)
        cx, lf, rt = xa + 16, xa + BOX_L, xa + BOX_R
        snap10 = fdiv(cx, TILE) * TILE * 10
        dead = False
        if mode == 0:
            gL, gR, gC = self.tile(lf, feet), self.tile(rt, feet), self.tile(cx, feet)
            sup = sol(gL) or sol(gR) or pla(gL) or pla(gR) or lad(gC)
            to_lad = (vert == -1 and lad(self.tile(cx, feet - 2))) or (vert == 1 and lad(gC))
            on_pole = (not sup) and pol(self.tile(cx, y + 24))
            n_mode = 2 if jump else 1 if to_lad else 0 if sup else 3 if on_pole else 2
            n_x10 = snap10 if (not jump and (to_lad or on_pole)) else xa10
            n_y10 = y10 + vert * CLIMB10 if (not jump and to_lad) else y10
            n_vy = JUMP10 if jump else 0
        elif mode == 2:
            vy = min(self.vy + GRAVITY10, VY_MAX10)
            ay10 = y10 + vy
            ay = fdiv(ay10, 10)
            afeet = ay + CLAUDE_H
            rising = vy < 0
            bump = rising and (sol(self.tile(lf, ay)) or sol(self.tile(rt, ay)))
            a_top = top(afeet)
            crossed = feet <= a_top <= afeet
            aL, aR, aC = self.tile(lf, afeet), self.tile(rt, afeet), self.tile(cx, afeet)
            lad_top = lad(aC) and not lad(self.tile(cx, afeet - TILE))
            land = (not rising) and crossed and (sol(aL) or sol(aR) or pla(aL) or pla(aR) or lad_top)
            land_y = a_top - CLAUDE_H
            mid = self.tile(cx, ay + 24)
            grab_l = lad(mid) and (vert != 0 or (mid == T_[':'] and vy > 0))
            grab_p = pol(mid) and vy > 0
            grab = (not land) and (grab_l or grab_p)
            n_mode = 0 if land else 1 if grab_l else 3 if grab_p else 2
            n_y10 = land_y * 10 if land else y10 if bump else ay10
            n_vy = 0 if (land or bump or grab) else vy
            n_x10 = snap10 if grab else xa10
            dead = land and (land_y - stand > MAX_FALL)
        elif mode == 1:
            ly10 = y10 + vert * CLIMB10
            ly = fdiv(ly10, 10)
            lfeet = ly + CLAUDE_H
            up, down = vert == -1, vert == 1
            ceiling = up and sol(self.tile(cx, ly))
            at_top = up and not ceiling and not lad(self.tile(cx, lfeet - 2))
            floor = down and sol(self.tile(cx, lfeet))
            rope_end = down and not lad(self.tile(cx, lfeet - 2)) and not lad(self.tile(cx, lfeet))
            step_off = run != 0 and vert == 0
            n_mode = 2 if jump else 0 if (at_top or floor) else 2 if (rope_end or step_off) else 1
            n_y10 = (top(lfeet - 2) + TILE - CLAUDE_H) * 10 if at_top else (top(lfeet) - CLAUDE_H) * 10 if floor else y10 if ceiling else ly10
            n_vy = JUMP10 if jump else 0
            n_x10 = x10
        else:
            py10 = y10 + SLIDE10
            py = fdiv(py10, 10)
            pfeet = py + CLAUDE_H
            p_floor = sol(self.tile(cx, pfeet))
            p_end = not pol(self.tile(cx, py + 24)) and not pol(self.tile(cx, pfeet))
            n_mode = 0 if p_floor else 2 if p_end else 3
            n_y10 = (top(pfeet) - CLAUDE_H) * 10 if p_floor else py10
            n_vy, n_x10 = 0, x10
        self.x10, self.y10, self.vy, self.mode = n_x10, n_y10, n_vy, n_mode
        if n_mode != 2:
            self.stand = fdiv(n_y10, 10)
        self.facing = 0 if run > 0 else 1 if run < 0 else self.facing
        return dead

    def change(self):
        cx, cy = fdiv(self.x10, 10) + 16, fdiv(self.y10, 10) + 24
        dc = -1 if cx < 0 else 1 if cx >= W else 0
        dd = -1 if cy < 0 else 1 if cy >= FIELD_H else 0
        if dc or dd:
            d, c = WHERE[self.room]
            target = [r for r, (d2, c2) in WHERE.items() if (d2, c2) == (d + dd, c + dc)]
            if target:
                self.room = target[0]
                self.x10 -= dc * W * 10
                self.y10 -= dd * FIELD_H * 10
                self.stand -= dd * FIELD_H
                self.entry = (self.x10, self.y10, self.mode)

    def step(self, key=0):
        k = KEYS[key]
        self.run = -1 if k == 'Left' else 1 if k == 'Right' else 0 if k == 'Release' else self.run
        self.vert = -1 if k == 'Up' else 1 if k == 'Down' else 0 if k == 'ReleaseV' else self.vert
        self.tick += 1
        if self.move(k == 'Jump'):
            self.x10, self.y10, self.mode = self.entry
            self.vy, self.stand, self.lives = 0, fdiv(self.y10, 10), self.lives - 1
        self.change()
        y = fdiv(self.y10, 10)
        self.min_y = min(self.min_y, y)
        self.air += self.mode == 2

    def play(self, script, ticks):
        keys = dict(script)
        for i in range(ticks):
            self.step(keys.get(i, 0))
        return dict(X=fdiv(self.x10, 10), Y=fdiv(self.y10, 10), Mode=self.mode, Room=ORDER.index(self.room), Lives=self.lives,
                    MinY=self.min_y, Air=self.air)


K = IN
# Szenarien im Startraum 005 (Start: Spalte 8, oberste Etage): (Name, Tastenfolge [(Tick, Taste)], Ticks)
SCENARIOS = [
    ('stehen', [], 30),
    ('Sprung auf der Stelle', [(0, K['Jump'])], 60),
    ('rechts laufen 100 Ticks', [(0, K['Right']), (100, K['Release'])], 120),
    ('Sprung im Lauf', [(0, K['Right']), (20, K['Jump']), (70, K['Release'])], 100),
    ('links zur Stange und hinunter', [(0, K['Left'])], 260),
    ('rechts zur Leiter, hinunter', [(0, K['Right']), (202, K['Release']), (203, K['Down']), (300, K['ReleaseV'])], 320),
    ('Schwundboden ueberqueren', [(0, K['Right']), (202, K['Release']), (203, K['Down']), (280, K['ReleaseV']), (281, K['Left'])], 520),
]

if __name__ == '__main__':
    for name, script, ticks in SCENARIOS:
        s = Sim()
        r = s.play(script, ticks)
        print('%-32s At=%s Key=%s Ticks=%d -> %s' % (name, [t for t, _ in script], [k for _, k in script], ticks, r))
    s = Sim()
    print('Start', fdiv(s.x10, 10), fdiv(s.y10, 10))
