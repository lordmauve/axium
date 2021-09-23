import sys
import pygame
import wasabi2d as w2d
from pygame import joystick
from wasabigeom import vec2
from pathlib import Path
from functools import lru_cache

controller_db = Path(__file__).parent / 'data/gamecontrollerdb.txt'

joystick.init()

if sys.platform == 'linux':
    PLATFORM = 'Linux'
elif sys.platform == 'win32':
    PLATFORM = 'Windows'
elif sys.platform == 'darwin':
    PLATFORM = 'Mac OS X'
else:
    import warnings
    warnings.warn(UserWarning(
        "Couldn't detect platform; "
        "controller mappings may not be available"
    ))
    PLATFORM = 'unknown'


@lru_cache()
def load_db() -> dict:
    data = {}
    with controller_db.open() as f:
        for lineno, line in enumerate(f, start=1):
            line = line.strip()
            if line.startswith('#') or not line:
                continue

            try:
                guid, name, *kvs = line.rstrip(',').split(',')
            except ValueError:
                raise ValueError(
                    f"Error parsing {controller_db} at line {lineno}: {line!r}"
                )
            mapping = {}
            for kv in kvs:
                key, colon, value = kv.partition(':')
                if not colon:
                    raise ValueError(
                        f"Error parsing {controller_db} "
                        f"at line {lineno}: {line!r}"
                    )
                mapping[key] = value
            platform = mapping.pop('platform').strip()
            if platform != PLATFORM:
                # Drop data that doesn't correspond to the current platform
                continue
            data[guid] = name, mapping
    return data


DEFAULT_MAPPING = {
    'leftx': 'a0',
    'lefty': 'a1',
    'start': 'b6',
    'a': 'b0',
    'b': 'b1',
    'x': 'b2',
    'y': 'b3',
}


def getter(buttoncode, stick):
    if buttoncode[0] == 'a':
        num = int(buttoncode[1:])
        return lambda: stick.get_axis(num)
    elif buttoncode[0] == 'b':
        num = int(buttoncode[1:])
        return lambda: stick.get_button(num)
    elif buttoncode[0] == 'h':
        hat, axis = map(int, buttoncode[1:].split('.'))
        return lambda: stick.get_hat(hat)[axis]
    else:
        raise ValueError(f"Unknown button code {buttoncode}")


class Controller:
    def __init__(self):
        self.attached = w2d.Event()
        self.detached = w2d.Event()
        self.detached.set()
        self.id = None

    def _reattach(self, num):
        self.stick = joystick.Joystick(num)
        self.id = self.stick.get_instance_id()

        guid = self.stick.get_guid()
        self.name, mapping = load_db().get(guid, DEFAULT_MAPPING)
        self.leftx = getter(mapping['leftx'], self.stick)
        self.lefty = getter(mapping['lefty'], self.stick)

        self.a = getter(mapping['a'], self.stick)
        self.b = getter(mapping['b'], self.stick)
        self.x = getter(mapping['x'], self.stick)
        self.y = getter(mapping['y'], self.stick)

        self.buttonmap = {
            name: int(buttoncode[1:])
            for name, buttoncode in mapping.items()
            if buttoncode.startswith('b')
        }
        self.revmap = {v: k for k, v in self.buttonmap.items()}
        self.attached.set()
        self.detached.reset()

    def _detach(self):
        self.detached.set()
        self.attached.reset()

    def read_stick(self) -> vec2:
        """Get a vector representing the joystick input."""
        jx = self.leftx()
        jy = self.lefty()
        v = vec2(jx, jy)
        length = min(1, v.length() * 1.05)
        if length < 0.1:
            return vec2(0, 0)
        return v.scaled_to(length)

    async def button_press(self, *buttons) -> str:
        """Wait for a button press on this stick."""
        while True:
            ev = await w2d.next_event(pygame.JOYBUTTONDOWN)
            if ev.instance_id != self.id:
                continue
            button = self.revmap.get(ev.button, ev.button)
            if not buttons or button in buttons:
                return button

    async def button_release(self, *buttons) -> str:
        """Wait for a button release on this stick."""
        while True:
            ev = await w2d.next_event(pygame.JOYBUTTONUP)
            if ev.instance_id != self.id:
                continue
            button = self.revmap.get(ev.button, ev.button)
            if not buttons or button in buttons:
                return button


MAX_STICKS = 2
sticks = [Controller() for _ in range(MAX_STICKS)]
player_count = 0


async def hotplug():
    global player_count
    import clocks

    while True:
        # FIXME: we should not lose track of which stick is bound to which slot
        num_sticks = joystick.get_count()
        print(f"Detected {num_sticks} joysticks")
        for i in range(MAX_STICKS):
            if i < num_sticks:
                sticks[i]._reattach(i)
            else:
                sticks[i]._detach()
        player_count = min(num_sticks, MAX_STICKS)
        await w2d.next_event(pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED)
