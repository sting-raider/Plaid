"""Exercise the bounded raw capture independently of a game or ares."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        source, exe, record = tmp / 'test.c', tmp / 'test.exe', tmp / 'record.json'
        source.write_text('''
#include <stdio.h>
#include <stdint.h>
typedef uint8_t u8;
typedef uint32_t u32;
#include "repair_capture.h"
int main(int argc, char **argv) {
  static u8 ram[0x30000];
  for (u32 i = 0; i < sizeof ram; ++i) ram[i] = (u8)i;
  if (plaid_repair_capture(argv[1], ram, sizeof ram, 3, 0x80000040, 0x80018000, 17) != 1) return 1;
  if (plaid_repair_capture(argv[2], ram, sizeof ram, 15, 0x80000004, 0, 18) != 1) return 2;
  if (plaid_repair_capture(argv[3], ram, sizeof ram, 3, 0, 0x90000000, 0) != 0) return 3;
  if (plaid_repair_capture(argv[3], ram, sizeof ram, 8, 0x80000000, 0, 0) != 0) return 4;
  return 0;
}
''')
        cc = shutil.which('gcc') or shutil.which('clang')
        if not cc:
            raise RuntimeError('C compiler required')
        subprocess.run([cc, '-std=c11', '-I', str(ROOT), str(source), '-o', str(exe)], check=True)
        second, rejected = tmp / 'second.json', tmp / 'rejected.json'
        subprocess.run([str(exe), str(record), str(second), str(rejected)], check=True)
        data = json.loads(record.read_text())
        assert (data['fault'], data['site'], data['target'], data['vi'], data['physical_start']) == (
            3, '80000040', '80018000', 17, 0x8000)
        assert bytes.fromhex(data['bytes']) == bytes(i & 255 for i in range(0x8000, 0x28000))
        data = json.loads(second.read_text())
        assert data['target'] == '80000004' and data['physical_start'] == 0
        assert len(bytes.fromhex(data['bytes'])) == 0x10004
        assert not rejected.exists()
    print('PASS bounded raw repair capture')


if __name__ == '__main__':
    main()
