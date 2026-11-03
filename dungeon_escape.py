"""
DUNGEON ESCAPE: I Wanna Be The Escapee
--------------------------------------
Side-view dungeon platformer with gravity. Run with the ARROW KEYS,
jump with SPACE. Find the key, open the door, reach the EXIT. Trust nothing.

  - gravity, variable-height jump and a double jump
  - hidden spikes that are invisible until they kill you
  - fake exits that kill you
  - fake walls you can walk through
  - patrolling monsters
  - instant restart (R) and a mark left where you died

Run:  pip install pygame
      python dungeon_escape.py

Controls
  LEFT / RIGHT (or A / D) : run
  SPACE (or UP / W)       : jump. Tap = short hop, hold = high jump.
                            Press again in mid-air for a double jump.
  R                       : restart the stage (after dying, or any time)
  ENTER                   : next stage (after clearing one)
  ESC                     : quit

Level tiles (text grid, every row must be 20 characters, 13 rows)
  #  wall / floor         .  empty air          P  player start
  E  real exit            X  FAKE exit (kills)  K  key
  D  locked door (touch it with the key)        S  visible spike
  H  HIDDEN spike (kills) F  fake wall (walkable, looks solid)
  G  monster walking left/right (turns at ledges and walls)
  V  flying monster moving up/down
  I  ice floor (歩くと滑る床)
"""
import math
import sys
import os
import pygame

# ----------------------------------------------------------------- settings
os.chdir(os.path.dirname(os.path.abspath(__file__)))
TILE = 40
COLS, ROWS = 20, 13
HUD_H = 60
FOOT_H = 40
SCREEN_W = COLS * TILE
SCREEN_H = ROWS * TILE + HUD_H + FOOT_H
FPS = 60

PLAYER_SIZE = 24
MOVE_SPEED = 190          # px/s
GRAVITY = 1800            # px/s^2
JUMP_SPEED = 650          # px/s  (about 2.9 tiles high)
JUMP_CUT = 0.45           # releasing SPACE early multiplies upward speed by this
MAX_FALL = 900
MAX_AIR_JUMPS = 1         # 1 = double jump, 0 = single jump only
COYOTE = 0.08             # seconds you can still jump after leaving a ledge
JUMP_BUFFER = 0.10        # seconds a jump press is remembered before landing

ENEMY_R = 12
ENEMY_SPEED = 110
ICE_ACCELERATION = 250     # 氷の上での加速度.低いと滑りやすい
ICE_FRICTION = 10           # 摩擦の値。低いと滑りやすい

BG = (10, 10, 18)
SKY_A = (26, 26, 40)
SKY_B = (30, 30, 46)
WALL_C = (70, 70, 110)
WALL_EDGE = (45, 45, 80)
WALL_ICE = (188,226,232)
WHITE = (235, 235, 245)
RED = (225, 50, 50)
GREEN = (90, 220, 130)
GOLD = (245, 200, 60)
BLUE = (80, 150, 255)

# ------------------------------------------------------------------- levels
# Design rule of thumb: a normal jump rises about 2 tiles and crosses about
# 2 tiles of gap, so keep ledges within that unless you want a double jump.
LEVELS = [
    {
        "name": "Stage 1: The Cellar",
        "hint": "Climb up, grab the key, then unlock the door on the right.",
        "grid": [
            "####################",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#P................E#",
            "####################",
            "####################",
        ],
    },
    {
        "name": "Stage 2: Trust Nothing",
        "hint": "That EXIT looks awfully close. Some walls aren't walls.",
        "grid": [
            "####################",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#P................E#",
            "####################",
            "####################",
        ],
    },
    {
        "name": "Stage 3: The Vault",
        "hint": "Climb to the key. The door needs it. Everything else wants you dead.",
        "grid": [
            "####################",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#P................E#",
            "####################",
            "####################",
        ],
    },
    {
        "name": "Stage 4: The Cellar",
        "hint": "Climb up, grab the key, then unlock the door on the right.",
        "grid": [
            "####################",
            "#..................#",
            "#..................#",
            "#....#.............#",
            "#....#.K...........#",
            "#....#.............#",
            "#....#S.G..........#",
            "#....#IIIII........#",
            "#..................#",
            "#................DD#",
            "#P...........H...DE#",
            "####IIIIIIIIII######",
            "####################",
            ],
        },
        {
            "name": "Stage 5: The Cellar",
            "hint": "Climb up, grab the key, then unlock the door on the right.",
            "grid": [
            "####################",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#P................E#",
            "####################",
            "####################",
            ],
            },
        {
            "name": "Stage 6: The Cellar",
            "hint": "Climb up, grab the key, then unlock the door on the right.",
            "grid": [
            "####################",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#..................#",
            "#P................E#",
            "####################",
            "####################",
            ],
            }
]


# -------------------------------------------------------------------- world
def overlap(a, b):
    """a, b are (left, top, right, bottom)."""
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def tile_box(tx, ty):
    return (tx * TILE, ty * TILE, (tx + 1) * TILE, (ty + 1) * TILE)


def spike_box(tx, ty):
    """Spikes only hurt in the lower half of their tile."""
    return (tx * TILE + 8, ty * TILE + TILE / 2,
            (tx + 1) * TILE - 8, (ty + 1) * TILE)


class Enemy:
    def __init__(self, x, y, dx, dy, walker):
        self.x, self.y, self.dx, self.dy, self.walker = x, y, dx, dy, walker

    def update(self, dt, world):
        nx = self.x + self.dx * ENEMY_SPEED * dt
        ny = self.y + self.dy * ENEMY_SPEED * dt
        lead_x = nx + self.dx * ENEMY_R
        lead_y = ny + self.dy * ENEMY_R
        turn = world.solid_px(lead_x, lead_y)
        if self.walker and not turn:
            # turn around at ledges: no floor just below the leading edge
            turn = not world.solid_px(lead_x, self.y + ENEMY_R + 2)
        if turn:
            self.dx, self.dy = -self.dx, -self.dy
        else:
            self.x, self.y = nx, ny

    def hits(self, box):
        cx = min(max(self.x, box[0]), box[2])
        cy = min(max(self.y, box[1]), box[3])
        return math.hypot(self.x - cx, self.y - cy) < ENEMY_R - 2


class World:
    """One stage: tiles, player physics, monsters and all the rules."""

    def __init__(self, grid):
        self.walls, self.fake_walls, self.Ice_walls, self.doors = set(), set(), set(), set()
        self.keys, self.spikes, self.hidden = set(), set(), set()
        self.fake_exits = set()
        self.exit = None
        self.enemies = []
        self.px = self.py = TILE * 1.5
        for y, row in enumerate(grid):
            for x, ch in enumerate(row):
                p = (x, y)
                cx, cy = x * TILE + TILE / 2, y * TILE + TILE / 2
                if ch == "#":
                    self.walls.add(p)
                elif ch == "F":
                    self.fake_walls.add(p)
                elif ch == "I":
                    self.Ice_walls.add(p)
                elif ch == "D":
                    self.doors.add(p)
                elif ch == "K":
                    self.keys.add(p)
                elif ch == "S":
                    self.spikes.add(p)
                elif ch == "H":
                    self.hidden.add(p)
                elif ch == "E":
                    self.exit = p
                elif ch == "X":
                    self.fake_exits.add(p)
                elif ch == "G":      # sits on the floor
                    self.enemies.append(
                        Enemy(cx, (y + 1) * TILE - ENEMY_R, 1, 0, True))
                elif ch == "V":
                    self.enemies.append(Enemy(cx, cy, 0, 1, False))
                elif ch == "P":
                    self.px = cx
                    self.py = (y + 1) * TILE - PLAYER_SIZE / 2
        # physics state
        self.vy = 0.0
        self.vx = 0.0
        self.on_ground = False
        self.air_jumps = MAX_AIR_JUMPS
        self.coyote = 0.0
        self.jump_buffer = 0.0
        self.jump_held = False
        self.facing = 1
        # game state
        self.has_key = False
        self.dead = None
        self.cleared = False
        self.message = ""

    # ---- queries ---------------------------------------------------------
    def solid(self, tx, ty):
        if not (0 <= tx < COLS and 0 <= ty < ROWS):
            return True
        return (tx, ty) in self.walls or (tx, ty) in self.doors or (tx, ty) in self.Ice_walls

    def solid_px(self, x, y):
        return self.solid(math.floor(x / TILE), math.floor(y / TILE))

    def player_box(self):
        h = PLAYER_SIZE / 2
        return (self.px - h, self.py - h, self.px + h, self.py + h)

    def on_ice(self):
        """プレイヤーのX軸が氷床と重なっている間は氷床として扱う。"""
        left_tx = math.floor((self.px - PLAYER_SIZE / 4) / TILE)
        right_tx = math.floor((self.px + PLAYER_SIZE / 4) / TILE)
        return any(
            (tx, ty) in self.Ice_walls
            for tx in (left_tx, right_tx)
            for ty in range(ROWS)
        )

    # ---- input -----------------------------------------------------------
    def jump_pressed(self):
        self.jump_held = True
        self.jump_buffer = JUMP_BUFFER

    def jump_released(self):
        self.jump_held = False
        if self.vy < 0:                      # let go early = shorter jump
            self.vy *= JUMP_CUT

    def _do_jump(self):
        self.vy = -JUMP_SPEED
        self.on_ground = False
        self.coyote = 0.0
        self.jump_buffer = 0.0
        if not self.jump_held:               # tapped and released already
            self.vy *= JUMP_CUT

    # ---- movement --------------------------------------------------------
    def _move_axis(self, dx, dy):
        """Move along one axis and push out of solid tiles. True if blocked."""
        h = PLAYER_SIZE / 2
        hit = False
        self.px += dx
        self.py += dy
        l, t, r, b = self.player_box()
        for ty in range(math.floor(t / TILE), math.floor((b - 0.001) / TILE) + 1):
            for tx in range(math.floor(l / TILE), math.floor((r - 0.001) / TILE) + 1):
                if self.solid(tx, ty):
                    hit = True
                    if dx > 0:
                        self.px = tx * TILE - h
                    elif dx < 0:
                        self.px = (tx + 1) * TILE + h
                    if dy > 0:
                        self.py = ty * TILE - h
                    elif dy < 0:
                        self.py = (ty + 1) * TILE + h
                    l, t, r, b = self.player_box()
        return hit

    def die(self, reason):
        if not self.dead:
            self.dead = reason

    def _open_door(self, start):
        """Unlock a door and every door tile connected to it."""
        stack = [start]
        while stack:
            t = stack.pop()
            if t in self.doors:
                self.doors.discard(t)
                x, y = t
                stack += [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

    def update(self, dt, dirx):
        if self.dead or self.cleared:
            return

        # ---- jumping (coyote time, jump buffer, double jump)
        self.coyote = max(0.0, self.coyote - dt)
        self.jump_buffer = max(0.0, self.jump_buffer - dt)
        if self.on_ground:
            self.coyote = COYOTE
            self.air_jumps = MAX_AIR_JUMPS
        if self.jump_buffer > 0:
            if self.on_ground or self.coyote > 0:
                self._do_jump()
            elif self.air_jumps > 0:
                self.air_jumps -= 1
                self._do_jump()

        # ---- 滑る床
        target_vx = dirx * MOVE_SPEED
        if self.on_ice():
            if dirx:
                # ゆっくりと加速
                if self.vx < target_vx:
                    self.vx = min(target_vx, self.vx + ICE_ACCELERATION * dt)
                elif self.vx > target_vx:
                    self.vx = max(target_vx, self.vx - ICE_ACCELERATION * dt)
            else:
                # 滑り続ける
                if self.vx > 0:
                    self.vx = max(0.0, self.vx - ICE_FRICTION * dt)
                elif self.vx < 0:
                    self.vx = min(0.0, self.vx + ICE_FRICTION * dt)
        else:
            if dirx:
                self.vx = target_vx
            else:
                self.vx = 0.0
        if dirx:
            self.facing = dirx
        if abs(self.vx) > 0:
            hit = self._move_axis(self.vx * dt, 0)
            if hit:
                self.vx = 0.0
        self.vy = min(self.vy + GRAVITY * dt, MAX_FALL)
        dy = self.vy * dt
        self.on_ground = False
        if self._move_axis(0, dy):
            if dy > 0:
                self.on_ground = True
            self.vy = 0.0

        box = self.player_box()

        for e in self.enemies:
            e.update(dt, self)
            if e.hits(box):
                self.die("A monster got you.")

        # ---- doors: touch with the key to unlock
        pad = (box[0] - 4, box[1] - 4, box[2] + 4, box[3] + 4)
        for d in list(self.doors):
            if d in self.doors and overlap(pad, tile_box(*d)):
                if self.has_key:
                    self._open_door(d)
                    self.has_key = False
                    self.message = "Door unlocked!"
                else:
                    self.message = "The door is locked. Find a key."

        tile = (math.floor(self.px / TILE), math.floor(self.py / TILE))
        if tile in self.keys:
            self.keys.discard(tile)
            self.has_key = True
            self.message = "You got the key!"

        for p in self.spikes | self.hidden:
            if overlap(box, spike_box(*p)):
                self.die("Spikes!" if p in self.spikes else
                         "Hidden spikes! Nobody warned you.")
        if tile in self.fake_exits:
            self.die("That exit was fake!")
        if tile == self.exit:
            self.cleared = True


# --------------------------------------------------------------------- game
class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        pygame.display.set_caption("DUNGEON ESCAPE: I Wanna Be The Escapee")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("consolas", 18)
        self.small = pygame.font.SysFont("consolas", 15)
        self.title = pygame.font.SysFont("consolas", 24, bold=True)
        self.big = pygame.font.SysFont("consolas", 64, bold=True)
        self.deaths = 0
        self.total_time = 0.0
        self.shake = 0
        self.markers = [[] for _ in LEVELS]    # where you died, per stage
        self.level_idx = 0
        self.load(0)

    def load(self, idx):
        self.level_idx = idx
        self.level = LEVELS[idx]
        self.restart()

    def restart(self):
        self.world = World(self.level["grid"])
        self.world.message = self.level["hint"]
        self.death_counted = False

    # ---- drawing ---------------------------------------------------------
    def draw_tiles(self, ox, oy):
        w = self.world
        revealed = bool(w.dead)
        for y in range(ROWS):
            for x in range(COLS):
                p = (x, y)
                rect = pygame.Rect(ox + x * TILE, oy + y * TILE, TILE, TILE)
                if p in w.walls or p in w.fake_walls or p in w.Ice_walls:
                    pygame.draw.rect(self.screen, WALL_C, rect)
                    pygame.draw.rect(self.screen, WALL_EDGE, rect, 2)
                    if revealed and p in w.fake_walls:
                        pygame.draw.rect(self.screen, GREEN, rect, 2)
                    if p in w.Ice_walls:
                        pygame.draw.rect(self.screen, WALL_ICE, rect)
                    continue
                

                pygame.draw.rect(self.screen,SKY_A if (x + y) % 2 else SKY_B, rect)
                c = rect.center
                if p in w.doors:
                    pygame.draw.rect(self.screen, (140, 90, 40), rect.inflate(-4, 0))
                    pygame.draw.circle(self.screen, GOLD, c, 6)
                elif p in w.keys:
                    pygame.draw.circle(self.screen, GOLD, (c[0] - 6, c[1]), 7, 3)
                    pygame.draw.line(self.screen, GOLD, c, (c[0] + 12, c[1]), 3)
                    pygame.draw.line(self.screen, GOLD, (c[0] + 9, c[1]),
                                     (c[0] + 9, c[1] + 6), 3)
                elif p == w.exit or p in w.fake_exits:
                    pygame.draw.rect(self.screen, (30, 120, 70),
                                     rect.inflate(-6, -2), border_radius=6)
                    t = self.small.render("EXIT", True, WHITE)
                    self.screen.blit(t, t.get_rect(center=c))
                elif p in w.spikes or (revealed and p in w.hidden):
                    for i in range(3):
                        bx = rect.left + 4 + i * 11
                        pygame.draw.polygon(self.screen, (200, 200, 210), [
                            (bx, rect.bottom - 1), (bx + 6, rect.centery),
                            (bx + 12, rect.bottom - 1)])

    def draw_world(self):
        ox = int((self.shake % 4 - 2) * 2) if self.shake else 0
        oy = HUD_H
        self.draw_tiles(ox, oy)
        for mx, my in self.markers[self.level_idx]:
            t = self.font.render("x", True, (170, 50, 50))
            self.screen.blit(t, t.get_rect(center=(ox + mx, oy + my)))
        for e in self.world.enemies:
            c = (int(ox + e.x), int(oy + e.y))
            pygame.draw.circle(self.screen, RED, c, ENEMY_R)
            for s in (-4, 4):
                pygame.draw.circle(self.screen, WHITE, (c[0] + s, c[1] - 2), 3)
        l, t, r, b = self.world.player_box()
        body = pygame.Rect(int(ox + l), int(oy + t), PLAYER_SIZE, PLAYER_SIZE)
        pygame.draw.rect(self.screen, BLUE, body, border_radius=5)
        eye = 14 if self.world.facing > 0 else 4
        for s in (eye, eye + 6):
            pygame.draw.circle(self.screen, WHITE, (body.x + s, body.y + 9), 3)
        if self.world.has_key:
            pygame.draw.circle(self.screen, GOLD, (body.right, body.top), 5)

    def draw_hud(self):
        self.screen.blit(self.title.render(self.level["name"], True, GOLD), (12, 8))
        info = (f"Deaths: {self.deaths}   Time: {int(self.total_time)}s   "
                f"Key: {'YES' if self.world.has_key else 'no'}")
        self.screen.blit(self.font.render(info, True, WHITE), (12, 36))
        y = HUD_H + ROWS * TILE + 6
        msg = self.world.dead or self.world.message
        col = RED if self.world.dead else GREEN
        self.screen.blit(self.font.render(msg, True, col), (12, y))
        keys = "ARROWS move | SPACE jump (hold = higher, again in air = double) | R restart"
        self.screen.blit(self.small.render(keys, True, (140, 140, 170)), (12, y + 20))

    def draw_overlay(self, text, color, sub):
        shade = pygame.Surface((SCREEN_W, ROWS * TILE), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 150))
        self.screen.blit(shade, (0, HUD_H))
        cy = HUD_H + ROWS * TILE // 2
        img = self.big.render(text, True, color)
        self.screen.blit(img, img.get_rect(center=(SCREEN_W // 2, cy - 20)))
        s = self.font.render(sub, True, WHITE)
        self.screen.blit(s, s.get_rect(center=(SCREEN_W // 2, cy + 30)))

    def draw(self):
        self.screen.fill(BG)
        self.draw_world()
        self.draw_hud()
        w = self.world
        if w.dead:
            self.draw_overlay("YOU DIED", RED, "Press R to try again")
        elif w.cleared:
            if self.level_idx + 1 < len(LEVELS):
                self.draw_overlay("STAGE CLEAR!", GREEN, "Press ENTER for the next stage")
            else:
                self.draw_overlay("YOU ESCAPED!", GREEN,
                                  f"{self.deaths} deaths, {int(self.total_time)}s. "
                                  "ENTER to play again")
        pygame.display.flip()

    # ---- loop ------------------------------------------------------------
    JUMP_KEYS = (pygame.K_SPACE, pygame.K_UP, pygame.K_w)

    def handle_keydown(self, key):
        if key == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()
        elif key == pygame.K_r:
            self.restart()
        elif key in self.JUMP_KEYS:
            self.world.jump_pressed()
        elif key == pygame.K_RETURN and self.world.cleared:
            if self.level_idx + 1 < len(LEVELS):
                self.load(self.level_idx + 1)
            else:
                self.deaths, self.total_time = 0, 0.0
                self.markers = [[] for _ in LEVELS]
                self.load(0)

    def run(self):
        while True:
            dt = min(self.clock.tick(FPS) / 1000.0, 1 / 30)
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif e.type == pygame.KEYDOWN:
                    self.handle_keydown(e.key)
                elif e.type == pygame.KEYUP and e.key in self.JUMP_KEYS:
                    self.world.jump_released()

            k = pygame.key.get_pressed()
            dirx = (k[pygame.K_RIGHT] or k[pygame.K_d]) - (k[pygame.K_LEFT] or k[pygame.K_a])

            if not self.world.dead and not self.world.cleared:
                self.total_time += dt
            self.world.update(dt, dirx)

            if self.world.dead and not self.death_counted:
                self.death_counted = True
                self.deaths += 1
                self.shake = 15
                self.markers[self.level_idx].append(
                    (int(self.world.px), int(self.world.py)))
            if self.shake:
                self.shake -= 1
            self.draw()


if __name__ == "__main__":
    Game().run()
