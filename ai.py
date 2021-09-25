import random
from contextlib import contextmanager
import operator

from wasabigeom import vec2

from collisions import colgroup
from clocks import coro, animate
from helpers import angle_to


class NullTarget:
    """A dummy target for when everything is dead.

    Causes enemies to head towards the world origin.
    """
    pos = vec2(0, 0)

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
        fire_weapon()
        await coro.sleep(1)
