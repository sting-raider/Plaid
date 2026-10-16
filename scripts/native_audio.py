"""PCM validation shared by native game smoke runs and their synthetic tests."""
import array
import sys
import wave


def audio_peak(path):
    with wave.open(str(path), 'rb') as wav:
        if wav.getnchannels() != 2 or wav.getsampwidth() != 2:
            raise ValueError('native audio must be 16-bit stereo PCM')
        samples = array.array('h', wav.readframes(wav.getnframes()))
    if sys.byteorder != 'little':
        samples.byteswap()
    peak = max(map(abs, samples), default=0)
    if not peak:
        raise ValueError('native validation produced no non-silent audio')
    return peak
