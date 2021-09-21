from contextlib import contextmanager

import numpy as np
from wasabigeom import vec2


def random_vec2(spread) -> vec2:
    return vec2(
        np.random.normal(0, spread),
        np.random.normal(0, spread),
    )


@contextmanager
def showing(obj):
    """Delete an object after the context."""
    try:
        yield obj
    finally:
        obj.delete()
