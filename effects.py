import random

import wasabi2d as w2d
from wasabi2d.primitives.particles import ParticleGroup
from wasabigeom import vec2

from helpers import showing, random_vec2
import clocks
from clocks import animate, coro
import sfx

scene: w2d.Scene
game: w2d.Nursery
pixels: ParticleGroup = None
smoke: ParticleGroup = None
flame: ParticleGroup = None


def init(s: w2d.Scene):
    global pixels, smoke, flame, scene

    scene = s
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


def mklight(pos=vec2(0, 0), color='white'):
    return scene.layers[99].add_sprite('point_light', pos=pos, color=color)


def pop(pos, vel, color=(1, 1, 1, 1)):
    async def run_pop():
        ring = scene.layers[1].add_sprite(
            'light_01',
            pos=pos,
            color=color[:3] + (0.6,),
            scale=0.01
        )
        light = mklight(pos=pos, color=color)
        with showing(ring), showing(light):
            animate(
                ring,
                duration=0.3,
                scale=0.2,
                color=color[:3] + (0.0,),
                angle=6
            )
            animate(
                light,
                duration=0.3,
                scale=0.2
            )
            async for dt in coro.frames_dt(seconds=0.3):
                ring.pos += vel * dt
    game.do(run_pop())


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
            rate=200,
            size=6,
            pos_spread=3,
            vel_spread=10,
            spin_spread=5,
            emit_angle_spread=3,
        )
        group = w2d.Group([emitter, mklight(color='orange')], pos=pos)
        emitter_vel = random_vec2(100) + vel
        emitter_accel = random_vec2(200)
        with showing(group):
            async for dt in coro.frames_dt(seconds=random.uniform(0.5, 1.0)):
                emitter_vel += emitter_accel * dt
                group.pos += emitter_vel * dt
                emitter.rate *= 0.7 ** dt
                if emitter.rate < 1:
                    break

    for _ in range(random.randint(2, 4)):
        game.do(trail())
