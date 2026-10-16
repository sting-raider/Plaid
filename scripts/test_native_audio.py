"""Empty/silent WAVs fail native audio validation; signed PCM survives."""
import struct
import tempfile
import wave
from pathlib import Path

from native_audio import audio_peak


def main():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'audio.wav'
        for samples, expected in (([], 0), ([0] * 16, 0), ([0, -32768, 7, 0], 32768)):
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((2, 2, 32000, 0, 'NONE', 'not compressed'))
                wav.writeframes(struct.pack(f'<{len(samples)}h', *samples))
            if expected:
                assert audio_peak(path) == expected
            else:
                try:
                    audio_peak(path)
                except ValueError as error:
                    assert 'no non-silent audio' in str(error)
                else:
                    raise AssertionError('silent or empty WAV accepted')
    print('PASS native audio: empty and silent WAVs refused; signed stereo PCM peak checked (3 cases)')


if __name__ == '__main__':
    main()
