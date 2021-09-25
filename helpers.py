from contextlib import contextmanager
import random
from math import tau, pi

import numpy as np
import wasabi2d as w2d
from wasabigeom import vec2


def random_vec2(spread) -> vec2:
    return vec2(
        np.random.normal(0, spread),
        np.random.normal(0, spread),
    )


def random_ring(r) -> vec2:
    """Get a random point on a ring of radius r around the origin."""
    return vec2(0, r).rotated(random.uniform(0, tau))


def angle_to(target, from_obj) -> float:
    return angle_to_pos(target.pos, from_obj)


def angle_to_pos(pos, from_obj) -> float:
    sep = pos - from_obj.pos
    r = (sep.angle() - from_obj.angle) % tau
    if r > pi:
        r -= tau
    return r


@contextmanager
def showing(obj):
    """Delete an object after the context."""
    try:
        yield obj
    finally:
        obj.delete()
