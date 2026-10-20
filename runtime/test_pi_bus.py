"""Read-only PI writes retain latch/busy effects; compare authored guest reads to ares."""
import json
import os
import shutil
import subprocess


def run(exe, cc, T):
    from test_tlb_execution import _ares_run
    A, out = T.A, T.OUT
    # The write/read pair stays in one instruction-cache line.
    program = [A.lui(A.t0, 0xb000), A.lui(A.t1, 0x1234), A.ori(A.t1, A.t1, 0x5678),
               A.sw(A.t1, 0x40, A.t0), A.lw(A.s0, 0x40, A.t0), A.lw(A.s1, 0x40, A.t0), *A.DONE]
    raw = out / 'pi-readonly.bin'
    raw.write_bytes(A.assemble(program))
    reference = _ares_run(raw)
    assert reference.returncode == 0, (reference.stdout, reference.stderr)
    regs = json.loads(next(line for line in reference.stdout.splitlines() if line.startswith('{')))['regs']
    assert regs[A.s0] == 0x12345678 and regs[A.s1] == 0, regs
    source = out / 'pi-bus.c'
    source.write_text(r'''
#include <stdint.h>
#include <assert.h>
typedef uint32_t u32;
typedef uint64_t u64;
#include "pi_bus.h"
int main(void) {
  plaid_pi_bus bus = {0}; u32 value = 0;
  plaid_pi_bus_write(&bus, 0x12345678, 1000);
  assert(plaid_pi_bus_busy(&bus, 1000) && plaid_pi_bus_busy(&bus, 1199));
  assert(!plaid_pi_bus_busy(&bus, 1200));
  plaid_pi_bus_write(&bus, 0xabcdef01, 1001); /* ignored while busy */
  assert(plaid_pi_bus_read_pending(&bus, 1002, &value) && value == 0x12345678);
  assert(!plaid_pi_bus_busy(&bus, 1003));
  assert(!plaid_pi_bus_read_pending(&bus, 1003, &value));
  plaid_pi_bus_write(&bus, 0xabcdef01, 1200);
  assert(plaid_pi_bus_read_pending(&bus, 1201, &value) && value == 0xabcdef01);
  plaid_pi_bus_write(&bus, 0x11223344, 1300);
  assert(!plaid_pi_bus_read_pending(&bus, 1500, &value));
  return 0;
}
''')
    binary = out / ('pi-bus.exe' if os.name == 'nt' else 'pi-bus')
    subprocess.run([cc, '-O2', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(T.ROOT / 'runtime'), str(source), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True, timeout=30)
    # The runtime route preserves ROM contents after writes and leaves save
    # space unmodelled. Read after the deadline avoids host clock sensitivity.
    program = [*T.li(A.sp, 0x80007f00), *T.poke(0xb0000040, 0x12345678),
               *T.call('osGetCount'), *T.li(A.s0, 10000), 'wait',
               A.addiu(A.s0, A.s0, -1), A.bne(A.s0, A.zero, 'wait'), A.nop,
               *T.log_word(0xb0000040), *A.DONE, 'osGetCount', A.jr(A.ra), A.nop]
    binary = T.build(exe, cc, 'pi-readonly', program, ['osGetCount'])
    rom = out / 'pi-readonly.z64'
    rom.write_bytes(bytes.fromhex('80371240') + bytes(0x3c) + bytes.fromhex('cafef00d') + bytes(0xfbc))
    result = subprocess.run([str(binary), '--rom', str(rom), '--dump', hex(T.LOG), '1'], capture_output=True, text=True, timeout=30)
    rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    assert result.returncode == 0 and next(r['words'] for r in rows if 'words' in r) == [0xcafef00d], (result.stdout, result.stderr)
    print('PI read-only bus: ares latch read, ignored busy writes, 200-COUNT deadline, read completion and unchanged ROM')


if __name__ == '__main__':
    import test_runtime as T
    T.OUT.mkdir(parents=True, exist_ok=True)
    run(T.ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid'),
        os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang'), T)
