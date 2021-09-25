from pygame import mixer
from pygame.mixer import Sound
import pyfxr
import random
from functools import lru_cache

import wasabi2d as w2d

mixer.pre_init(44100, channels=1)
mixer.init()

from wasabi2d import music

music.set_volume(0.2)
music.play('for_robots')


laser = Sound(buffer=pyfxr.SFX(
    base_freq=0.61,
    freq_limit=0.224,
    freq_ramp=-0.304,
    duty=0.656,
    duty_ramp=-0.2,
    env_attack=0.0,
    env_sustain=0.26,
    env_decay=0.184,
    pha_offset=0.01,
    pha_ramp=-0.132,
    wave_type=pyfxr.WaveType.SQUARE,
))
laser.set_volume(0.1)

enemy_laser = Sound(buffer=pyfxr.SFX(
    base_freq=0.46,
    freq_limit=0.2,
    freq_ramp=-0.187,
    duty=0.88,
    duty_ramp=-0.067,
    env_attack=0.0,
    env_sustain=0.285,
    env_decay=0.145,
    env_punch=0.043,
    wave_type=pyfxr.WaveType.SQUARE,
))
enemy_laser.set_volume(0.1)

explosion = Sound(buffer=pyfxr.SFX(
    base_freq=0.06,
    freq_ramp=-0.011,
    env_attack=0.16,
    env_sustain=0.31,
    env_decay=0.67,
    env_punch=0.19,
    lpf_resonance=0.0,
    lpf_freq=0.31,
    lpf_ramp=-0.15,
    wave_type=pyfxr.WaveType.NOISE,
))
explosion.set_volume(0.4)

explosion_small = Sound(buffer=pyfxr.SFX(
    base_freq=0.06,
    freq_limit=0.0,
    freq_ramp=0.0,
    freq_dramp=-0.16,
    env_attack=0.0,
    env_sustain=0.2,
    env_decay=0.38,
    env_punch=0.37,
    pha_offset=-0.045,
    pha_ramp=-0.197,
    arp_speed=0.72,
    arp_mod=0.404,
    wave_type=pyfxr.WaveType.NOISE,
))
explosion_small.set_volume(0.2)

powerup = Sound(buffer=pyfxr.SFX(
    base_freq=0.241,
    freq_ramp=0.16,
    vib_strength=0.33,
    vib_speed=0.51,
    env_attack=0.0,
    env_sustain=0.08,
    env_decay=0.46,
    pha_offset=0.01,
    arp_speed=0.28,
    arp_mod=0.0,
    wave_type=pyfxr.WaveType.SQUARE,
))
powerup.set_volume(0.3)

rocket = Sound(buffer=pyfxr.SFX(
    base_freq=0.25,
    freq_limit=0.07,
    freq_ramp=0.16,
    freq_dramp=-0.2,
    duty=0.46,
    duty_ramp=0.06,
    env_attack=0.19,
    env_sustain=0.17,
    env_decay=0.51,
    env_punch=0.15,
    wave_type=pyfxr.WaveType.NOISE,
))
rocket.set_volume(0.15)

phaser = Sound(buffer=pyfxr.SFX(
    base_freq=0.31,
    freq_limit=0.19,
    freq_ramp=-0.19,
    duty=0.701,
    duty_ramp=-0.192,
    env_attack=0.0,
    env_sustain=0.32,
    env_decay=0.16,
    hpf_freq=0.189,
    wave_type=pyfxr.WaveType.SINE,
))
phaser.set_volume(0.2)


impacts = [
    Sound(buffer=pyfxr.SFX(
        base_freq=0.44 + i * 0.03,
        freq_ramp=-0.652,
        env_attack=0.0,
        env_sustain=0.098,
        env_decay=0.131,
        hpf_freq=0.197,
        wave_type=pyfxr.WaveType.NOISE,
    ))
    for i in range(3)
]
[i.set_volume(0.3) for i in impacts]
def impact():
    random.choice(impacts).play()

@lru_cache
def placement(n):
    freq = 0.29 + n * 0.01
    s = Sound(buffer=pyfxr.SFX(
        base_freq=freq,
        freq_ramp=-0.489,
        env_attack=0.0,
        env_sustain=0.019,
        env_decay=0.234,
        wave_type=pyfxr.WaveType.SAW,
    ))
    s.set_volume(0.05)
    return s


async def play(sound_name):
    snd = w2d.sounds.load(sound_name)
    snd.play()
    try:
        await w2d.clock.coro.sleep(snd.get_length())
    except:
        snd.stop()
        raise


number_names = {
    1: 'one',
    2: 'two',
    3: 'three',
    4: 'four',
    5: 'five',
    6: 'six',
    7: 'seven',
    8: 'eight',
    9: 'nine',
    10: 'ten',
    11: 'eleven',
    12: 'twelve',
    13: 'thirteen',
    14: 'fourteen',
    15: 'fifteen',
    16: 'sixteen',
    17: 'seventeen',
    18: 'eighteen',
    19: 'nineteen',
    20: 'twenty',
    30: 'thirty',
    40: 'forty',
    50: 'fifty',
    60: 'sixty',
    70: 'seventy',
    80: 'eighty',
    90: 'ninety',
}

def spell(n):
    if n <= 20:
        yield number_names[n]
    elif n < 100:
        tens, n = divmod(n, 10)
        yield number_names[tens * 10]
        if n:
            yield number_names[n]
    elif n < 1000:
        hundreds, tens = divmod(n, 100)
        yield number_names[hundreds]
        yield 'hundred'
        if tens:
            yield 'and'
            yield from spell(tens)


def pickup():
    snd = Sound(buffer=pyfxr.SFX(
        base_freq=random.uniform(0.75, 0.9),
        env_attack=0.0,
        env_sustain=0.039,
        env_decay=0.272,
        env_punch=0.468,
        arp_mod=0.253,
    ))
    snd.set_volume(0.2)
    snd.play()
