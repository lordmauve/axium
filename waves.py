import numpy as np
import random
from numpy.random import default_rng
import bisect
from itertools import product


def plan_group(strength, seed):
    """Plan a group with the given strength.

    Groups need some variety so we use randomness here, but we use a fixed seed
    in order to generate reproducible results.
    """
    rng = default_rng(abs(hash(seed)))

    if strength < 6:
        ships = rng.integers(2, 4)
    else:
        ships = 4

    strengths = rng.poisson((strength - ships) / ships, (ships,)) + 1
    delta = strength - np.sum(strengths)
    strengths[0] = max(1, strengths[0] + delta)
    return sorted(strengths, reverse=True)


def plan_wave(wave_num):
    """Plan a wave at the given wave number."""
    strength = wave_num + 1
    num_groups = max(1, min(4, strength // 3))
    strength_per_group, remainder = divmod(strength, num_groups)

    return [
        plan_group(
            strength_per_group + (i < remainder),
            seed=(wave_num, i)
        )
        for i in range(num_groups)
    ]


AI_COSTS = [
    ('attack', 1),  # Fly close then attack
    ('sniper', 2),  # Attack from a distance
    ('kamikaze', 3),  # Crash into the target
    ('zapper', 5),  # Fly close and stay close
]

TYPE_COSTS = [
    ('fighter', 1),  # Standard small ship
    ('interceptor', 3),  # Faster ship
    ('bomber', 5),  # Slow ship but with strong health
]

GROUP_COSTS = [
    (False, 1),  # Don't coordinate attacks
    (True, 2),  # Coordinate attacks with the rest of the group
]


def combos(*criteria):
    """Return all combinations of the given criteria and their cost."""
    for options in product(*criteria):
        choices, costs = zip(*options)
        yield np.product(costs), choices


ALL_TYPES = sorted(combos(AI_COSTS, TYPE_COSTS, GROUP_COSTS))


def plan_ship(strength, seed):
    rng = random.Random(abs(hash(seed)))

    idx = bisect.bisect_left(ALL_TYPES, (strength + 1,))
    if idx >= len(ALL_TYPES):
        return ALL_TYPES[-1]
    idx = max(0, idx - 1)
    matches = [ALL_TYPES[idx]]
    found_strength = matches[0][0]
    idx -= 1
    while idx >= 0 and ALL_TYPES[idx][0] == found_strength:
        matches.append(ALL_TYPES[idx])
        idx -= 1

    ship_strength, (ai, type, group_aware) = rng.choice(matches)
    return {
        'ai': ai,
        'type': type,
        'group_aware': group_aware,
        'strength': ship_strength,
        'target_strength': strength,
    }


def plan_ships_of_wave(wave_num):
    groups = []
    for groupnum, ships in enumerate(plan_wave(wave_num)):
        groups.append([
            plan_ship(strength, seed=(groupnum, i))
            for i, strength in enumerate(ships)
        ])
    return groups


if __name__ == '__main__':
    # for i in range(1, 101):
    #     print(plan_wave(i))

    # for group in plan_ships_of_wave(29):
    #     print(group)
    for strength in range(20):
        print(plan_ship(strength, 0))
