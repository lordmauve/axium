from typing import Type, TypeVar, NamedTuple
from itertools import product, count
from enum import Enum
import math
from collections import Counter, deque

import numpy as np
import wasabi2d as w2d
from wasabigeom import vec2
import random

import sfx
from helpers import random_vec2, showing, random_ring, angle_to_pos
from collisions import colgroup
import clocks
from clocks import coro, animate
import effects

scene: w2d.Scene = None
diffuse = -2
emissive = -1

LIGHTBLUE = (0.6, 0.6, 1.0, 1.0)
WHITE = (1.0, 1.0, 1.0, 1.0)


@colgroup.handler('ship', 'star_bit')
def handle_collect(ship, star_bit):
    star_bit.collected = ship
    ship.balance.value += random.randint(18, 25) * 10
    colgroup.untrack(star_bit)


async def star_bit(pos):
    scale = random.uniform(0.06, 0.08)
    star = scene.layers[1].add_sprite('star_07', pos=pos, scale=scale)
    star.radius = 60
    star.collected = False

    async def flash():
        for _ in range(2):
            await animate(star, color=LIGHTBLUE)
            await animate(star, color=WHITE)

        with coro.move_on_after(3):
            while True:
                star.color = (0, 0, 0, 0)
                await coro.sleep(0.2)
                star.color = (0.6, 0.6, 1.0, 1.0)
                await coro.sleep(0.3)
        ns.cancel()

    async def move():
        vel = random_vec2(50)
        async for dt in coro.frames_dt():
            if star.collected:
                break
            vel *= 0.5 ** dt
            star.pos += vel * dt

        collector = star.collected
        async for dt in coro.frames_dt():
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


class Edge(Enum):
    """Identify an edge of a grid square."""

    RIGHT = 0
    BOTTOM = 1


class Connection(NamedTuple):
    x: int
    y: int
    edge: Edge

    @property
    def cell(self):
        return self.x, self.y


@colgroup.handler('threx_bullet', 'building')
def handle_collect(bullet, building):
    bullet.delete()
    effects.pixels.emit(
        random.randint(3, 6),
        pos=bullet.pos,
        vel=bullet.vel * 0.1,
        size=2,
        spin=3,
        vel_spread=30,
        color=(0.3, 0.3, 0.3, 1.0)
    )
    effects.pop(bullet.pos, bullet.vel * 0.2, color=LIGHTBLUE)
    sfx.impact()
    building.hit(bullet.damage)


class Base:
    def __init__(self):
        self._tiles = self._sparks = None
        self.grid = set()
        self.objects = []
        self.connectors: Counter[tuple[int, int]] = Counter()
        self.wiring: tuple[int, int, Edge] = set()
        self.power = 0

    def clear(self):
        for o in self.objects[:]:
            o.delete()
        self.grid.clear()
        self.objects.clear()
        self.connectors.clear()
        self.wiring.clear()
        if self._tiles:
            self._tiles.clear()

    @property
    def tiles(self):
        if self._tiles is None:
            self._tiles = scene.layers[diffuse].add_tile_map()
        return self._tiles

    @property
    def sparks(self):
        if self._sparks:
            return self._sparks
        sparks =  self._sparks = scene.layers[1].add_particle_group(
            max_age=1,
            drag=0.01,
            grow=0.1,
            texture='twirl_02'
        )
        sparks.add_color_stop(0, LIGHTBLUE)
        sparks.add_color_stop(1.0, (1.0, 1.0, 1.0, 0))
        return sparks

    def world_to_cell(self, pos) -> tuple[int, int]:
        x, y = pos
        return round(x / 48), round(y / 48)

    def cell_to_world(self, cell: tuple[int, int]) -> vec2:
       return vec2(cell) * 48 + vec2(24, 24)

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

    def wiring_for(self, cell: tuple[int, int]) -> set[Connection]:
        cx, cy = cell
        return {
            Connection(cx - 2, cy, Edge.RIGHT),
            Connection(cx + 1, cy, Edge.RIGHT),
            Connection(cx, cy - 2, Edge.BOTTOM),
            Connection(cx, cy + 1, Edge.BOTTOM),
        }

    def connectors_for(self, cell: tuple[int, int]) -> set[tuple[int, int]]:
        cx, cy = cell
        return {
            (cx - 2, cy),
            (cx + 2, cy),
            (cx, cy - 2),
            (cx, cy + 2),
        }

    async def lay_connector(
            self,
            start_points: set[tuple[int, int]],
        ):
        if any(p in self.grid for p in start_points):
            return

        if not self.connectors:
            self.connectors.update(start_points)
            return

        # Find closest connector by manhattan distance
        (startx, starty), (connectx, connecty) = min(
            product(start_points, self.connectors),
            key=lambda pair: manhattan_distance(*pair)
        )

        self.connectors.update(start_points)

        sleep = coro.sleep
        interval = 0.03

        # Build the path we'd like the connector to follow
        self.update_tile(startx, starty)
        await sleep(interval)

        def mkrange(a, b):
            if a < b:
                return range(a, b)
            else:
                return range(a - 1, b - 1, -1)

        sounds = (sfx.placement(n).play() for n in count())

        for y in mkrange(starty, connecty):
            c = Connection(startx, y, Edge.BOTTOM)
            self.wiring.add(c)
            self.update_tile(*c.cell)
            self.update_tile(startx, y + 1)
            next(sounds)
            await sleep(interval)
        for x in mkrange(startx, connectx):
            c = Connection(x, connecty, Edge.RIGHT)
            self.wiring.add(c)
            self.update_tile(*c.cell)
            self.update_tile(x + 1, connecty)
            next(sounds)
            await sleep(interval)

        self.update_tile(connectx, connecty)

    def update_tile(self, x, y):
        """Update the tile at the given position."""
        if (x, y) in self.grid:
            return
        adj = (
            Connection(x - 1, y, Edge.RIGHT) in self.wiring,
            Connection(x, y, Edge.RIGHT) in self.wiring,
            Connection(x, y - 1, Edge.BOTTOM) in self.wiring,
            Connection(x, y, Edge.BOTTOM) in self.wiring,
        )
        self.tiles[x, y] = self.ADJ_MAP.get(adj, 'connector_lr')
        self.sparks.emit(
            10,
            size=20,
            pos=self.cell_to_world((x, y)),
            pos_spread=0,
            vel_spread=100,
            age_spread=0.5,
            angle_spread=3,
        )

    def burn(self, center):
        for cell in self.cells_for(center):
            self.tiles[cell] = 'burned'
            self.grid.discard(cell)
        self.connectors -= Counter(self.connectors_for(center))
        self.wiring.difference_update(self.wiring_for(center))

    ADJ_MAP = {
        # l, r, u, d
        (1, 1, 0, 0): 'connector_lr',
        (1, 0, 0, 0): 'connector_lr',
        (0, 1, 0, 0): 'connector_lr',
        (0, 0, 1, 1): 'connector_ud',
        (0, 0, 1, 0): 'connector_ud',
        (0, 0, 0, 1): 'connector_ud',
        (1, 0, 1, 0): 'corner_lu',
        (1, 0, 0, 1): 'corner_ld',
        (0, 1, 1, 0): 'corner_ru',
        (0, 1, 0, 1): 'corner_rd',
        (1, 1, 1, 0): 'tee_lru',
        (1, 1, 0, 1): 'tee_lrd',
        (0, 1, 1, 1): 'tee_rud',
        (1, 0, 1, 1): 'tee_lud',
        (1, 1, 1, 1): 'connector_lrud',
        (0, 0, 0, 0): None,
    }

    async def place(self, type: Type[T], pos: vec2) -> T:
        world_pos, can_place = self.can_place(pos)
        if not can_place:
            raise ValueError("Cannot place here")
        cell = self.world_to_cell(pos)

        for pos in self.cells_for(cell):
            del self.tiles[pos]
        self.grid.update(self.cells_for(cell))
        obj = type(self, world_pos, cell)
        self.objects.append(obj)

        self.wiring.update(self.wiring_for(cell))
        connectors = self.connectors_for(cell)
        async with w2d.Nursery() as ns:
            ns.do(self.lay_connector(connectors))
            ns.do(obj.build(self))
        return obj

    def sufficient_power(self, cls) -> bool:
        """Return True if there is sufficient power to place this object."""
        return (self.power - len(self.objects) + cls.POWER) > 0


base = Base()


class Building:
    health = 50
    radius = 72
    nursery = None
    POWER = 0

    def __init__(self, base, pos, cell):
        self.base = base
        self.pos = pos
        self.cell = cell
        self.nursery = w2d.Nursery()
        self.sprite = self.build_sprite()
        self.sprite.pos = pos

    def delete(self):
        self.base.objects.remove(self)
        self.sprite.delete()
        self.nursery.cancel()
        colgroup.untrack(self)

    def hit(self, damage) -> bool:
        """Take damage.

        Return True if the building was destroyed.
        """
        self.health -= damage
        if self.health > 0:
            return False

        for _ in range(2):
            effects.explode(self.pos + random_vec2(48), vel=vec2(0, 0))
        self.base.burn(self.cell)
        self.delete()
        return True


class Reactor(Building):
    radius = 60
    health = 100

    def __init__(self, base, pos, cell):
        super().__init__(base, pos, cell)

    def build_sprite(self):
        return w2d.Group(
            [
                scene.layers[diffuse].add_sprite('component_base'),
                scene.layers[emissive].add_sprite('reactor'),
            ],
        )

    def delete(self):
        super().delete()
        self.base.power -= self.POWER

    POWER = 4

    async def build(self, base):
        self.base.power += self.POWER
        base, reactor = self.sprite
        for s in self.sprite:
            s.color = (1, 1, 1, 0)
            animate(s, duration=0.3, color=(1, 1, 1, 1))
        reactor.scale = 2.0
        base.scale = 0.5
        animate(base, scale=1.0, tween='decelerate')
        await animate(
            reactor,
            scale=1.0,
            tween='decelerate',
            angle=random.choice((6, -6))
        )
        colgroup.track(self, 'building')


class Rockets(Building):
    """An armory that produces a pack of rockets."""

    def build_sprite(self):
        parts = [
            scene.layers[diffuse].add_sprite('arsenal'),
            scene.layers[diffuse].add_sprite('radar', pos=(-53, -53)),
        ]
        self.blinkenlights = [
            scene.layers[emissive].add_sprite(
                'blinkenlight',
                color='black',
                pos=(-54, 55 - 16 * i)
            )
            for i in range(5)
        ]
        return w2d.Group(
            parts + self.blinkenlights
        )

    async def run_radar(self):
        radar = self.sprite[1]
        while True:
            da = random.uniform(1, -1)
            await animate(
                radar,
                tween='accel_decel',
                angle=radar.angle + da
            )
            await coro.sleep(3)

    async def run_blinkenlights(self):
        ON_COLOR = LIGHTBLUE
        OFF_COLOR = (0, 0, 0, 1.0)
        while True:
            for b in self.blinkenlights:
                for _ in range(5):
                    await animate(b, duration=0.5, color=ON_COLOR)
                    await animate(b, duration=0.5, color=OFF_COLOR)
                await animate(b, duration=0.5, color=ON_COLOR)

            powerup = scene.layers[0].add_sprite('rocket_pack', pos=self.pos)
            powerup.radius = 20
            powerup.event = w2d.Event()
            powerup.weapon = 'rocket'
            powerup.weapon_count = 5
            with colgroup.tracking(powerup, 'powerup'), \
                    showing(powerup):
                await powerup.event
                for b in self.blinkenlights:
                    b.color = OFF_COLOR

    async def build(self, base):
        self.sprite.scale = 0.3
        rot = random.randint(-2, 2) * (math.pi / 2)
        self.sprite.angle = rot
        await animate(self.sprite,
            scale=1,
            duration=0.3,
            tween='decelerate'
        )
        if rot:
            await coro.sleep(0.2)
            await animate(self.sprite,
                scale=0.8,
                duration=0.1,
                tween='decelerate'
            )
            await animate(
                self.sprite,
                angle=0,
                duration=0.2,
                tween='accel_decel'
            )
            await animate(
                self.sprite,
                scale=1,
                duration=0.2,
                tween='decelerate'
            )
        with colgroup.tracking(self, "building"):
            async with self.nursery:
                self.nursery.do(self.run_radar())
                self.nursery.do(self.run_blinkenlights())


class PhaserBay(Building):
    """An armory that produces two packs of phasers."""

    def build_sprite(self):
        parts = [
            scene.layers[diffuse].add_sprite('phaserbay')
        ]

        self.lights_top, self.lights_bottom = [
            [
                scene.layers[emissive].add_sprite(
                    'blinkenlight',
                    color='black',
                    pos=(18, j * (38 - 16 * i))
                )
                for i in range(2)
            ]
            for j in (-1, 1)
        ]
        return w2d.Group(
            parts + self.lights_top + self.lights_bottom,
        )

    async def run_radar(self):
        radar = self.sprite[1]
        while True:
            da = random.uniform(1, -1)
            await animate(
                radar,
                tween='accel_decel',
                angle=radar.angle + da
            )
            await coro.sleep(3)

    async def run_bay(self, lights, spawn_pos):
        ON_COLOR = LIGHTBLUE
        OFF_COLOR = (0, 0, 0, 1.0)
        while True:
            for b in lights:
                for _ in range(5):
                    await animate(b, duration=0.5, color=ON_COLOR)
                    await animate(b, duration=0.5, color=OFF_COLOR)
                await animate(b, duration=0.5, color=ON_COLOR)

            powerup = scene.layers[0].add_sprite(
                'phaser_pack',
                pos=self.pos + spawn_pos
            )
            powerup.radius = 20
            powerup.event = w2d.Event()
            powerup.weapon = 'phaser'
            powerup.weapon_count = 8
            with colgroup.tracking(powerup, 'powerup'), \
                    showing(powerup):
                await powerup.event
                for b in lights:
                    b.color = OFF_COLOR

    async def build(self, base):
        self.sprite.scale = 0.3
        await animate(self.sprite,
            scale=1,
            duration=0.3,
            tween='decelerate'
        )
        with colgroup.tracking(self, "building"):
            async with self.nursery:
                self.nursery.do(self.run_bay(self.lights_top, vec2(-26, -33)))
                await coro.sleep(1.0)
                self.nursery.do(self.run_bay(self.lights_bottom, vec2(-26, 33)))


class RepairBay(Building):

    def build_sprite(self):
        group = w2d.Group([
            scene.layers[diffuse].add_sprite('repairbay'),
            scene.layers[diffuse].add_sprite('iris'),
        ])
        self.iris = group[1]
        self.iris.scale = 0.01
        self.iris_waiting = w2d.Event()
        self.iris_open = w2d.Event()
        self.repairing = set()
        return group

    async def run_drones(self):
        while True:
            most_damaged = None
            most_damaged_frac = 2
            for o in self.base.objects:
                frac = o.health / type(o).health
                if frac >= 1:
                    continue
                if o in self.repairing:
                    continue
                if frac < most_damaged_frac:
                    most_damaged_frac = frac
                    most_damaged = o
            if most_damaged:
                self.nursery.do(self.drone(most_damaged))
            await coro.sleep(1)

    async def drone(self, target):
        self.repairing.add(target)
        DRONE_SPEED = 200
        try:
            await self.open_iris()
            drone = scene.layers[0].add_sprite(
                'repairdrone',
                pos=self.pos,
                color=(0, 0, 0, 1.0),
                scale=0.1
            )
            with showing(drone):
                sep = target.pos - self.pos
                await animate(
                    drone,
                    duration=0.2,
                    scale=1.0,
                    angle=sep.angle(),
                    color=(1, 1, 1, 1.0),
                )

                if sep.is_zero():
                    dest = self.pos + random_ring(100)
                else:
                    dest = target.pos - sep.safe_scaled_to(100)

                async def go_to(dest):
                    sep = dest - drone.pos
                    time = sep.length() / DRONE_SPEED
                    if time < 0.01:
                        return
                    await face(dest)
                    await animate(drone, tween='accel_decel', pos=dest, duration=time)

                async def face(dest):
                    angle = angle_to_pos(dest, drone)
                    if abs(angle) < 0.02:
                        return
                    await animate(drone, duration=0.1, angle=drone.angle + angle)

                async def heal():
                    sep = target.pos - drone.pos
                    effects.pixels.emit(
                        20,
                        pos=drone.pos,
                        vel=sep.safe_scaled_to(60),
                        age_spread=0.1,
                        vel_spread=20,
                        size=2,
                        color=(0, 1, 0, 0.4),
                    )
                    light = effects.mklight(pos=drone.pos, color=(0, 1, 0, 0.4))
                    light.scale = 2
                    target.health = min(target.health + 5, type(target).health)
                    with showing(light):
                        await animate(light, duration=0.4, scale=0.1)

                new_pos = dest
                while target.health < type(target).health:
                    await go_to(new_pos)
                    if target.health < 0:
                        break
                    await face(target.pos)
                    if target.health < 0:
                        break
                    await heal()
                    new_pos = target.pos + random_ring(100)

                await go_to(self.pos)
                await self.open_iris()
                await animate(
                    drone,
                    duration=0.2,
                    scale=0.1,
                    color=(0, 0, 0, 1.0)
                )
        finally:
            self.repairing.discard(target)

    async def open_iris(self):
        if self.iris_open.is_set():
            return
        self.iris_waiting.set()
        await self.iris_open

    async def iris_control(self):
        while True:
            await self.iris_waiting
            await animate(self.iris, duration=0.1, tween='decelerate', scale=1.0)
            self.iris_open.set()
            await coro.sleep(1.0)
            self.iris_open = w2d.Event()
            self.iris_waiting = w2d.Event()
            await animate(self.iris, duration=0.1, tween='decelerate', scale=0.01)

    async def build(self, base):
        self.sprite.scale = 0.3
        await animate(self.sprite,
            scale=1,
            duration=0.3,
            tween='decelerate'
        )
        with colgroup.tracking(self, "building"):
            async with self.nursery:
                self.nursery.do(self.run_drones())
                self.nursery.do(self.iris_control())




@colgroup.handler('ship', 'powerup')
def handle_collect(ship, powerup):
    powerup.event.set()
    if ship.weapon != powerup.weapon:
        ship.weapon = powerup.weapon
        ship.weapon_count = powerup.weapon_count
    else:
        ship.weapon_count += powerup.weapon_count
    sfx.powerup.play()


def roundto(n, to):
    return (n + to / 2) // to * to


async def building_mode(ship, player, construction_ns):
    """Display a reticle where to build the next base object."""
    def insertion_point():
        return ship.pos + vec2(100, 0).rotated(ship.angle)

    items = deque([
        ('blueprint_phaser', PhaserBay, 3000),
        ('blueprint_rocket', Rockets, 5000),
        ('blueprint_repair', RepairBay, 8000),
        ('blueprint_reactor', Reactor, 2000),
    ])
    blueprint, cls, cost = items[0]
    if not base.sufficient_power(cls):
        items.appendleft(items.pop())  # Cycle to the reactor
        blueprint, cls, cost = items[0]

    can_place = False
    obj = scene.layers[-1].add_sprite(blueprint)

    def update():
        pos, can_place = base.can_place(insertion_point())
        if cost > player.balance.value:
            can_place = False
        elif not base.sufficient_power(cls):
            can_place = False
        obj.pos = pos
        obj.color = 'white' if can_place else 'red'

    update()

    async def process_input():
        nonlocal blueprint, cls, cost
        while True:
            button = await player.controller.button_press(
                'a', 'y', 'leftshoulder', 'rightshoulder'
            )
            if button == 'y':
                ns.cancel()
            elif button == 'a':
                point = insertion_point()
                pos, can_place = base.can_place(point)
                if cost > player.balance.value:
                    # Speak
                    w2d.sounds.insufficient_funds.play()
                    ns.cancel()
                    continue
                if not base.sufficient_power(cls):
                    # Speak
                    w2d.sounds.insufficient_power.play()
                    ns.cancel()
                    continue
                if can_place:
                    player.balance.value -= cost
                    construction_ns.do(base.place(cls, point))
                    ns.cancel()
            elif button == 'leftshoulder':
                items.appendleft(items.pop())
                blueprint, cls, cost = items[0]
                obj.image = blueprint
                update()
            elif button == 'rightshoulder':
                items.append(items.popleft())
                blueprint, cls, cost = items[0]
                obj.image = blueprint
                update()

    async def update_reticle():
        while True:
            update()
            await coro.sleep(0.1)

    with showing(obj):
        async with w2d.Nursery() as ns:
            ns.do(update_reticle())
            ns.do(process_input())
