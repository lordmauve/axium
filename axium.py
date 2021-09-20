from hashlib import sha256
from typing import Tuple
from numpy.lib.nanfunctions import nansum
import wasabi2d as w2d
from wasabigeom import vec2
import numpy as np
import pygame
from pygame import joystick
import pygame.mixer
import random
from math import tau, pi
from functools import partial
from itertools import combinations, count
from typing import Iterable, Tuple
from contextlib import contextmanager

import sfx

joystick.init()
stick = joystick.Joystick(0)

# Ship deceleration
DECEL = 0.01
ACCEL = 2000
BULLET_SPEED = 700  # px/s

scene = w2d.Scene(1280, 720, title="Axium")
bg = scene.layers[-3].add_sprite('space', pos=(0, 0))
hud = scene.layers[5]
hud.is_hud = True

coro = w2d.clock.coro


particles = scene.layers[1].add_particle_group(max_age=1, drag=0.5)
particles.add_color_stop(0, (1, 1, 1, 1))
particles.add_color_stop(1, (0, 0, 0, 0))


# The set of objects the Threx would like to attack
targets = set()


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
        targets.add(self)


Reactor()



class CollisionGroup:
    """Find object collisions using a sort-and-sweep broad phase."""

    def __init__(self):
        self.objects = []
        self.dead = set()
        self.types = {}
        self.handlers = {}

    def add_handler(self, type_a: str, type_b: str, func):
        """Register an object"""
        self.handlers[type_a, type_b] = func

    def handler(self, type_a: str, type_b: str):
        """Decorator to register a handler for some types"""
        def dec(func):
            self.add_handler(type_a, type_b, func)
        return dec

    def track(self, obj: object, type: str):
        self.objects.append(obj)
        self.types[obj] = type

    def untrack(self, obj: object):
        self.dead.add(obj)
        self.types.pop(obj, None)

    def find_collisions(self) -> Iterable[Tuple[object, object]]:
        self.objects = [o for o in self.objects if o not in self.dead]
        self.dead.clear()

        if not self.objects:
            return

        def collisions_axis(objects, left, right, collisions_y):
            objects.sort(key=left)
            it = iter(objects)
            o = next(it)
            found = [o]
            mark = right(o)
            for o in it:
                if left(o) < mark:
                    found.append(o)
                else:
                    if len(found) > 1:
                        yield from collisions_y(found)
                    found = [o]
                mark = max(mark, right(o))
            if len(found) == len(objects):
                yield found
            elif len(found) > 1:
                yield from collisions_y(found)

        collisions_x = partial(
            collisions_axis,
            left=lambda o: o.x - o.radius,
            right=lambda o: o.x + o.radius,
            collisions_y=lambda objects: collisions_y(objects)
        )
        collisions_y = partial(
            collisions_axis,
            left=lambda o: o.y - o.radius,
            right=lambda o: o.y + o.radius,
            collisions_y=collisions_x
        )

        for group in collisions_x(self.objects):
            for a, b in combinations(group, 2):
                sep = a.pos - b.pos
                if sep.length() < a.radius + b.radius:
                    yield a, b

    def process_collisions(self):
        for a, b in self.find_collisions():
            try:
                types = self.types[a], self.types[b]
            except KeyError:
                # One or other object has probably been deleted in the handler
                continue
            handler = self.handlers.get(types)
            if handler:
                handler(a, b)
                continue

            handler = self.handlers.get(types[::-1])
            if handler:
                handler(b, a)


colgroup = CollisionGroup()

@colgroup.handler('ship', 'threx_shot')
def handle_collision(ship, shot):
    particles.emit(50, pos=ship.pos, vel=ship.vel, vel_spread=50)
    ship.nursery.cancel()
    shot.delete()
    colgroup.untrack(shot)


@colgroup.handler('threx', 'bullet')
def handle_collision(threx, bullet):
    particles.emit(50, pos=threx.pos, vel=threx.vel, vel_spread=50, color='red')
    threx.nursery.cancel()
    bullet.delete()
    colgroup.untrack(bullet)


def read_joy() -> vec2:
    """Get a vector representing the joystick input."""
    jx = stick.get_axis(0)
    jy = stick.get_axis(1)
    v = vec2(jx, jy)
    length = v.length() * 1.05
    length = min(1, length ** 2)
    if length < 0.1:
        length = 0
    return v.scaled_to(length)


async def bullet(ship):
    sfx.laser.play()
    vel = vec2(BULLET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = scene.layers[1].add_sprite(
        'tripleshot',
        pos=pos,
        angle=ship.angle,
    )
    shot.radius = 20
    colgroup.track(shot, 'bullet')

    async for dt in coro.frames_dt(seconds=3):
        if not shot.is_alive():
            break
        shot.pos += vel * dt
    else:
        shot.delete()
    colgroup.untrack(shot)


async def joy_press(*buttons):
    """Wait until one of the given buttons is pressed."""
    while True:
        ev = await w2d.next_event(pygame.JOYBUTTONDOWN)
        if not buttons or ev.button in buttons:
            return ev


async def joy_release(*buttons):
    """Wait until one of the given buttons is pressed."""
    while True:
        ev = await w2d.next_event(pygame.JOYBUTTONUP)
        if not buttons or ev.button in buttons:
            return ev


def trail(obj, color='white', stroke_width=2):
    trail = scene.layers[1].add_line(
        [obj.pos] * 50,
        color=color,
        stroke_width=stroke_width,
    )
    *_, alpha = trail.color
    colors = trail.colors
    colors[:, 3] = np.linspace(alpha, 0, 50) ** 2
    trail.colors = colors

    try:
        while True:
            yield
            stern = obj.pos + vec2(-10, 0).rotated(obj.angle)
            trail.vertices = np.vstack([
                [stern],
                trail.vertices[:-1]
            ])
    finally:
        trail.delete()


async def threx_shoot(ship):
    sfx.enemy_laser.play()
    vel = vec2(BULLET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = w2d.Group(
        [
            scene.layers[1].add_sprite('threx_bullet1'),
            scene.layers[1].add_sprite('threx_bullet2'),
        ],
        pos=pos
    )
    shot.radius = 12
    colgroup.track(shot, 'threx_bullet')

    async for dt in coro.frames_dt(seconds=2):
        if not shot:
            break
        shot.pos += vel * dt
        shot[0].angle += 4 * dt
        shot[1].angle -= 2 * dt
    shot.delete()


async def do_threx(bullet_nursery):
    """Coroutine to run an enemy ship."""
    pos = vec2(
        random.uniform(-200, 200),
        random.uniform(-200, 200),
    )

    ship = scene.layers[0].add_sprite('threx', pos=pos)
    mark = hud.add_sprite('radarmark')
    ship.radius = 14
    ship.vel = vec2(250, 0)
    ship.rudder = 0
    t = trail(ship, color='red', stroke_width=1)

    target = random.choice(list(targets))

    def angle_to(obj) -> float:
        sep = target.pos - ship.pos
        r = (sep.angle() - ship.angle) % tau
        if r > pi:
            r -= tau
        return r

    async def drive():
        turn_rate = 3.0

        async for dt in coro.frames_dt():
            ship.vel = ship.vel.rotated(ship.rudder * turn_rate * dt)

            ship.pos += ship.vel * dt
            ship.angle = ship.vel.angle()
            next(t)
            cam = scene.camera.pos
            off = (ship.pos - cam)
            if off.length() > 360:
                mark.pos = off.scaled_to(300)
                mark.angle = off.angle()
                mark.color = (1, 1, 1, 1)
            else:
                mark.color = (0, 0, 0, 0)

    async def steer():
        async for dt in coro.frames_dt():
            r = angle_to(target)

            if r > 1e-2:
                ship.rudder = 1
            elif r < -1e-2:
                ship.rudder = -1
            else:
                ship.rudder = 0

            sep = target.pos - ship.pos
            if sep.length() < 100 + target.radius:
                ship.rudder = random.choice((1, -1))
                await coro.sleep(0.2)

    async def shoot():
        while True:
            async for dt in coro.frames_dt():
                if abs(angle_to(target)) < 0.2:
                    break
                await coro.sleep(0.1)
            bullet_nursery.do(threx_shoot(ship))
            await coro.sleep(1)

    async with w2d.Nursery() as ns:
        ship.nursery = ns
        colgroup.track(ship, 'threx')
        ns.do(drive())
        ns.do(steer())
        ns.do(shoot())
    colgroup.untrack(ship)
    mark.delete()
    ship.delete()


async def do_life():
    ship = scene.layers[0].add_sprite('ship')
    ship.radius = 12
    targets.add(ship)

    async def drive_ship():
        vel = ship.vel = vec2(0, 0)
        t = trail(ship, color=(0.6, 0.8, 1.0, 0.9))
        async for dt in coro.frames_dt():
            ship.pos += vel * dt
            scene.camera.pos = ship.pos
            bg.pos = ship.pos - 0.03 * scene.camera.pos
            if vel.length_squared() > 10:
                ship.angle = vel.angle()

            vel = vel * (DECEL ** dt) + read_joy() * ACCEL * dt
            if stick.get_button(1):
                vel = vel.scaled_to(600)
            ship.vel = vel
            next(t)

    async def shoot():
        while True:
            await joy_press(0)
            ns.do(bullet(ship))
            await coro.sleep(0.1)

    async with w2d.Nursery() as ns:
        ship.nursery = ns
        colgroup.track(ship, 'ship')
        ns.do(drive_ship())
        ns.do(shoot())

    ship.delete()
    targets.remove(ship)


async def screenshot():
    """Take screenshots when the player presses the Start button."""
    button = 11
    while True:
        await joy_press(button)
        scene.screenshot()
        await joy_release(button)


async def collisions():
    async for _ in coro.frames():
        colgroup.process_collisions()


@contextmanager
def showing(obj):
    try:
        yield obj
    finally:
        obj.delete()


async def show_title(text):
    label = hud.add_label(
        text,
        font='sector_034',
        align="center",
        fontsize=36,
        pos=(0, 0),
        color=(0, 0, 0, 0)
    )
    label.scale = 0.2
    await w2d.animate(label, duration=0.3, scale=1.0, y=-200, color=(1, 1, 1, 1))
    await coro.sleep(3)
    await w2d.animate(label, duration=0.5, color=(0, 0, 0, 0), scale=5, y=-400)
    label.delete()


async def wave(wave_num):
    await show_title(f"Begining wave {wave_num}")
    async with w2d.Nursery() as ns:
        for _ in range(wave_num):
            ns.do(do_threx(ns))
    await coro.sleep(5)


async def main():
    async with w2d.Nursery() as game:
        game.do(do_life())
        game.do(screenshot())
        game.do(collisions())
        for wave_num in count(1):
            await wave(wave_num)


w2d.run(main())
