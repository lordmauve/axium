
import wasabi2d as w2d
from wasabigeom import vec2

from pygame import joystick

joystick.init()
stick = joystick.Joystick(0)

# Ship deceleration
DECEL = 0.1
ACCEL = 1000

scene = w2d.Scene()


def read_joy() -> vec2:
    jx = stick.get_axis(0)
    jy = stick.get_axis(1)
    return vec2(jx, jy)


async def do_life():
    ship = scene.layers[0].add_sprite('ship')

    async def drive_ship():
        vel = vec2(0, 0)
        async for dt in w2d.clock.coro.frames_dt():
            ship.pos += vel * dt
            if vel.length_squared() > 10:
                ship.angle = vel.angle()
            vel = vel * (DECEL ** dt) + read_joy() * ACCEL * dt


    await drive_ship()


async def main():
    for _ in range(3):
        await do_life()


w2d.run(main())
