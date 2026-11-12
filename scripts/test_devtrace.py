import devtrace


def trace(frames, tasks=(), origins=()):
    lines = [f'task {t} data 00001000 size 8 hash {h} vi 1' for t, h in tasks]
    lines += [f'vi {i + 1} ns 0 origin {o} count 0 gfx 0' for i, o in enumerate(origins)]
    lines += [f'rdp {i + 1} commands {c} hash {h:016x} vi {v} ops {ops}' for i, (c, h, v, ops) in enumerate(frames)]
    return devtrace.parse('\n'.join(lines) + '\n')


def test_compare():
    same = [(3, 1, 0, '29:1 36:2'), (3, 2, 60, '29:1 36:2'), (3, 3, 120, '29:1 36:2')]
    report = devtrace.compare(trace(same, [(1, 'aa')], ['00000000', '00000280']), trace(same, [(1, 'aa')], ['00000280']))
    assert 'first divergence none; 0 of the first 1 native hashes' in report[0]
    assert report[2].endswith('same order')  # origin 0 (VI not set up) is ignored
    assert 'RDP frames: native 3 ares 3; first divergence none; 0 of the first 3' in report[3]
    assert report[-1] == 'per-second opcode means compared over 2 seconds, ares shifted +0 s'
    # Second 1 lacks ten triangles natively: a frame ares never drew, and a shifted mean.
    native = same[:1] + [(3, 9, 60, '29:1 36:2'), (3, 3, 120, '29:1 36:2')]
    ares = same[:1] + [(13, 2, 60, '0f:10 29:1 36:2'), (3, 3, 120, '29:1 36:2')]
    report = devtrace.compare(trace(native), trace(ares))
    assert 'first divergence at frame 1; 1 of the first 3 native frames never occur in ares, first at frame 1 (native vi 60, 3 commands)' in report[3]
    assert '  second 1: opcode 0f per frame native 0.0 ares 10.0' in report


if __name__ == '__main__':
    test_compare()
    print('devtrace comparison passed')
