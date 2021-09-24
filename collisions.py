from functools import partial
from itertools import combinations
from typing import Iterable, Tuple
from contextlib import contextmanager


class CollisionGroup:
    """Find object collisions using a sort-and-sweep broad phase."""

    def __init__(self):
        self.objects = []
        self.dead = set()
        self.types = {}
        self.handlers = {}
        self.by_type: dict[str, set] = {}

    def add_handler(self, type_a: str, type_b: str, func):
        """Register an object"""
        self.handlers[type_a, type_b] = func
        self.by_type.setdefault(type_a, set())
        self.by_type.setdefault(type_b, set())

    def handler(self, type_a: str, type_b: str):
        """Decorator to register a handler for some types"""
        def dec(func):
            self.add_handler(type_a, type_b, func)
        return dec

    def track(self, obj: object, type: str):
        """Start tracking collisions for an object.

        The object should have .pos and .radius attributes.
        """
        assert type in self.by_type, \
            f"No collision handlers for {type}"
        self.by_type[type].add(obj)
        self.objects.append(obj)
        self.types[obj] = type

    def untrack(self, obj: object):
        """Stop tracking collisions for an object.

        This is a no-op if the object is already untracked.
        """
        self.dead.add(obj)
        type = self.types.pop(obj, None)
        if type:
            self.by_type[type].discard(obj)

    @contextmanager
    def tracking(self, obj: object, type: str):
        """Track an object for collisions within the context."""
        self.track(obj, type)
        try:
            yield
        finally:
            self.untrack(obj)

    def test(self, pos, radius, type) -> list[object]:
        """Find objects within the given radius around pos."""
        found = []
        rsquare = radius * radius
        for o in self.by_type[type]:
            r = o.radius
            if (o.pos - pos).length_squared() < (rsquare + r * r):
                found.append(o)
        return found

    def find_collisions(self) -> Iterable[Tuple[object, object]]:
        self.objects = [o for o in self.objects if o not in self.dead]
        self.dead.clear()

        if not self.objects:
            return

        def collisions_axis(objects, left, right, collisions_y):
            objects.sort(key=left)
            it = iter(objects)
            o = next(it)
            found = [o]
            mark = right(o)
            for o in it:
                if left(o) < mark:
                    found.append(o)
                else:
                    if len(found) > 1:
                        yield from collisions_y(found)
                    found = [o]
                mark = max(mark, right(o))
            if len(found) == len(objects):
                yield found
            elif len(found) > 1:
                yield from collisions_y(found)

        collisions_x = partial(
            collisions_axis,
            left=lambda o: o.pos.x - o.radius,
            right=lambda o: o.pos.x + o.radius,
            collisions_y=lambda objects: collisions_y(objects)
        )
        collisions_y = partial(
            collisions_axis,
            left=lambda o: o.pos.y - o.radius,
            right=lambda o: o.pos.y + o.radius,
            collisions_y=collisions_x
        )

        for group in collisions_x(self.objects):
            for a, b in combinations(group, 2):
                sep = a.pos - b.pos
                if sep.length() < a.radius + b.radius:
                    yield a, b

    def process_collisions(self):
        for a, b in self.find_collisions():
            try:
                types = self.types[a], self.types[b]
            except KeyError:
                # One or other object has probably been deleted in the handler
                continue
            handler = self.handlers.get(types)
            if handler:
                handler(a, b)
                continue

            handler = self.handlers.get(types[::-1])
            if handler:
                handler(b, a)


colgroup = CollisionGroup()
