from hashlib import sha256
import wasabi2d as w2d
from wasabigeom import vec2
import numpy as np
import pygame
from pygame import joystick
import pygame.mixer
import random
from math import tau, pi, sin, cos
from itertools import count
from contextlib import asynccontextmanager
from dataclasses import dataclass

import sfx
import building
from helpers import showing, random_vec2
from collisions import colgroup
import controllers
from clocks import coro, animate
import clocks
import effects


# Ship deceleration
DECEL = 0.01
ACCEL = 2000
BULLET_SPEED = 700  # px/s
ROCKET_SPEED = 400  # px/s

scene = building.scene = w2d.Scene(1280, 720, title="Axium", fullscreen=True)
#scene.chain = [w2d.chain.LayerRange().wrap_effect('pixellate', pxsize=4, antialias=0.5)]

bg = scene.layers[-3].add_sprite('space', pos=(0, 0))
scene.layers[-3].parallax = 0.03
scene.chain = [
    w2d.chain.LayerRange(stop=-3),
    w2d.chain.Light(
        light=99,
        diffuse=-2,
        ambient=(0.4, 0.4, 0.4, 1)
    ),
    w2d.chain.LayerRange(-1, 90),
]

hudvp = scene.create_viewport()
hud = hudvp.layers[5]
radar_layer = hudvp.layers[0]

effects.init(scene)

# The set of objects the Threx would like to attack
targets = set()


@colgroup.handler('ship', 'threx_bullet')
def handle_collision(ship, shot):
    kill_ship(ship)
    shot.delete()
    colgroup.untrack(shot)


def kill_ship(ship):
    effects.explode(pos=ship.pos, vel=ship.vel)
    ship.nursery.cancel()


def kill_threx(threx):
    effects.pixels.emit(
        10,
        pos=threx.pos,
        vel=threx.vel,
        vel_spread=100,
        size=2,
        age_spread=0.5,
        angle_spread=3,
        spin=10,
        color='red'
    )
    effects.pop(threx.pos, threx.vel, (1.0, 0.3, 0.3, 0.6))
    for _ in range(random.randint(1, 3)):
        game.do(building.star_bit(threx.pos))
    threx.nursery.cancel()


@colgroup.handler('ship', 'threx')
def handle_collision(ship, threx):
    kill_ship(ship)
    kill_threx(threx)


@colgroup.handler('threx', 'bullet')
def handle_collision(threx, bullet):
    kill_threx(threx)
    bullet.delete()
    colgroup.untrack(bullet)



async def bullet(ship):
    sfx.laser.play()
    vel = vec2(BULLET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = w2d.Group([
            scene.layers[1].add_sprite('tripleshot'),
            effects.mklight(),
        ],
        pos=pos,
        angle=ship.angle,
    )
    shot.radius = 20
    with colgroup.tracking(shot, 'bullet'), showing(shot):
        async for dt in coro.frames_dt(seconds=3):
            if not shot:
                break
            shot.pos += vel * dt


async def rocket(ship):
    sfx.laser.play()
    vel = vec2(ROCKET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = w2d.Group(
        [
            scene.layers[1].add_sprite('rocket'),
            effects.flame.add_emitter(
                rate=100,
                pos=(-10, 0),
                pos_spread=1,
                size=4,
                vel=(-100, 0),
                vel_spread=20,
            ),
            effects.mklight(pos=(-10, 0), color='orange')
        ],
        pos=pos,
        angle=ship.angle,
    )
    shot.radius = 20

    target = None

    with colgroup.tracking(shot, 'bullet'), showing(shot):
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
    effects.explode(shot.pos, vec2(0, 0))


async def trail(obj, color='white', stroke_width=2):
    trail = scene.layers[1].add_line(
        [obj.pos] * 50,
        color=color,
        stroke_width=stroke_width,
    )
    *_, alpha = trail.color
    colors = trail.colors
    colors[:, 3] = np.linspace(alpha, 0, 50) ** 2
    trail.colors = colors

    with showing(trail):
        t = 0
        async for dt in coro.frames_dt():
            stern = obj.pos + vec2(-10, 0).rotated(obj.angle)
            verts = trail.vertices
            verts[0] = stern
            t += dt
            if t > 1 / 60:
                verts[1:] = verts[:-1]
                t %= 1 / 60
            trail.vertices = verts


async def threx_shoot(ship):
    sfx.enemy_laser.play()
    vel = vec2(BULLET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + vec2(20, 0).rotated(ship.angle)
    shot = w2d.Group(
        [
            scene.layers[1].add_sprite('threx_bullet1'),
            scene.layers[1].add_sprite('threx_bullet2'),
            effects.mklight(color='red'),
        ],
        pos=pos
    )
    shot.vel = vel
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


async def do_threx(bullet_nursery, pos):
    """Coroutine to run an enemy ship."""
    ship = scene.layers[0].add_sprite('threx', pos=pos)
    ship.radius = 14
    ship.vel = vec2(250, 0)
    ship.rudder = 0

    target = None

    def pick_target():
        nonlocal target
        if random.randrange(5) > 0 and building.base.objects:
            target = random.choice(building.base.objects)
        else:
            target = random.choice(list(targets))

    pick_target()

    async def drive():
        turn_rate = 3.0

        async for dt in coro.frames_dt():
            ship.vel = ship.vel.rotated(ship.rudder * turn_rate * dt)

            ship.pos += ship.vel * dt
            ship.angle = ship.vel.angle()
            cam = scene.camera.pos
            off = (ship.pos - cam)

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

    with colgroup.tracking(ship, 'threx'), showing(ship):
        async with w2d.Nursery() as ns:
            ship.nursery = ns
            ns.do(drive())
            ns.do(steer())
            ns.do(shoot())
            ns.do(trail(ship, color='red', stroke_width=1))


async def do_life(viewport, controller):
    ship = viewport.layers[0].add_sprite('ship')
    ship.radius = 12
    ship.weapon = 'bullet'
    ship.weapon_count = inf = float('inf')
    ship.boosting = False
    targets.add(ship)

    async def drive_ship():
        vel = ship.vel = vec2(0, 0)
        async for dt in coro.frames_dt():
            ship.pos += vel * dt
            viewport.camera.pos = ship.pos
            if vel.length_squared() > 10:
                ship.angle = vel.angle()

            vel = vel * (DECEL ** dt) + controller.read_stick() * ACCEL * dt
            if ship.boosting and vel.length_squared() > 9:
                vel = vel.scaled_to(700)
                effects.pixels.emit(
                    np.random.poisson(20 * dt),
                    pos=ship.pos,
                    pos_spread=3,
                    vel=vel * -0.2,
                    size=1.3,
                    spin=3,
                    color=(0.6, 0.6, 1.0, 0.5)
                )
            ship.vel = vel

    async def boost():
        while True:
            await controller.button_press('b')
            ship.boosting = True
            backwards_left = vec2(-60, -20).rotated(ship.angle)
            backwards_right = vec2(-60, 20).rotated(ship.angle)
            for v in (backwards_left, backwards_right):
                effects.pixels.emit(
                    15,
                    pos=ship.pos,
                    pos_spread=3,
                    vel=v,
                    vel_spread=6,
                    size=1.3,
                    spin=v.y * 0.25,
                    color=(0.6, 0.6, 1.0, 0.5)
                )
            await controller.button_release('b')
            ship.boosting = False

    async def shoot():
        while True:
            button = await controller.button_press('a', 'y')
            if button == 'a':
                func = globals()[ship.weapon]
                ns.do(func(ship))
                ship.weapon_count -= 1
                if ship.weapon_count == 0:
                    ship.weapon = 'bullet'
                    ship.weapon_count = inf
                await coro.sleep(0.1)
            elif button == 'y':
                await building.building_mode(ship, controller, game)

    async def radar():
        tracked = {}
        transparent = (0, 0, 0, 0)
        try:
            async for _ in coro.frames_dt():
                current_threx = colgroup.by_type['threx']
                new_threx = current_threx - tracked.keys()
                for target in new_threx:
                    mark = tracked[target] = radar_layer.add_sprite(
                        'radarmark',
                        color=transparent,
                        scale=3.0
                    )
                    mark.anim = w2d.animate(mark, duration=0.5, scale=1.0)
                dead_threx = tracked.keys() - current_threx
                for t in dead_threx:
                    mark.anim.stop()
                    tracked.pop(t).delete()
                center = viewport.camera.pos
                vprect = viewport.rect
                vprect.center = center
                vpradius = min(viewport.dims) // 2 - 30
                vpcenter = viewport.center

                for target, mark in tracked.items():
                    off = target.pos - center
                    onscreen = vprect.collidepoint(target.pos)
                    mark.color = transparent if onscreen else 'red'
                    mark.pos = vpcenter + off.safe_scaled_to(vpradius)
                    mark.angle = off.angle()
        finally:
            for mark in tracked.values():
                mark.anim.stop()
                mark.delete()


    with colgroup.tracking(ship, 'ship'), showing(ship):
        async with w2d.Nursery() as ns:
            ship.nursery = ns
            ns.do(drive_ship())
            ns.do(shoot())
            ns.do(trail(ship, color=(0.6, 0.8, 1.0, 0.9)))
            ns.do(radar())
            ns.do(boost())
    targets.remove(ship)


async def screenshot(controller):
    """Take screenshots when the player presses the Start button."""
    button = 11
    while True:
        await controller.button_press('start')
        scene.screenshot()
        await controller.button_release('start')


async def collisions():
    async for _ in coro.frames():
        colgroup.process_collisions()


@asynccontextmanager
async def split_screen():
    vp1, hud = scene.viewports
    vp1.width -= 12
    vp2 = scene.viewport.clone(x=scene.width - 10, width=10)
    vp2.camera.pos = 0, 0
    scene.viewports = [vp1, vp2, hud]
    clocks.game.paused = True
    def split(w):
        vp1.width = w
        vp2.x = w
        vp2.width = max(1, scene.width - w)
    async for w in clocks.ui.coro.interpolate(
            scene.width,
            scene.width // 2,
            duration=0.5,
            tween='accel_decel'):
        split(w)
    clocks.game.paused = False
    try:
        yield vp1, vp2
    finally:
        clocks.game.paused = True
        async for w in clocks.ui.coro.interpolate(
                scene.width // 2,
                scene.width,
                duration=0.5,
                tween='accel_decel'):
            split(w)
        vp2.delete()
        clocks.game.paused = False


@asynccontextmanager
async def show_title(text):
    label = hud.add_label(
        text,
        font='sector_034',
        align="center",
        fontsize=36,
        pos=(hudvp.width // 2, 250),
        color=(0, 0, 0, 0)
    )
    label.scale = 0.2
    await animate(label, duration=0.3, scale=1.0, y=200, color=(1, 1, 1, 1))
    yield
    await animate(label, duration=0.5, color=(0, 0, 0, 0), scale=5, y=0)
    label.delete()


async def wave(wave_num):
    async with show_title(f"Beginning wave {wave_num}"):
        await sfx.play('beginning_wave')
        for sound in sfx.spell(wave_num):
            await sfx.play(sound)

    async with w2d.Nursery() as ns:
        if wave_num < 4:
            enemies = wave_num + 1
        else:
            enemies = min(wave_num // 2, 12)
        groups = max(1, min(4, enemies // 3))
        enemies_per_group = enemies / groups
        spawned = 0
        for i in range(groups):
            group_center = vec2(0, 1500).rotated(random.uniform(0, tau))
            while spawned < enemies_per_group * (i + 1):
                pos = group_center + vec2(0, 100).rotated(random.uniform(0, tau))
                ns.do(do_threx(game, pos))
                spawned += 1
    await slowmo()


async def slowmo():
    """Slow down the game for a moment."""
    try:
        await clocks.ui.animate(clocks.game, duration=0.3, rate=0.3)
        await clocks.ui.coro.sleep(1)
        await clocks.ui.animate(clocks.game, duration=0.3, rate=1.0)
    finally:
        clocks.game.rate = 1.0


@dataclass
class Player:
    controller: controllers.Controller
    viewport: w2d.scene.Viewport


async def play_game(nursery):
    lives = 3

    pos = vec2(20, 20)
    icons = [
        hud.add_sprite(
            'ship',
            pos=pos + vec2(24, 0) * i,
            angle=-pi / 2
        )
        for i in range(lives)
    ]
    nursery.do(building.base.place(building.Reactor, vec2(0, 100)))

    def take_life():
        nonlocal lives
        if not lives:
            return False
        lives -= 1
        icons.pop().delete()
        return True

    async def play(viewport, controller):
        while True:
            await do_life(viewport, controller)
            await coro.sleep(3)
            if not take_life():
                hotplug.cancel()
                return
            await clocks.ui.animate(
                viewport.camera,
                duration=0.5,
                pos=vec2(0, 0)
            )

    async def player2():
        async with split_screen() as (_, vp2):
            await play(vp2, controllers.sticks[1])

    async def wait_for_p2():
        await controllers.sticks[1].attached
        await controllers.sticks[1].button_press('start')
        players.do(player2())

    async with w2d.Nursery() as players:
        players.do(play(scene.viewport, controllers.sticks[0]))
        async with w2d.Nursery() as hotplug:
            hotplug.do(wait_for_p2())

    building.base.clear()

    nursery.cancel()


async def joystick_ready():
    label = hud.add_label(
        "Please attach a joystick",
        font='sector_034',
        align="center",
        fontsize=25,
        pos=(hudvp.width // 2, 450),
        color='white',
    )
    with showing(label):
        await controllers.sticks[0].attached


async def title():
    title = w2d.Group([
        hud.add_sprite('title', pos=(hudvp.width // 2, 250)),
    ])
    async def orbit():
        theta = 0
        async for dt in clocks.ui.coro.frames_dt():
            theta += 0.1 * dt
            scene.camera.pos = 200 * vec2(
                cos(theta * 3),
                sin(theta * 5)
            )

    with showing(title):
        async with w2d.Nursery() as ns:
            ns.do(orbit())
            await joystick_ready()
            title.append(hud.add_label(
                "Press start to begin",
                font='sector_034',
                align="center",
                fontsize=25,
                pos=(hudvp.width // 2, 450),
                color='white',
            ))

            await controllers.sticks[0].button_press('start')
            ns.cancel()
        await clocks.ui.animate(scene.camera, duration=0.3, pos=vec2(0, 0))


async def main():
    global game
    async with w2d.Nursery() as services:
        services.do(controllers.hotplug())
        while True:
            stick = await title()
            async with w2d.Nursery() as game:
                effects.game = game
                game.do(play_game(game))
                game.do(screenshot(controllers.sticks[0]))
                game.do(collisions())
                for wave_num in count(1):
                    await wave(wave_num)
        services.cancel()


w2d.run(main())
