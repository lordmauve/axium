from typing import Type, TypeVar
from itertools import product

import numpy as np
import wasabi2d as w2d
from wasabigeom import vec2
import random

import sfx
from helpers import random_vec2, showing
from collisions import colgroup
from controllers import joy_press


scene: w2d.Scene = None


@colgroup.handler('ship', 'star_bit')
def handle_collect(ship, star_bit):
    star_bit.collected = ship
    colgroup.untrack(star_bit)


async def star_bit(pos):
    scale = random.uniform(0.06, 0.08)
    star = scene.layers[1].add_sprite('star_07', pos=pos, scale=scale)
    star.radius = 60
    star.collected = False

    async def flash():
        while star.is_alive():
            await w2d.animate(star, color=(0.3, 0.3, 1.0, 1.0))
            await w2d.animate(star, color=(1.0, 1.0, 1.0, 1.0))

    async def move():
        vel = random_vec2(50)
        async for dt in w2d.clock.coro.frames_dt():
            if star.collected:
                break
            vel *= 0.5 ** dt
            star.pos += vel * dt

        collector = star.collected
        async for dt in w2d.clock.coro.frames_dt():
            sep = star.pos - collector.pos

            closer = sep.length() * 0.001 ** dt
            if closer < 16:
                sfx.pickup()
                ns.cancel()
            sep = sep.scaled_to(closer)
            star.pos = collector.pos + sep

    with showing(star):
        with colgroup.tracking(star, "star_bit"):
            async with w2d.Nursery() as ns:
                ns.do(flash())
                ns.do(move())


def manhattan_distance(a: tuple[int, int], b: tuple[int, int]):
    ax, ay = a
    bx, by = b
    return abs(ax - bx) + abs(ay - by)


T = TypeVar('T')


class Base:
    def __init__(self):
        self._tiles = None
        self.grid = set()
        self.objects = []
        self.connectors = set()
        self.wiring = set()

    @property
    def tiles(self):
        if self._tiles is None:
            self._tiles = scene.layers[-1].add_tile_map()
        return self._tiles

    def world_to_cell(self, pos) -> tuple[int, int]:
        x, y = pos
        return round(x / 48), round(y / 48)

    def can_place(self, pos) -> tuple[vec2, bool]:
        cx, cy = self.world_to_cell(pos)
        coord = vec2(cx * 48 + 24, cy * 48 + 24)
        for cell in self.cells_for((cx, cy)):
            if cell in self.grid:
                return coord, False
        return coord, True

    def cells_for(self, cell: tuple[int, int]):
        cx, cy = cell
        return product([cx - 1, cx, cx + 1], [cy - 1, cy, cy + 1])

    def connectors_for(self, cell: tuple[int, int]) -> set[tuple[int, int]]:
        cx, cy = cell
        return {
            (cx - 2, cy),
            (cx + 2, cy),
            (cx, cy - 2),
            (cx, cy + 2),
        }

    def internal_connectors(self, cell: tuple[int, int]) -> set[tuple[int, int]]:
        cx, cy = cell
        return {
            (cx - 1, cy),
            (cx + 1, cy),
            (cx, cy - 1),
            (cx, cy + 1),
        }

    def lay_connector(self, start_points):
        if any(p in self.grid for p in start_points):
            return

        if not self.connectors:
            return

        # Find closest connector by manhattan distance
        (startx, starty), (connectx, connecty) = min(
            product(start_points, self.connectors),
            key=lambda pair: manhattan_distance(*pair)
        )

        # Build the path we'd like the connector to follow
        path = set()
        ystep = -1 if starty > connecty else 1
        for y in range(starty, connecty + ystep, ystep):
            c = startx, y
            path.add(c)
            if c in self.wiring:
                break
        else:
            corner = startx, y
            xstep = -1 if startx > connectx else 1
            for x in range(startx, connectx + xstep, xstep):
                c = x, y
                if c == corner:
                    continue
                path.add(c)
                if c in self.wiring:
                    break

        # Insert the whole path
        self.wiring.update(path)

        # Update the tile map
        tiles = self.tiles
        for x, y in path:
            adj = (
                (x - 1, y) in self.wiring,
                (x + 1, y) in self.wiring,
                (x, y - 1) in self.wiring,
                (x, y + 1) in self.wiring,
            )
            tiles[x, y] = self.ADJ_MAP.get(adj, 'connector_lr')

    ADJ_MAP = {
        # l, r, u, d
        (1, 1, 0, 0): 'connector_lr',
        (0, 0, 1, 1): 'connector_ud',
        (1, 0, 1, 0): 'corner_lu',
        (1, 0, 0, 1): 'corner_ld',
        (0, 1, 1, 0): 'corner_ru',
        (0, 1, 0, 1): 'corner_rd',
        (1, 1, 1, 0): 'tee_lru',
        (1, 1, 0, 1): 'tee_lrd',
        (0, 1, 1, 1): 'tee_rud',
        (1, 0, 1, 1): 'tee_lud',
        (1, 1, 1, 1): 'connector_lrud',
    }

    def place(self, type: Type[T], pos: vec2) -> T:
        world_pos, can_place = self.can_place(pos)
        if not can_place:
            raise ValueError("Cannot place here")
        cell = self.world_to_cell(pos)

        for pos in self.cells_for(cell):
            del self.tiles[pos]
        self.grid.update(self.cells_for(cell))
        self.wiring.update(self.internal_connectors(cell))
        obj = type(world_pos)
        self.objects.append(obj)

        connectors = self.connectors_for(cell)
        self.lay_connector(connectors)
        self.connectors.update(connectors)
        self.connectors.difference_update(self.grid)
        return obj


base = Base()


class Reactor:
    radius = 60

    def __init__(self, pos=vec2(0, 0)):
        self.sprite = w2d.Group(
            [
                scene.layers[-1].add_sprite('component_base'),
                scene.layers[1].add_sprite('reactor'),
            ],
            pos=pos
        )
        self.pos = pos


def roundto(n, to):
    return (n + to / 2) // to * to


async def building_mode(ship):
    """Display a reticle where to build the next base object."""
    def insertion_point():
        return ship.pos + vec2(100, 0).rotated(ship.angle)

    RED = (1.0, 0, 0, 0.4)
    GREEN = (0, 1.0, 0, 0.4)

    obj = scene.layers[-1].add_sprite('component_base')

    def update():
        pos, can_place = base.can_place(insertion_point())
        obj.pos = pos
        obj.color = GREEN if can_place else RED

    update()

    async def process_input():
        while True:
            ev = await joy_press()
            if ev.button == 3:
                ns.cancel()
            elif ev.button == 0:
                point = insertion_point()
                pos, can_place = base.can_place(point)
                if can_place:
                    base.place(Reactor, point)
                    ns.cancel()

    async def update_reticle():
        while True:
            update()
            await w2d.clock.coro.sleep(0.1)

    with showing(obj):
        async with w2d.Nursery() as ns:
            ns.do(update_reticle())
            ns.do(process_input())
