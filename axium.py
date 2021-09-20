import wasabi2d as w2d
from wasabigeom import vec2
import numpy as np
import pygame
from pygame import joystick
import pygame.mixer

import sfx

joystick.init()
stick = joystick.Joystick(0)

# Ship deceleration
DECEL = 0.1
ACCEL = 1000
BULLET_SPEED = 700  # px/s

scene = w2d.Scene(1280, 720, title="Axium")
bg = scene.layers[-3].add_sprite('space', pos=(0, 0))

coro = w2d.clock.coro


def read_joy() -> vec2:
    jx = stick.get_axis(0)
    jy = stick.get_axis(1)
    return vec2(jx, jy)


async def bullet(ship):
    sfx.laser.play()
    vel = vec2(BULLET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = scene.layers[1].add_sprite(
        'tripleshot',
        pos=pos,
        angle=ship.angle,
    )
    async for dt in coro.frames_dt(seconds=3):
        shot.pos += vel * dt
    shot.delete()


async def joy_press(*buttons):
    """Wait until one of the given buttons is pressed."""
    while True:
        ev = await w2d.next_event(pygame.JOYBUTTONDOWN)
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
    shot = w2d.Group([
        scene.layers[1].add_sprite('threx_bullet1'),
        scene.layers[1].add_sprite('threx_bullet2'),
    ],
        pos=pos
    )
    async for dt in coro.frames_dt():
        shot.pos += vel * dt
        shot[0].angle += 4 * dt
        shot[1].angle -= 2 * dt
    shot.delete()


async def do_threx(bullet_nursery):
    """Coroutine to run an enemy ship."""
    ship = scene.layers[0].add_sprite('threx')
    ship.vel = vec2(0, 0)
    t = trail(ship, color='red', stroke_width=1)
    async def drive():
        async for dt in coro.frames_dt():
            ship.x += 30 * dt
            next(t)

    async def shoot():
        while True:
            bullet_nursery.do(threx_shoot(ship))
            await coro.sleep(1)

    async with w2d.Nursery() as ns:
        ns.do(drive())
        ns.do(shoot())


async def do_life():
    ship = scene.layers[0].add_sprite('ship')
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
            ship.vel = vel
            next(t)

    async def shoot():
        while True:
            await joy_press(0)
            ns.do(bullet(ship))
            await coro.sleep(0.1)

    async with w2d.Nursery() as ns:
        ns.do(drive_ship())
        ns.do(shoot())


async def main():
    for _ in range(3):
        async with w2d.Nursery() as game:
            game.do(do_life())
            game.do(do_threx(game))


w2d.run(main())
