from hashlib import sha256
import wasabi2d as w2d
from wasabigeom import vec2
import numpy as np
import pygame
from pygame import joystick
import pygame.mixer
import random
from math import tau, pi
from itertools import count
from contextlib import asynccontextmanager

import sfx
import building
from helpers import showing, random_vec2
from collisions import colgroup
from controllers import stick, read_joy, joy_press, joy_release
from clocks import coro, animate
import clocks


# Ship deceleration
DECEL = 0.01
ACCEL = 2000
BULLET_SPEED = 700  # px/s
ROCKET_SPEED = 400  # px/s

scene = building.scene = w2d.Scene(1280, 720, title="Axium", fullscreen=False)
#scene.chain = [w2d.chain.LayerRange().wrap_effect('pixellate', pxsize=4, antialias=0.5)]

bg = scene.layers[-3].add_sprite('space', pos=(0, 0))
hud = scene.layers[5]
hud.is_hud = True


pixels = scene.layers[1].add_particle_group(
    max_age=1.5,
    clock=clocks.game,
)
pixels.add_color_stop(0, (1, 1, 1, 1))
pixels.add_color_stop(1, (1, 1, 1, 1))
pixels.add_color_stop(1.5, (1, 1, 1, 0))

smoke = scene.layers[1].add_particle_group(
    max_age=3,
    drag=0.1,
    spin_drag=0.5,
    grow=2,
    texture='smoke_04',
    clock=clocks.game,
)
smoke.add_color_stop(0, (0.3, 0.3, 0.3, 1))
smoke.add_color_stop(1, (0, 0, 0, 1))
smoke.add_color_stop(3, (0, 0, 0, 0))

flame = scene.layers[1].add_particle_group(
    max_age=1,
    drag=0.5,
    spin_drag=0.5,
    grow=3,
    texture='smoke_04',
    clock=clocks.game,
)
flame.add_color_stop(0, (2, 2, 0.2, 1))
flame.add_color_stop(0.2, (1, 0.3, 0.0, 1))
flame.add_color_stop(0.5, (0, 0, 0.0, 1))
flame.add_color_stop(1, (0, 0, 0, 0))



# The set of objects the Threx would like to attack
targets = set()



# @colgroup.handler('ship', 'threx_bullet')
# def handle_collision(ship, shot):
#     explode(pos=ship.pos, vel=ship.vel)
#     ship.nursery.cancel()
#     shot.delete()
#     colgroup.untrack(shot)


@colgroup.handler('threx', 'bullet')
def handle_collision(threx, bullet):
    pixels.emit(10, pos=threx.pos, vel=threx.vel, vel_spread=100, size=2, age_spread=0.5, angle_spread=3, spin=10, color='red')
    async def splode(pos, vel):
        with showing(scene.layers[1].add_sprite('light_01', pos=pos, color=(1, 0.3, 0.3, 1.0), scale=0.01)) as ring:
            animate(ring, duration=0.3, scale=0.4, color=(1, 0.3, 0.3, 0.0), angle=6)
            async for dt in coro.frames_dt():
                ring.pos += vel * dt

    game.do(splode(threx.pos, threx.vel))
    for _ in range(random.randint(1, 3)):
        game.do(building.star_bit(threx.pos))
    threx.nursery.cancel()
    bullet.delete()
    colgroup.untrack(bullet)


def explode(pos, vel):
    sfx.explosion.play()
    scene.camera.screen_shake(10)
    smoke.emit(
        20,
        pos=pos,
        vel=vel * 0.6,
        vel_spread=100,
        angle_spread=3,
        spin_spread=5,
        age_spread=0.3,
        size=12
    )

    async def trail():
        emitter = flame.add_emitter(
            pos=pos,
            rate=200,
            size=6,
            pos_spread=3,
            vel_spread=10,
            spin_spread=5,
            emit_angle_spread=3,
        )
        emitter_vel = random_vec2(100) + vel
        emitter_accel = random_vec2(200)
        with showing(emitter):
            async for dt in coro.frames_dt(seconds=random.uniform(0.5, 1.0)):
                emitter_vel += emitter_accel * dt
                emitter.pos += emitter_vel * dt
                emitter.rate *= 0.7 ** dt
                if emitter.rate < 1:
                    break

    for _ in range(random.randint(2, 5)):
        game.do(trail())



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
    with colgroup.tracking(shot, 'bullet'), showing(shot):
        async for dt in coro.frames_dt(seconds=3):
            if not shot.is_alive():
                break
            shot.pos += vel * dt


async def rocket(ship):
    sfx.laser.play()
    vel = vec2(ROCKET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = w2d.Group(
        [
            scene.layers[1].add_sprite('rocket'),
            flame.add_emitter(
                rate=100,
                pos=(-10, 0),
                pos_spread=1,
                size=4,
                vel=(-100, 0),
                vel_spread=20,
            )
        ],
        pos=pos,
        angle=ship.angle,
    )
    shot.radius = 20
    colgroup.track(shot, 'bullet')

    target = None

    async for dt in coro.frames_dt(seconds=2):
        if not target or not target.is_alive():
            target = None
            objs = colgroup.test(shot.pos, 200, 'threx')
            if objs:
                target = objs[0]

        if target:
            r = angle_to(target, shot)

            if r > 1e-2:
                vel = vel.rotated(min(r, 10 * dt))
            elif r < -1e-2:
                vel = vel.rotated(max(r, -10 * dt))
            shot.angle = vel.angle()

        if not shot:
            break
        shot.pos += vel * dt
    else:
        shot.delete()
    colgroup.untrack(shot)
    explode(shot.pos, vec2(0, 0))



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
            verts = trail.vertices
            verts[0] = stern
            verts[1:] = verts[:-1]
            trail.vertices = verts
    finally:
        trail.delete()


async def run_trail(trail):
    async for _ in coro.frames_dt():
        next(trail)


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
    with colgroup.tracking(shot, 'threx_bullet'), showing(shot):
        async for dt in coro.frames_dt(seconds=2):
            if not shot:
                break
            shot.pos += vel * dt
            shot[0].angle += 4 * dt
            shot[1].angle -= 2 * dt


def angle_to(target, from_obj) -> float:
    sep = target.pos - from_obj.pos
    r = (sep.angle() - from_obj.angle) % tau
    if r > pi:
        r -= tau
    return r


async def do_threx(bullet_nursery):
    """Coroutine to run an enemy ship."""
    pos = vec2(
        random.uniform(-200, 200),
        random.uniform(-200, 200),
    )

    ship = scene.layers[0].add_sprite('threx', pos=pos)
    mark = hud.add_sprite('radarmark', color='red')
    ship.radius = 14
    ship.vel = vec2(250, 0)
    ship.rudder = 0
    t = trail(ship, color='red', stroke_width=1)

    if random.randrange(5) > 0 and building.base.objects:
        target = random.choice(building.base.objects)
    else:
        target = random.choice(list(targets))

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
                mark.color = 'red'
            else:
                mark.color = (0, 0, 0, 0)

    async def steer():
        async for dt in coro.frames_dt():
            r = angle_to(target, ship)

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
                if abs(angle_to(target, ship)) < 0.2:
                    break
                await coro.sleep(0.1)
            bullet_nursery.do(threx_shoot(ship))
            await coro.sleep(1)

    with colgroup.tracking(ship, 'threx'), showing(ship), showing(mark):
        async with w2d.Nursery() as ns:
            ship.nursery = ns
            ns.do(drive())
            ns.do(steer())
            ns.do(shoot())


async def do_life():
    ship = scene.layers[0].add_sprite('ship')
    ship.radius = 12
    ship.weapon = 'bullet'
    ship.weapon_count = inf = float('inf')
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
            if stick.get_button(1) and vel.length_squared() > 9:
                vel = vel.scaled_to(600)
            ship.vel = vel
            next(t)

    async def shoot():
        while True:
            ev = await joy_press(0, 3)
            if ev.button == 0:
                func = globals()[ship.weapon]
                ns.do(func(ship))
                ship.weapon_count -= 1
                if ship.weapon_count == 0:
                    ship.weapon = 'bullet'
                    ship.weapon_count = inf
                await coro.sleep(0.1)
            elif ev.button == 3:
                await building.building_mode(ship, game)

    with colgroup.tracking(ship, 'ship'), showing(ship):
        async with w2d.Nursery() as ns:
            ship.nursery = ns
            ns.do(drive_ship())
            ns.do(shoot())

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


@asynccontextmanager
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
    await animate(label, duration=0.3, scale=1.0, y=-200, color=(1, 1, 1, 1))
    yield
    await animate(label, duration=0.5, color=(0, 0, 0, 0), scale=5, y=-400)
    label.delete()


async def wave(wave_num):
    async with show_title(f"Begining wave {wave_num}"):
        await sfx.play('beginning_wave')
        for sound in sfx.spell(wave_num):
            await sfx.play(sound)

    async with w2d.Nursery() as ns:
        for _ in range(wave_num + 1):
            ns.do(do_threx(game))
    await slowmo()


async def slowmo():
    """Slow down the game for a moment."""
    try:
        await clocks.ui.animate(clocks.game, duration=0.3, rate=0.3)
        await clocks.ui.coro.sleep(1)
        await clocks.ui.animate(clocks.game, duration=0.3, rate=1.0)
    finally:
        clocks.game.rate = 1.0


async def main():
    global game
    async with w2d.Nursery() as game:
        game.do(do_life())
        game.do(screenshot())
        game.do(collisions())
        for wave_num in count(1):
            await wave(wave_num)


w2d.run(main())
