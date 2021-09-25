import wasabi2d as w2d
from wasabigeom import vec2
import numpy as np
import pygame
import pygame.mixer
import random
from math import tau, pi, sin, cos
from itertools import count, cycle
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

import sfx
import building
from helpers import showing, random_ring, angle_to
from collisions import colgroup
import controllers
from clocks import coro, animate
import clocks
import effects
import waves
import ai

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
    threx.nursery.cancel()


@colgroup.handler('ship', 'threx')
def handle_collision(ship, threx):
    kill_ship(ship)
    kill_threx(threx)


@colgroup.handler('threx', 'bullet')
def handle_collision(threx, bullet):
    threx.health -= bullet.damage
    if threx.health <= 0:
        kill_threx(threx)
        for _ in range(random.randint(1, 3)):
            game.do(building.star_bit(threx.pos))
    else:
        effects.pixels.emit(
            5,
            pos=threx.pos,
            vel=bullet.vel * 0.3,
            vel_spread=50,
            size=2,
            age_spread=0.5,
            angle_spread=3,
            spin=10,
            color='red'
        )

    if threx.health > 0 or bullet.fragile:
        bullet.delete()
        colgroup.untrack(bullet)


async def bullet(ship):
    sfx.laser.play()
    shot = w2d.Group([
            scene.layers[1].add_sprite('tripleshot'),
            effects.mklight(),
        ],
    )
    shot.damage = 10
    shot.radius = 10
    shot.fragile = True
    await shoot(shot, ship)


async def shoot(shot, shooter, offset=vec2(20, 0), type='bullet', max_age=3):
    vel = vec2(BULLET_SPEED, 0).rotated(shooter.angle) + shooter.vel
    shot.pos = shooter.pos + offset.rotated(shooter.angle)
    shot.angle = shooter.angle
    shot.vel = vel
    with colgroup.tracking(shot, type), showing(shot):
        async for dt in coro.frames_dt(seconds=max_age):
            if not shot:
                break
            shot.pos += vel * dt


async def phaser(ship):
    sfx.laser.play()
    light = effects.mklight()
    light.scale *= 2
    shot = w2d.Group([
            scene.layers[1].add_sprite('phaser'),
            light,
        ]
    )
    shot.radius = 22
    shot.damage = 10
    shot.fragile = False
    await shoot(shot, ship)


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
    shot.damage = 20
    shot.fragile = True
    shot.vel = vel

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
            shot.vel = vel
    effects.explode(shot.pos, vec2(0, 0))


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
    shot.damage = 5
    with colgroup.tracking(shot, 'threx_bullet'), showing(shot):
        async for dt in coro.frames_dt(seconds=2):
            if not shot:
                break
            shot.pos += vel * dt
            shot[0].angle += 4 * dt
            shot[1].angle -= 2 * dt


async def threx_bomb(ship, offset):
    sfx.enemy_laser.play()
    vel = vec2(BULLET_SPEED, 0).rotated(ship.angle) + ship.vel
    pos = ship.pos + offset.rotated(ship.angle)
    shot = w2d.Group(
        [
            scene.layers[1].add_sprite('threx_bullet1'),
            scene.layers[1].add_sprite('threx_bullet2'),
            effects.mklight(color='red'),
            effects.smoke.add_emitter(
                rate=70,
                color=(1, 0, 0, 0.6),
                emit_angle_spread=3,
                spin_spread=2,
                size=5,
            )
        ],
        pos=pos
    )
    shot.vel = vel
    shot.radius = 12
    shot.damage = 15
    with colgroup.tracking(shot, 'threx_bullet'), showing(shot):
        async for dt in coro.frames_dt(seconds=3):
            if not shot:
                break
            shot.pos += vel * dt
            shot[0].angle += 4 * dt
            shot[1].angle -= 2 * dt


async def do_threx(bullet_nursery, pos, ship_plan, groupctx):
    """Coroutine to run an enemy ship."""

    if ship_plan['type'] == 'fighter':
        ship = scene.layers[0].add_sprite('threx', pos=pos)
        ship.radius = 14
        ship.speed = 250
        ship.weapon_interval = 1.0
        ship.health = 10
        ship.turn_rate = 3.0

        def weapon_func():
            bullet_nursery.do(threx_shoot(ship))
    elif ship_plan['type'] == 'interceptor':
        ship = scene.layers[0].add_sprite('threx_interceptor', pos=pos)
        ship.radius = 18
        ship.speed = 350
        ship.health = 10
        ship.weapon_interval = 0.5
        ship.turn_rate = 2.0
        def weapon_func():
            for port in (vec2(0, -15), vec2(0, 15)):
                shot = w2d.Group(
                    [
                        scene.layers[1].add_sprite('threx_phaser', pos=(-5, 0)),
                        effects.mklight(color='red'),
                    ]
                )
                shot.radius = 8
                shot.damage = 5
                bullet_nursery.do(shoot(
                    shot,
                    ship,
                    offset=port,
                    type='threx_bullet',
                    max_age=1
                ))
    elif ship_plan['type'] == 'bomber':
        ship = scene.layers[0].add_sprite('threx_bomber', pos=pos)
        ship.radius = 30
        ship.speed = 150
        ship.health = 40
        ship.weapon_interval = 1.0
        ship.turn_rate = 1.0
        ports = cycle([vec2(10, -25), vec2(10, 25)])
        def weapon_func():
            port = next(ports)
            bullet_nursery.do(threx_bomb(ship, port))
    else:
        raise ValueError(f"Unknown ship type {ship_plan['type']}")

    ship.vel = vec2(ship.speed, 0)
    ship.rudder = 0
    ship.plan = ship_plan

    if not ship.plan['group_aware']:
        groupctx = ai.Group()
    ship.groupctx = groupctx

    ai.pick_target(ship)
    with colgroup.tracking(ship, 'threx'), showing(ship), groupctx.ship_alive():
        async with w2d.Nursery() as ns:
            ship.nursery = ns
            ns.do(ai.reconsider_target(ship))
            ns.do(getattr(ai, ship.plan['ai'])(ship, weapon_func))
            ns.do(effects.trail(ship, color='red', stroke_width=1))

    if ship_plan['type'] == 'bomber':
        effects.explode(ship.pos, vec2(0, 0))


async def do_life(player):
    viewport = player.viewport
    controller = player.controller
    ship = player.viewport.layers[0].add_sprite('ship')
    ship.radius = 12
    ship.weapon = 'bullet'
    ship.weapon_count = inf = float('inf')
    ship.boosting = False
    ship.balance = player.balance
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
                await building.building_mode(ship, player, game)

    async def radar():
        tracked = {}
        transparent = (0, 0, 0, 0)
        blue = (0.6, 0.6, 1.0, 1.0)
        try:
            async for _ in coro.frames_dt():
                objects = {(t, 'red') for t in colgroup.by_type['threx']}
                objects |= {(t, blue) for t in colgroup.by_type['building']}
                objects |= {
                    (t, blue) for t in colgroup.by_type['ship'] if t is not ship
                }
                new_objects = objects - tracked.keys()
                for target in new_objects:
                    mark = tracked[target] = radar_layer.add_sprite(
                        'radarmark',
                        color=transparent,
                        scale=3.0
                    )
                    mark.anim = w2d.animate(mark, duration=0.5, scale=1.0)
                dead_objects = tracked.keys() - objects
                for t in dead_objects:
                    mark.anim.stop()
                    tracked.pop(t).delete()
                center = viewport.camera.pos
                vprect = viewport.rect
                vprect.center = center
                vpradius = min(viewport.dims) // 2 - 30
                vpcenter = viewport.center

                for (target, color), mark in tracked.items():
                    off = target.pos - center
                    onscreen = vprect.collidepoint(target.pos)
                    mark.color = transparent if onscreen else color
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
            ns.do(effects.trail(ship, color=(0.6, 0.8, 1.0, 0.9)))
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


async def wave(wave_num, groups=None):
    async with show_title(f"Beginning wave {wave_num}"):
        await sfx.play('beginning_wave')
        for sound in sfx.spell(wave_num):
            await sfx.play(sound)

    async with w2d.Nursery() as ns:
        groups = groups or waves.plan_ships_of_wave(wave_num)
        for plan, groupctx in zip(groups, ai.mkgroups(len(groups))):
            group_center = random_ring(1500)
            for ship_plan in plan:
                pos = group_center + random_ring(100)
                ns.do(do_threx(game, pos, ship_plan, groupctx))
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
    balance: 'Balance'


class Balance:
    INITIAL_BALANCE = 0

    def __init__(self, value=None):
        self._value = self._display_value = value or self.INITIAL_BALANCE
        self.sprite = w2d.Group([
                hud.add_label(
                    str(int(self._value)),
                    font='sector_034',
                    align="right",
                    fontsize=20,
                    color='white',
                    pos=(-20, 10)
                ),
                hud.add_sprite('money_symbol', pos=(-10, 0)),
            ],
            pos=(scene.viewport.width - 5, 20)
        )

    @property
    def pos(self):
        return self.sprite.pos

    @pos.setter
    def pos(self, v):
        self.sprite.pos = v

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        clocks.ui.animate(self, tween='decelerate', display_value=v)
        self._value = v

    @property
    def display_value(self):
        return self._display_value

    @display_value.setter
    def display_value(self, v):
        v = self._display_value = int(v)
        self.sprite[0].text = str(v)

    def delete(self):
        self.sprite.delete()


async def play_game(nursery):
    lives = 5

    pos = vec2(20, 20)
    icons = [
        hud.add_sprite(
            'ship',
            pos=pos + vec2(24, 0) * i,
            angle=-pi / 2
        )
        for i in range(lives)
    ]
    balance = Balance()
    nursery.do(building.base.place(building.Reactor, vec2(0, 100)))

    def take_life():
        nonlocal lives
        if not lives:
            return False
        lives -= 1
        icons.pop().delete()
        return True

    async def play(player):
        while True:
            await do_life(player)
            await coro.sleep(3)
            if not take_life():
                hotplug.cancel()
                return
            await clocks.ui.animate(
                player.viewport.camera,
                duration=0.5,
                pos=vec2(0, 0)
            )

    async def player2():
        async with split_screen() as (_, vp2):
            player2 = Player(
                controller=controllers.sticks[1],
                viewport=vp2,
                balance=balance,
            )
            await play(player2)

    async def wait_for_p2():
        await controllers.sticks[1].attached
        p2_start = hud.add_label(
            "Player 2 Press start",
            font='sector_034',
            align="center",
            fontsize=14,
            pos=((hudvp.width * 3) // 4, hudvp.height - 20),
            color=(1, 1, 1, 0.33)
        )
        with showing(p2_start):
            await controllers.sticks[1].button_press('start')
            players.do(player2())

    with showing(balance):
        async with w2d.Nursery() as players:
            player1 = Player(
                controller=controllers.sticks[0],
                viewport=scene.viewport,
                balance=balance,
            )
            players.do(play(player1))
            async with w2d.Nursery() as hotplug:
                hotplug.do(wait_for_p2())

    building.base.clear()

    nursery.cancel()


async def joystick_ready():
    label = hud.add_label(
        "Please connect a game controller",
        font='sector_034',
        align="center",
        fontsize=20,
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
    from argparse import ArgumentParser
    p = ArgumentParser()
    p.add_argument('--wave', type=int, help="Wave to start with", default=1)
    p.add_argument('--cash', type=int, help="Start with extra cash", default=0)
    p.add_argument(
        '--test-threx',
        action='store_true',
        help="Walk through enemy ship combos",
        default=False
    )
    args = p.parse_args()

    Balance.INITIAL_BALANCE = args.cash or 0

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
                if args.wave != 1:
                    # FIXME: this causes a crash for some reason?
                    # File "wasabi2d/primitives/text.py", line 34, in render
                    #     self.tex.use(0)
                    #   File "moderngl/texture.py", line 403, in use
                    #     self.mglo.use(location)
                    # AttributeError: 'mgl.InvalidObject' object has no attribute 'use'
                    #
                    # async with title("Get ready!"):
                    #     await coro.sleep(20)
                    await coro.sleep(5)
                for wave_num in count(args.wave):
                    if args.test_threx:
                        await wave(wave_num, waves.test_ship_type(wave_num))
                    else:
                        await wave(wave_num)
        services.cancel()


w2d.run(main())
