"""Captured code is separate from ROM and dispatch rechecks the whole window."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from repair_record import admit_records, native_manifest, write_record


def main():
    exe = ROOT / 'target/debug' / ('plaid.exe' if os.name == 'nt' else 'plaid')
    cc = os.environ.get('CC') or shutil.which('gcc') or shutil.which('clang')
    with tempfile.TemporaryDirectory(prefix='observed-', dir=ROOT / 'target') as temporary:
        out = Path(temporary)
        def plaid(*args, ok=True):
            r = subprocess.run([str(exe), *map(str, args)], capture_output=True, text=True)
            assert (r.returncode == 0) == ok, (args, r.stdout, r.stderr)
            return r.stdout

        rom = bytearray(4096)
        rom[:4] = bytes.fromhex('80371240')
        # An unresolved tail; ROM has SYSCALL at the runtime-observed destination.
        rom[64:76] = bytes.fromhex('8c9900000320000800000000')
        rom[96:100] = bytes.fromhex('0000000c')
        source, loads, mapping, c = (out / n for n in ('test.z64', 'loads.json', 'map.json', 'game.c'))
        source.write_bytes(rom)
        payload = bytes.fromhex('240200073c08a000ad02100003e0000800000000deadbeef')
        raw = out / 'raw.json'
        raw.write_text(json.dumps(dict(format='plaid-repair-raw-v0', fault=15, site='80000020',
                                       target='80000020', vi=10, physical_start=32, bytes=payload.hex())))
        record_path = write_record(raw, out / 'repair')
        record = json.loads(record_path.read_text())
        loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic observed image', loads=[])))
        admit_records(loads, [record_path])
        discover = ('discover', source, '64', '0x80000000', '64', '0x80000000', mapping, '--loads', loads)
        plaid(*discover)
        original = mapping.read_bytes()
        plaid(*discover)
        assert mapping.read_bytes() == original
        program = json.loads(original)
        spec = next(iter(program['load_images'].values()))
        assert spec['observed']['1'] == record
        placed = next(l['destination']['start'] for l in spec['loads'] if 'observed' in l['encoding'])
        assert placed != 0x80000020 and any(b['start']['pc'] == placed for b in program['blocks'])
        verdict = json.loads(plaid('solve', source, mapping, '--residual-dispatch'))
        assert verdict['residual_sites'] and (verdict['status'] == 'closed' or verdict['blockers'] == verdict['trapped_sites']), verdict
        manifest = native_manifest(program, verdict, True)
        assert not manifest['native_complete'] and manifest['observed_images'] == [dict(
            image=hashlib.sha256(payload).hexdigest(), sha256=record['sha256'], generation=1,
            window_base=32, window_size=len(payload), observed_root='80000020', site_pc='80000020', storage_base=placed)]
        (out / 'native-manifest.json').write_text(json.dumps(manifest))
        plaid('lower-map', source, mapping, '0x80000000', '0x80000f00', c, ok=False)
        plaid('lower-map', source, mapping, '0x80000000', '0x80000f00', c, '--residual-dispatch')
        harness = out / 'harness.c'
        harness.write_text('''#include <assert.h>
#include <string.h>
#include "game.c"
#include "runtime.c"
static plaid_state s;
static const unsigned char payload[] = {''' + ','.join(map(str, payload)) + '''};
int main(void) {
  for (int mode = 0; mode < 7; mode++) {
    memset(&s,0,sizeof s); plaid_load_images(&s);
    memcpy(s.ram+32,payload,sizeof payload);
    s.r[4]=SX32(0x80004000u); s.r[31]=SX32(0x80000f00u);
    s.ram[0x4000]=0x80; s.ram[0x4003]=0x20;
    if (mode == 1) s.ram[32] ^= 1;
    if (mode == 2) s.ram[sizeof payload+31] ^= 1; /* unexecuted captured byte */
    if (mode >= 3) {
      assert(plaid_link(&s,0x80000020u) != 1 && !s.fault);
      if (mode == 3) s.ram[32] ^= 1; /* bypass write tracking: cached binding must recheck */
      else if (mode == 4) { s.ram[0x4000]=0xa0; } /* uncached alias */
    }
    if (mode == 5) {
      for (unsigned k=0;k<PLAID_OVLS;k++) if (s.ovl_ok[k]) s.ovl_active[k]=1;
      assert(plaid_write_check(&s,32,4,0x80001000u));
      assert(plaid_store(&s,SX32(0xa0000020u),4,0,0x80001000u) && s.fault==2);
      assert(!memcmp(s.ram+32,payload,sizeof payload)); continue;
    }
    if (mode == 6) {
      assert(!plaid_protected(&s,32,4,0x80001000u)); s.ram[32]^=1;
    }
    int r=plaid_run(&s);
    assert(!plaid_safepoints && !s.native_frames);
    if (mode == 1 || mode == 2 || mode == 3 || mode == 4 || mode == 6) {
      assert(r && s.fault==17 && s.fault_pc==(mode==4 ? 0xa0000020u : 0x80000020u));
      assert(s.r[2]==0 && s.r[8]==0 && s.ram[0x1003]==0);
    } else {
      assert(!r && !s.fault && s.pc==0x80000f00u);
      for (int i=0;i<32;i++) assert(s.r[i] == (i==2 ? 7 : i==4 ? SX32(0x80004000u) :
        i==8 ? SX32(0xa0000000u) : i==25 ? SX32(mode==4 ? 0xa0000020u : 0x80000020u) :
        i==31 ? SX32(0x80000f00u) : 0));
      assert(s.ram[0x1000]==0 && s.ram[0x1001]==0 && s.ram[0x1002]==0 && s.ram[0x1003]==7);
      assert(!memcmp(s.ram+32,payload,sizeof payload) && !s.hi && !s.lo && !s.cp0_known);
    }
  }
  return 0;
}
''')
        binary = out / 'test.exe'
        subprocess.run([cc, '-O0', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                        '-I', str(out), '-I', str(ROOT / 'spikes/096-native-slice'), str(harness), '-lm', '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True, timeout=30, env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
        doc = json.loads(loads.read_text())
        other = bytes([*payload[:3], 11, *payload[4:]])
        second = dict(record, bytes=other.hex(), sha256=hashlib.sha256(other).hexdigest())
        rom_payload = bytes([*payload[:3], 3, *payload[4:]])
        for name, extra, images, results in [
                ('generations', second, [payload, other], [7, 11]),
                ('ambiguous', record, [payload], [17]),
                ('rom', None, [rom_payload, payload], [3, 7]),
                ('direct', None, [payload], [7])]:
            selected = json.loads(json.dumps(doc))
            if extra:
                selected['observed_images'].append(dict(generation=2, record=extra))
            else:
                rom[96:96+len(rom_payload)] = rom_payload
                if name == 'direct':
                    rom[64:76] = bytes.fromhex('080000080000000000000000')
                source.write_bytes(rom)
            loads.write_text(json.dumps(selected))
            plaid(*discover)
            manifest = native_manifest(json.loads(mapping.read_bytes()), {}, False)
            assert not manifest['native_complete']
            assert [r['generation'] for r in manifest['observed_images']] == ([1, 2] if extra else [1])
            plaid('lower-map', source, mapping, '0x80000000', '0x80000f00', c, '--residual-dispatch')
            harness.write_text('''#include <assert.h>
#include <string.h>
#include "game.c"
#include "runtime.c"
static plaid_state s;
static const unsigned char images[][''' + str(len(payload)) + '] = {' + ','.join('{' + ','.join(map(str, data)) + '}' for data in images) + '};\n' +
                'static const unsigned results[] = {' + ','.join(map(str, results)) + '''};
int main(void) {
  for (unsigned i=0;i<sizeof results/sizeof results[0];i++) {
    memset(&s,0,sizeof s); plaid_load_images(&s); memcpy(s.ram+32,images[i],sizeof images[i]);
    s.r[4]=SX32(0x80004000u); s.r[31]=SX32(0x80000f00u);
    s.ram[0x4000]=0x80; s.ram[0x4003]=0x20;
    int r=plaid_run(&s);
    assert(!plaid_safepoints && !s.native_frames);
    if (results[i]==17) assert(r && s.fault==17 && !s.r[2] && !s.ram[0x1003]);
    else assert(!r && !s.fault && s.r[2]==results[i] && s.ram[0x1003]==results[i] && s.pc==0x80000f00u);
  }
  return 0;
}
''')
            subprocess.run([cc, '-O0', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                            '-I', str(out), '-I', str(ROOT / 'spikes/096-native-slice'), str(harness), '-lm', '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True, timeout=30, env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
            if name == 'generations':
                plaid('lower-map', source, mapping, '0x80000000', '0x80000f00', c,
                      '--residual-dispatch', '--parts', '3', '--runtime-unit')
                harness.write_text(harness.read_text().replace('#include "game.c"', '#include "game.runtime.h"'))
                subprocess.run([cc, '-O0', '-std=c11', '-Wall', '-Werror', '-Wno-unused-label',
                                '-I', str(out), '-I', str(ROOT / 'spikes/096-native-slice'), str(harness),
                                str(c), *map(str, sorted(out.glob('game.part*.c'))), '-lm', '-o', str(binary)], check=True)
                subprocess.run([str(binary)], check=True, timeout=30, env={**os.environ, 'SDL_AUDIODRIVER': 'dummy'})
        # Authentication and bounds are checked again by the CLI, not trusted to Python.

        for key, value in [('sha256', '0'*64), ('window_size', 0x20004), ('target_pc', '80010000')]:
            changed = json.loads(json.dumps(doc))
            changed['observed_images'][0]['record'][key] = value
            loads.write_text(json.dumps(changed))
            plaid(*discover, ok=False)
        # Captures cannot discharge an unresolvable direct transfer.
        unknown = bytes.fromhex('0800200000000000')
        unclosed = dict(record, bytes=unknown.hex(), window_size=len(unknown), sha256=hashlib.sha256(unknown).hexdigest())
        doc['observed_images'][0]['record'] = unclosed
        loads.write_text(json.dumps(doc))
        plaid(*discover)
        refused = json.loads(plaid('solve', source, mapping, '--residual-dispatch'))
        assert refused['status'] == 'open' and any(b not in refused.get('trapped_sites', []) for b in refused['blockers'])
        plaid('lower-map', source, mapping, '0x80000000', '0x80000f00', c, '--residual-dispatch', ok=False)
    print('PASS observed image admission, deterministic generation, manifest, native dispatch, full-window/late mismatch, aliases, writes, generations, ROM coexistence and multipart output')


if __name__ == '__main__':
    main()
