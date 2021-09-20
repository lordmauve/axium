import wasabi2d as w2d
from wasabigeom import vec2
import numpy as np
import pyfxr
from pygame import joystick
import pygame.mixer

import sfx

joystick.init()
stick = joystick.Joystick(0)

# Ship deceleration
DECEL = 0.1
ACCEL = 1000
BULLET_SPEED = 700  # px/s

scene = w2d.Scene(1280, 720)
bg = scene.layers[-3].add_sprite('space', pos=(0, 0))


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
    async for dt in w2d.clock.coro.frames_dt(seconds=3):
        shot.pos += vel * dt
    shot.delete()


async def do_life():
    ship = scene.layers[0].add_sprite('ship')
    trail = scene.layers[1].add_line(
        [ship.pos] * 50,
        color=(0.6, 0.8, 1.0, 0.6),
        stroke_width=3,
    )

    async def drive_ship():
        vel = ship.vel = vec2(0, 0)
        async for dt in w2d.clock.coro.frames_dt():
            ship.pos += vel * dt
            scene.camera.pos = ship.pos
            bg.pos = ship.pos - 0.03 * scene.camera.pos
            if vel.length_squared() > 10:
                ship.angle = vel.angle()
            vel = vel * (DECEL ** dt) + read_joy() * ACCEL * dt
            ship.vel = vel

            stern = ship.pos + vec2(-10, 0).rotated(ship.angle)
            trail.vertices = np.vstack([
                [stern],
                trail.vertices[:-1]
            ])

    async def shoot():
        async for _ in w2d.clock.coro.frames():
            if stick.get_button(0):
                ns.do(bullet(ship))
                await w2d.clock.coro.sleep(0.1)

    async with w2d.Nursery() as ns:
        ns.do(drive_ship())
        ns.do(shoot())


async def main():
    for _ in range(3):
        await do_life()


w2d.run(main())
