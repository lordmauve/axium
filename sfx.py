from pygame import mixer
from pygame.mixer import Sound
import pyfxr

mixer.pre_init(44100, channels=1)
mixer.init()


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
