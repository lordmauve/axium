import pygame
import wasabi2d as w2d
from pygame import joystick
from wasabigeom import vec2


joystick.init()
stick = joystick.Joystick(0)


def read_joy() -> vec2:
    """Get a vector representing the joystick input."""
    jx = stick.get_axis(0)
    jy = stick.get_axis(1)
    v = vec2(jx, jy)
    length = min(1, v.length() * 1.05)
    if length < 0.1:
        length = 0
    return v.scaled_to(length)


async def joy_press(*buttons):
    """Wait until one of the given buttons is pressed."""
    while True:
        ev = await w2d.next_event(pygame.JOYBUTTONDOWN)
        if not buttons or ev.button in buttons:
            return ev


async def joy_release(*buttons):
    """Wait until one of the given buttons is pressed."""
    while True:
        ev = await w2d.next_event(pygame.JOYBUTTONUP)
        if not buttons or ev.button in buttons:
            return ev
