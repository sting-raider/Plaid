"""A mutated queue capacity cannot cause host division or a false normal return."""
import json
import subprocess


def run(exe, cc, T):
    queue, buffer, slot = 0x80004000, 0x80004100, 0x80004200
    for name in ('osSendMesg', 'osRecvMesg', 'osJamMesg'):
        for count in (0, 0xffffffff):
            program = [*T.li(T.A.sp, 0x80007f00), *T.call('osCreateMesgQueue', queue, buffer, 1),
                       *T.poke(queue + 8, 1), *T.poke(queue + 16, count),
                       *T.poke(buffer, 42), *T.poke(slot, 0xcafebabe),
                       *T.call(name, queue, slot if name == 'osRecvMesg' else 7, 0), *T.A.DONE]
            for function in ('osCreateMesgQueue', name):
                program += [function, T.A.jr(T.A.ra), T.A.nop]
            binary = T.build(exe, cc, 'invalid-queue', program, ['osCreateMesgQueue', name])
            result = subprocess.run([str(binary), '--dump', hex(slot), '1'], capture_output=True, text=True, timeout=30)
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            stop = next(row for row in rows if 'stop' in row)
            if count == 0 and name != 'osRecvMesg':
                assert result.returncode == 0 and stop['fault'] == 0 and stop['gpr'][2] == 'ffffffff', result.stdout
            else:
                assert result.returncode and stop['fault'] == 12, result.stdout
            assert next(row for row in rows if 'dump' in row)['words'] == [0xcafebabe]
    for name in ('osSendMesg', 'osRecvMesg', 'osJamMesg'):
        program = [*T.li(T.A.sp, 0x80007f00), *T.call(name, queue, 0, 0), *T.A.DONE,
                   name, T.A.jr(T.A.ra), T.A.nop]
        binary = T.build(exe, cc, 'zero-queue-probe', program, [name])
        result = subprocess.run([str(binary), '--dump', hex(queue), '6'], capture_output=True, text=True, timeout=30)
        rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        stop = next(row for row in rows if 'stop' in row)
        assert result.returncode == 0 and stop['fault'] == 0 and stop['gpr'][2] == 'ffffffff', result.stdout
        assert next(row for row in rows if 'dump' in row)['words'] == [0] * 6
    print('PASS queue capacity boundaries: zero-capacity nonblocking sends return full; receive division and negative capacity refuse before writes')
