import random
from contextlib import contextmanager
import operator

import wasabi2d as w2d
from wasabigeom import vec2

from collisions import colgroup
from clocks import coro, animate
from helpers import angle_to, random_ring
import effects


class NullTarget:
    """A dummy target for when everything is dead.

    Causes enemies to head towards the world origin.
    """
    pos = vec2(0, 0)
    radius = 1

    def __bool__(self):
        return False


NULL_TARGET = NullTarget()


class Group:
    """A group of ships that can coordinate.

    Ships that don't coordinate can just create their own private group.
    """

    def __init__(self, groups=frozenset()):
        self.other_groups = groups
        self._base_target = None
        self._ship_target = None
        self.ships = 0

    @contextmanager
    def ship_alive(self, ship):
        self.ships += 1
        try:
            yield
        finally:
            self.ships -= 1
            if self.ships == 0:
                self.other_groups.discard(self)
            elif self.ships == 1:
                self.other_groups.discard(self)
                if self.other_groups:
                    merge_with = min(
                        self.other_groups,
                        key=operator.attrgetter('ships')
                    )
                    merge_with.ships += self.ships
                    self.__dict__ = merge_with.__dict__

    def get_ship_target(self):
        if not colgroup.by_type['ship']:
            self._ship_target = None
            return self.get_base_target()
        if self._ship_target in colgroup.by_type['ship']:
            return self._ship_target

        t = self._ship_target = colgroup.choose_random('ship')
        return t

    def get_base_target(self):
        if not colgroup.by_type['building']:
            self._base_target = None
            return NULL_TARGET

        if self._base_target in colgroup.by_type['building']:
            return self._base_target

        t = self._base_target = colgroup.choose_random('building')
        return t

    def get_fighter_target(self, pos):
        targets = {self.get_ship_target(), self.get_base_target()}
        targets.discard(NULL_TARGET)

        if not targets:
            return NULL_TARGET

        return min(targets, key=lambda t: (t.pos - pos).length_squared())


def mkgroups(num):
    """Create num interrelated group objects."""
    groups = set()
    for _ in range(num):
        groups.add(Group(groups))
    return list(groups)


def pick_target(ship):
    if ship.plan['ai'] in ('attack', 'sniper'):
        ship.target = ship.groupctx.get_fighter_target(ship.pos)
    else:
        ship.target = ship.groupctx.get_base_target()


async def reconsider_target(ship):
    """Periodically reconsider the ship's target."""
    async for _ in coro.intervals(seconds=1):
        pick_target(ship)


async def drive(ship):
    turn_rate = 3.0

    async for dt in coro.frames_dt():
        ship.vel = ship.vel.rotated(ship.rudder * turn_rate * dt)

        ship.pos += ship.vel * dt
        ship.angle = ship.vel.angle()


async def steer(ship):
    async for dt in coro.frames_dt():
        target = ship.target
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


async def shoot(ship, fire_weapon):
    attack_range = 1000 if ship.plan['ai'] == 'sniper' else 400
    while True:
        async for dt in coro.frames_dt():
            target = ship.target
            dist = (target.pos - ship.pos).length()
            if dist < attack_range and abs(angle_to(target, ship)) < 0.2:
                break
            await coro.sleep(0.1)
        if target is NULL_TARGET:
            await coro.sleep(1)
            continue
        fire_weapon()
        await weapon_cooldown(ship)


async def drive_kamikaze(ship):
    async for dt in coro.frames_dt():
        target = ship.target
        sep = target.pos - ship.pos
        if target is not NULL_TARGET \
            and sep.length_squared() < target.radius ** 2 + ship.radius ** 2:
            break
        ship.angle = sep.angle()
        ship.vel = sep.scaled_to(ship.speed)
        ship.pos += ship.vel * dt

    effects.explode(ship.pos, ship.vel * 0.2)
    damage = {
        'fighter': 30,
        'interceptor': 50,
        'bomber': 120,
    }
    target.hit(damage[ship.plan['type']])



async def attack(ship, weapon_func):
    async with w2d.Nursery() as ns:
        ns.do(drive(ship))
        ns.do(steer(ship))
        ns.do(shoot(ship, weapon_func))


sniper = attack


async def kamikaze(ship, weapon_func):
    ship.speed *= 1.3
    ship.vel *= 1.3
    async with w2d.Nursery() as ns:
        ns.do(drive_kamikaze(ship))
        ns.do(shoot(ship, weapon_func))


async def weapon_cooldown(ship):
    await coro.sleep(ship.weapon_interval)


async def zapper(ship, weapon_func):
    target = ship.target

    # Zappers can fire faster
    ship.weapon_interval *= 0.7

    async def move_to_firing_pos():
        async for dt in coro.frames_dt():
            if ship.target is not target:
                return False
            firing_pos = target.pos - (target.pos - ship.pos).scaled_to(200)

            sep = firing_pos - ship.pos
            if sep.length_squared() < 50:
                return True
            ship.angle = sep.angle()
            ship.vel = sep.scaled_to(ship.speed)
            ship.pos += ship.vel * dt

    while True:
        target = ship.target
        if not await move_to_firing_pos():
            continue

        sep = target.pos - ship.pos
        await animate(ship, duration=0.1, angle=sep.angle())
        while ship.target is target:
            weapon_func()
            await weapon_cooldown(ship)
