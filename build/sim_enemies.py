# Gold Hunter - Python-Nachbau von Enemies_Init, Enemies_Step und Hit_Check (gleiche Regeln, gleiche Zahlen, gleiche Zufallszahlen).
# EnemySim = sim_player.Sim + Gegner: nach Tueren/Gegenstaenden laufen die Gegner, dann Hit_Check, dann der Raumwechsel (wie Game_Play).
from gh_lib import *
import sim_player as sp

T_ = TILE_CODE
LCG_A, LCG_C = 1103515245, 12345


def enemies_init(grid):
    out = []
    for r, row in enumerate(grid):
        for c, code in enumerate(row):
            if ENEMY_CODES[0] <= code <= ENEMY_CODES[1]:
                out.append([code - ENEMY_CODES[0], c * TILE * 10, r * TILE * 10, ((c + r) % 2) * 2 - 1, 0])
    return out


class EnemySim(sp.Sim):
    def __init__(self, level=1, seed=DEMO_SEED):
        super().__init__(level)
        self.seed = seed
        self.enemies = enemies_init(self.grid[self.room])
        self.hit = False

    def etile(self, x, y):
        return self.tile(x, y)

    def enemies_step(self):
        li = min(max(self.level - 1, 0), 2)
        speeds = [LV_SPIDER[li], 0, LV_SKULL[li]]
        sol = lambda v: v in SOLID
        pla = lambda v: v in PLATFORM
        lad = lambda v: v in CLIMBABLE
        tile = self.tile
        new = []
        for kind, x10, y10, dir_, mode in self.enemies:
            self.seed = (self.seed * LCG_A + LCG_C) & 0xFFFFFFFF
            rnd = (self.seed // 65536) % 32768
            spd = speeds[kind]
            spider = kind == 0
            x, y = x10 // 10, y10 // 10
            if kind == 1:
                new.append([kind, x10, y10, dir_, 0])
                continue
            if mode == 1:
                ny10 = y10 + dir_ * spd
                ny = ny10 // 10
                cxm = x + 16
                rdir = (rnd % 2) * 2 - 1
                down_floor = dir_ > 0 and (sol(tile(cxm, ny + 32)) or ny + 32 >= FIELD_H)
                floor_y = ((ny + 32) // TILE) * TILE - 32
                down_end = dir_ > 0 and not down_floor and not lad(tile(cxm, ny + 31)) and not lad(tile(cxm, ny + 33))
                up_top = dir_ < 0 and not lad(tile(cxm, ny + 31))
                top_y = ((ny + 31) // TILE + 1) * TILE - 32
                up_wall = dir_ < 0 and ny <= 0
                c_mode = 0 if (down_floor or up_top) else 1
                c_y10 = floor_y * 10 if down_floor else top_y * 10 if up_top else y10 if (down_end or up_wall) else ny10
                c_dir = rdir if (down_floor or up_top) else -dir_ if (down_end or up_wall) else dir_
                new.append([kind, x10, c_y10, c_dir, c_mode])
                continue
            nx10 = x10 + dir_ * spd
            nx = nx10 // 10
            front = nx + 31 if dir_ > 0 else nx
            ahead = tile(front, y + 32)
            hatch_ahead = ahead == T_['~']
            on_hatch = tile(x + 16, y + 32) == T_['~']
            sup = (sol(ahead) or pla(ahead) or lad(ahead)) if spider else (sol(ahead) or pla(ahead))
            support = sup and (not hatch_ahead or on_hatch)
            blocked = sol(tile(front, y + 16)) or nx < 0 or nx > W - 32 or not support
            w_x10 = x10 if blocked else nx10
            w_dir = -dir_ if blocked else dir_
            passing = spider and not blocked and (nx10 % (TILE * 10)) < spd
            colx = (nx // TILE) * TILE + 16
            can_up = lad(tile(colx, y + 16))
            can_down = lad(tile(colx, y + 33)) and y + 33 < FIELD_H - TILE
            pick = rnd % 4
            go_up = passing and can_up and pick == 0
            go_down = passing and can_down and not go_up and pick == 1
            climb = go_up or go_down
            new.append([kind, (colx - 16) * 10 if climb else w_x10, y10, -1 if go_up else 1 if go_down else w_dir, 1 if climb else 0])
        self.enemies = new

    def hit_check(self):
        x, y = self.x10 // 10, self.y10 // 10
        cl, cr, ct, cb = x + CBOX[0], x + CBOX[1], y + CBOX[2], y + CBOX[3]
        for kind, ex10, ey10, _, _ in self.enemies:
            ex, ey = ex10 // 10, ey10 // 10
            b = EBOX[kind]
            if cl < ex + b[1] and ex + b[0] < cr and ct < ey + b[3] and ey + b[2] < cb:
                return True
        return False

    def change(self):
        self.enemies_step()
        self.hit = self.hit_check()
        room = self.room
        super().change()
        if self.room != room:
            self.enemies = enemies_init(self.grid[self.room])


if __name__ == '__main__':
    from demo_events import DEMO_EVENTS, DEMO_LEN, DEMO_TREASURE_TICK
    s = EnemySim()
    ev = dict(DEMO_EVENTS)
    hits = []
    for t in range(DEMO_LEN):
        s.step(IN[ev.get(t, 'None')])
        if s.hit and (not hits or hits[-1][1] != t - 1):
            hits.append([t, t, s.room, s.mode])
        elif s.hit:
            hits[-1][1] = t
    print('Treffer-Strecken (von, bis, Raum, Modus):', len(hits))
    for h in hits:
        print('  ', h)
