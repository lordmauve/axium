import numpy as np
import wasabi2d as w2d
from wasabigeom import vec2
import random

import sfx
from helpers import random_vec2, showing
from collisions import colgroup


scene: w2d.Scene = None


@colgroup.handler('ship', 'star_bit')
def handle_collect(ship, star_bit):
    star_bit.collected = ship
    colgroup.untrack(star_bit)


async def star_bit(pos):
    scale = random.uniform(0.05, 0.08)
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
