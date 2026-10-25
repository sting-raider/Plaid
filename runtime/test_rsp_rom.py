"""Synthetic ROM discovery and fail-before-side-effects RSP task contracts."""
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor
import subprocess
from pathlib import Path


def run(exe, cc, T):
    A, V, out = T.A, T.V, T.OUT
    # Straight-line boot loads data, then text. The task's advertised text size
    # deliberately understates its DMA size, as real SDK tasks can do.
    boot = [A.addiu(A.at, A.zero, 0xFC0), A.lw(A.t0, 0x18, A.at), A.lw(A.t1, 0x1C, A.at),
            A.addiu(A.t1, A.t1, -1), V.mtc0(A.zero, 0), V.mtc0(A.t0, 1), V.mtc0(A.t1, 2),
            A.lw(A.t0, 0x10, A.at), A.addiu(A.t1, A.zero, 0x7F), A.addiu(A.t2, A.zero, 0x1080),
            V.mtc0(A.t2, 0), V.mtc0(A.t0, 1), V.mtc0(A.t1, 2), A.jr(A.t2), A.nop]
    boot_words = T.rsp_words(boot, 0)
    def task_program(boot_address):
        task = [2, 0, boot_address, len(boot_words) * 4, T.UCODE, 16, T.UDATA, 32, 0, 0, T.OUTB, 0, 0, 0, 0, 0]
        program = [*T.li(A.sp, 0x80007F00),
                   *[w for i, v in enumerate(boot_words) for w in T.poke(boot_address + i * 4, v)],
                   *[w for i, v in enumerate(T.UCODE_WORDS) for w in T.poke(T.UCODE + i * 4, v)],
                   *[w for i, v in enumerate(T.UDATA_WORDS) for w in T.poke(T.UDATA + i * 4, v)],
                   *[w for i, v in enumerate(task) for w in T.poke(T.RTASK + i * 4, v)],
                   'before_load', *T.call('osSpTaskLoad', T.RTASK), 'before_start', *T.call('osSpTaskStartGo', T.RTASK), *A.DONE]
        for name in runtime:
            program += [name, A.jr(A.ra), A.nop]
        return program
    runtime = ['osSpTaskLoad', 'osSpTaskStartGo']
    program = task_program(T.BOOT)
    # ROM contains both CPU code and separately addressed microcode bytes.
    raw = bytearray(0x10000)
    cpu = A.assemble(program)
    raw[:len(cpu)] = cpu
    for addr, words in [(T.BOOT, boot_words), (T.UCODE, T.UCODE_WORDS)]:
        start = addr - A.BASE
        raw[start:start + len(words) * 4] = b''.join(w.to_bytes(4, 'big') for w in words)
    rom = bytearray(0x1000) + raw
    rom[:4] = bytes.fromhex('80371240')
    rom_path, map_path, texts = out / 'rsp-rom.z64', out / 'rsp-rom-map.json', out / 'rsp-rom-texts'
    rom_path.write_bytes(rom)
    labels = A.label_pcs(program)
    decl = out / 'rsp-rom.runtime.json'
    decl.write_text(json.dumps(dict(format='plaid-runtime-functions-v0', source='synthetic',
                                   functions=[dict(entry=hex(labels[n]), name=n, callbacks=[]) for n in runtime])))
    subprocess.run([str(exe), 'discover', str(rom_path), '0x1000', hex(A.BASE), hex(len(raw)), hex(A.BASE),
                    str(map_path), str(decl)], check=True, capture_output=True)
    subprocess.run([str(exe), 'rsp-from-rom', str(rom_path), str(map_path), str(texts)], check=True)
    manifest = json.loads((texts / 'rsp-files.json').read_text())
    assert manifest['rom_sha256'] == hashlib.sha256(rom).hexdigest()
    assert {T.BOOT, T.UCODE} <= {t['guest_address'] for t in manifest['texts']}
    # Packed halfword tables also name nonstandard IMEM placements. Exercise
    # the actual ROM discovery -> DMA -> guarded native entry boundary.
    packed_raw = bytearray(rom)
    overlay = T.rsp_words([V.mfc0(A.t0, 6), V.mtc0(A.zero, 7),
                           A.ori(A.t1, A.zero, 0x789A), A.sw(A.t1, 0x200, A.zero), V.BREAK], 0xE00)
    overlay += [0] * (16 - len(overlay))
    loader_code = [A.ori(A.at, A.zero, 0xFC0), A.lhu(A.a1, 0x78, A.zero),
                   A.lhu(A.a0, 0x42, A.a1), A.srl(A.v1, A.a0, 12),
                   A.lhu(A.v0, 0x44, A.a1), A.lw(A.t0, 0x10, A.at),
                   A.andi(A.a0, A.a0, 0xFFF), A.addu(A.v0, A.v0, A.t0),
                   A.jal('packed_dma'), A.lhu(A.v1, 0x40, A.v1), A.jr(A.v1), A.nop]
    loader_code += [A.nop] * (16 - len(loader_code))
    loader_code += ['packed_dma', V.mtc0(A.v1, 0), V.mtc0(A.v0, 1), V.mtc0(A.a0, 2), A.jr(A.ra), A.nop]
    loader = T.rsp_words(loader_code, 0x80)
    # A valid short DMA record is not a terminator. Its placed resident path
    # must pass content filtering alongside the following full overlay.
    table = [0x1E00003F, 0x0300002B, 0x0280003F, 0x03800000]
    later = overlay.copy()
    later[2] = A.ori(A.t1, A.zero, 0x789B)
    # This short scalar trampoline reaches the resident DMA helper, then
    # returns to its own continuation. No RSP-specific opcode is in the span.
    short = T.rsp_words([A.ori(A.a0, A.zero, 7), A.ori(A.v0, A.zero, T.UDATA & 0xffff),
                         A.ori(A.v1, A.zero, 0x400), 2 << 26 | 0xC0 >> 2,
                         A.ori(A.ra, A.zero, 0xE20), 0, 0, 0,
                         A.ori(A.t1, A.zero, 0x6543), A.sw(A.t1, 0x200, A.zero), V.BREAK, 0], 0xE00)
    patches = [(T.UCODE, loader), (T.UCODE + 0x280, short),
               (T.UCODE + 0x300, overlay), (T.UCODE + 0x380, later),
               (T.UDATA + 0x40, table), (T.UDATA + 0x78, [0])]
    for address, words in patches:
        at = 0x1000 + address - A.BASE
        packed_raw[at:at + len(words) * 4] = b''.join(w.to_bytes(4, 'big') for w in words)
    packed_rom = out / 'rsp-rom-packed.z64'
    packed_rom.write_bytes(packed_raw)
    packed_texts = out / 'rsp-rom-packed-texts'
    packed_map = out / 'rsp-rom-packed-map.json'
    subprocess.run([str(exe), 'discover', str(packed_rom), '0x1000', hex(A.BASE), hex(len(raw)), hex(A.BASE),
                    str(packed_map), str(decl)], check=True, capture_output=True)
    subprocess.run([str(exe), 'rsp-from-rom', str(packed_rom), str(packed_map), str(packed_texts)], check=True)
    pm = json.loads((packed_texts / 'rsp-files.json').read_text())
    assert any(t['guest_address'] == T.UCODE + 0x300 and t['imem'] == 0xE00 and t['size'] == 64
               for t in pm['texts']), pm
    assert any(t['guest_address'] == T.UCODE + 0x380 and t['imem'] == 0xE00 and t['size'] == 64
               for t in pm['texts']), pm
    assert any(t['guest_address'] == T.UCODE + 0x280 and t['imem'] == 0xE00 and t['size'] == 48
               for t in pm['texts']), pm
    files = [str(texts / (t['name'] + '.c')) for t in manifest['texts']] + [str(texts / 'rsp_registry.c')]
    def compile_text(source):
        obj = source + '.o'
        subprocess.run([cc, '-O1', '-I', str(T.ROOT / 'crates/plaid-lower/src'), '-c', source, '-o', obj], check=True)
        return obj
    with ThreadPoolExecutor(min(8, os.cpu_count() or 1)) as pool:
        objects = list(pool.map(compile_text, files))
    packed_files = [str(packed_texts / (t['name'] + '.c')) for t in pm['texts']] + [str(packed_texts / 'rsp_registry.c')]
    with ThreadPoolExecutor(min(8, os.cpu_count() or 1)) as pool:
        packed_objects = list(pool.map(compile_text, packed_files))
    for selector, corrupt in ((0, False), (4, False), (0, True)):
        variant = program.copy()
        at = variant.index('before_load')
        edits = [*T.poke(T.RTASK + 0x1C, 0x80),
                 *[w for address, words in patches for i, v in enumerate(words) for w in T.poke(address + i * 4, v)]]
        edits += T.poke(T.UDATA + 0x78, selector << 16)
        if corrupt:
            edits += T.poke(T.UCODE + 0x300, 0xFFFFFFFF)
        variant[at:at] = edits
        at = variant.index('before_start') + 1 + len(T.call('osSpTaskStartGo', T.RTASK))
        variant[at:at] = T.log_word(0xA4000200) + T.log_word(0xA4000400)
        packed_native = T.build(exe, cc, f'rsp-rom-packed-{selector}-{int(corrupt)}', variant, runtime,
                                ['-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', str(T.ROOT / 'crates/plaid-lower/src'),
                                 *packed_objects])
        result = subprocess.run([str(packed_native), '--dump', hex(T.LOG), '2'], capture_output=True, text=True, timeout=30)
        if corrupt:
            assert result.returncode == 1 and 'unlowered RSP code' in result.stdout, (result.stdout, result.stderr)
            assert 'IMEM e00' in result.stderr, result.stderr
        else:
            rows = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
            words = next(row['words'] for row in rows if 'words' in row)
            assert result.returncode == 0 and words[0] == (0x6543 if selector else 0x789A), (result.stdout, result.stderr)
            if selector:
                assert words[1] == T.UDATA_WORDS[0], words
    flags = ['-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', str(T.ROOT / 'crates/plaid-lower/src'), *objects]
    native = T.build(exe, cc, 'rsp-rom', program, runtime, flags)
    for mutation in [None, 'boot', 'text', 'reachable', 'tail', 'pointer']:
        variant = program.copy()
        if mutation:
            before_start = variant.index('before_load' if mutation in ('boot', 'pointer') else 'before_start')
            address = dict(boot=T.BOOT, text=T.UCODE, reachable=T.UCODE + 0x40,
                           tail=T.UCODE + 0x7C, pointer=T.RTASK + 0x10)[mutation]
            variant[before_start:before_start] = T.poke(address, 0x807FFFF8 if mutation == 'pointer' else 0x12345678)
            native = T.build(exe, cc, 'rsp-rom-' + mutation, variant, runtime, flags)
        result = subprocess.run([str(native), '--dump', hex(T.OUTB), '2'], capture_output=True, text=True, timeout=30)
        lines = {k: v for line in result.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        if mutation and mutation != 'tail':
            assert result.returncode == 1 and lines['stop'] == 'unknown or ambiguous ROM-derived RSP microcode', (mutation, result.stdout, result.stderr)
            assert lines['words'] == [0, 0], (mutation, lines)
        else:
            assert result.returncode == 0 and lines['words'] == [0x12131415, T.OUTB & 0x1FFFFFFF], (result.stdout, result.stderr)
    # A boot the ROM supplies only by PI DMA into RAM outside every image is
    # selected from its recorded source (ADR-0225) and refused without it.
    dma_boot = A.BASE + len(raw) + 0x1000
    sourced_program = task_program(dma_boot)
    sourced = bytearray(rom)
    sourced_cpu = A.assemble(sourced_program)
    sourced[0x1000:0x1000 + len(sourced_cpu)] = sourced_cpu
    start = 0x1000 + T.BOOT - A.BASE
    sourced[start:start + len(boot_words) * 4] = bytes(len(boot_words) * 4)
    dma_rom = len(sourced)
    sourced += b''.join(w.to_bytes(4, 'big') for w in boot_words).ljust(128, bytes(1))
    unnamed_boot = dma_boot + 0x1000
    unnamed_rom = len(sourced)
    sourced += (unnamed_boot + 8).to_bytes(4, 'big') + bytes(4) + sourced[dma_rom:dma_rom + 128]
    sourced_rom, sourced_map = out / 'rsp-rom-sourced.z64', out / 'rsp-rom-sourced-map.json'
    sourced_rom.write_bytes(sourced)
    sourced_loads = out / 'rsp-rom-sourced-loads.json'
    sourced_loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='synthetic', loads=[],
                                             rsp_sources=[dict(destination=hex(dma_boot), size='0x80', rom=hex(dma_rom))])))
    subprocess.run([str(exe), 'discover', str(sourced_rom), '0x1000', hex(A.BASE), hex(len(raw)), hex(A.BASE),
                    str(sourced_map), str(decl)], check=True, capture_output=True)
    # Only externally named starts are roots; malformed source ranges fail early.
    source = dict(destination=hex(dma_boot), size='0x80', rom=hex(dma_rom))
    for changes in (dict(destination=hex(unnamed_boot), rom=hex(unnamed_rom), size='0x88'), dict(size='0x0'),
                    dict(destination='0x807ffff8', size='0x40'), dict(rom=hex(len(sourced)))):
        sourced_loads.write_text(json.dumps(dict(rsp_sources=[source | changes])))
        result = subprocess.run([str(exe), 'rsp-from-rom', str(sourced_rom), str(sourced_map),
                                 str(out / 'rsp-rom-source-invalid'), '--loads', str(sourced_loads)],
                                capture_output=True, text=True)
        if changes.get('destination') == hex(unnamed_boot):
            assert result.returncode == 0, result.stderr
            m = json.loads((out / 'rsp-rom-source-invalid/rsp-files.json').read_text())
            assert not any(t['source_kind'] == 'pi_dma' for t in m['texts']), m
        else:
            assert result.returncode != 0, changes
    sourced_loads.write_text(json.dumps(dict(rsp_sources=[source])))
    for with_source in (True, False):
        sourced_texts = out / f'rsp-rom-sourced-texts-{int(with_source)}'
        command = [str(exe), 'rsp-from-rom', str(sourced_rom), str(sourced_map), str(sourced_texts)]
        subprocess.run(command + (['--loads', str(sourced_loads)] if with_source else []), check=True)
        sm = json.loads((sourced_texts / 'rsp-files.json').read_text())
        dma_texts = [t for t in sm['texts'] if t['source_kind'] == 'pi_dma']
        assert [(t['guest_address'], t['imem'], t['size']) for t in dma_texts] == ([(dma_boot, 0, 128)] if with_source else []), dma_texts
        sources = [str(sourced_texts / (t['name'] + '.c')) for t in sm['texts']] + [str(sourced_texts / 'rsp_registry.c')]
        with ThreadPoolExecutor(min(8, os.cpu_count() or 1)) as pool:
            sourced_objects = list(pool.map(compile_text, sources))
        sourced_flags = ['-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', str(T.ROOT / 'crates/plaid-lower/src'), *sourced_objects]
        native = T.build(exe, cc, f'rsp-rom-sourced-{int(with_source)}', sourced_program, runtime, sourced_flags)
        result = subprocess.run([str(native), '--dump', hex(T.OUTB), '2'], capture_output=True, text=True, timeout=30)
        lines = {k: v for line in result.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        if with_source:
            assert result.returncode == 0 and lines['words'] == [0x12131415, T.OUTB & 0x1FFFFFFF], (result.stdout, result.stderr)
        else:
            assert result.returncode == 1 and lines['stop'] == 'unknown or ambiguous ROM-derived RSP microcode', result.stdout
            assert lines['words'] == [0, 0], lines
    # Direct task submission: no recognized rspboot, and no separate text DMA.
    # This program's relative branch works at either IMEM placement. DMEM data
    # start at zero because no boot program loads ucode_data in this variant.
    for mutation in [None, 'text', 'tail']:
        variant = program.copy()
        before_load = variant.index('before_load')
        edits = [*T.poke(T.RTASK + 8, T.UCODE), *T.poke(T.RTASK + 12, 0x80)]
        if mutation:
            edits += T.poke(T.UCODE + (0 if mutation == 'text' else 0x7C), 0x12345678)
        variant[before_load:before_load] = edits
        native = T.build(exe, cc, 'rsp-rom-direct-' + str(mutation), variant, runtime, flags)
        result = subprocess.run([str(native), '--dump', hex(T.OUTB), '2'], capture_output=True, text=True, timeout=30)
        lines = {k: v for line in result.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        if mutation == 'text':
            assert result.returncode == 1 and lines['stop'] == 'unknown or ambiguous ROM-derived RSP microcode', (result.stdout, result.stderr)
            assert lines['words'] == [0, 0], lines
        else:
            assert result.returncode == 0 and lines['words'] == [0x11111111, T.OUTB & 0x1FFFFFFF], (result.stdout, result.stderr)
    # Direct task with LH-from-DMEM/JR dispatch. Only the entry and delay slot
    # belong to the startup mask. Exercise both a target and its fallthrough.
    dispatch = T.rsp_words([V.mfc0(A.t0, 6), V.mfc0(A.t2, 5), A.lh(A.t1, 0xFD6, A.zero),
                            A.jr(A.t1), A.nop], 0)
    dispatch += [0] * (0x40 // 4 - len(dispatch)) + [A.nop, V.BREAK]
    dispatch += [0] * (0x80 // 4 - len(dispatch))
    raw_dispatch = bytearray(rom)
    offset = 0x1000 + T.UCODE - A.BASE
    raw_dispatch[offset:offset + 0x80] = b''.join(w.to_bytes(4, 'big') for w in dispatch)
    dispatch_rom = out / 'rsp-rom-dispatch.z64'
    dispatch_rom.write_bytes(raw_dispatch)
    dispatch_map_path = out / 'rsp-rom-dispatch-map.json'
    subprocess.run([str(exe), 'discover', str(dispatch_rom), '0x1000', hex(A.BASE), hex(len(raw)), hex(A.BASE),
                    str(dispatch_map_path), str(decl)], check=True, capture_output=True)
    dispatch_texts = out / 'rsp-rom-dispatch-texts'
    subprocess.run([str(exe), 'rsp-from-rom', str(dispatch_rom), str(dispatch_map_path), str(dispatch_texts)], check=True)
    dm = json.loads((dispatch_texts / 'rsp-files.json').read_text())
    dispatch_sources = [str(dispatch_texts / (t['name'] + '.c')) for t in dm['texts']]
    dispatch_registry = str(dispatch_texts / 'rsp_registry.c')
    with ThreadPoolExecutor(min(8, os.cpu_count() or 1)) as pool:
        dispatch_objects = list(pool.map(compile_text, dispatch_sources))
    registry_object = compile_text(dispatch_registry)
    for mutation in [None, 'target', 'fallthrough', 'data', 'ambiguous']:
        variant = program.copy()
        before_load = variant.index('before_load')
        edits = [*[w for i, v in enumerate(dispatch) for w in T.poke(T.UCODE + i * 4, v)],
                 *T.poke(T.RTASK + 8, T.UCODE), *T.poke(T.RTASK + 12, 0x80), *T.poke(T.RTASK + 20, 0x40)]
        if mutation in ('target', 'fallthrough', 'data'):
            edits += T.poke(T.UCODE + dict(target=0x40, fallthrough=0x44, data=0x7C)[mutation], 0x12345678)
        variant[before_load:before_load] = edits
        active_registry = registry_object
        if mutation == 'ambiguous':
            source = Path(dispatch_registry).read_text()
            name = next(t['name'] for t in dm['texts'] if t['guest_address'] == T.UCODE and t['imem'] == 0)
            source = source.replace('plaid_rsp_texts[] = {', 'plaid_rsp_texts[] = {&plaid_rsp_text_' + name + ',')
            duplicate = out / 'rsp-rom-ambiguous-registry.c'
            duplicate.write_text(source)
            active_registry = compile_text(str(duplicate))
        dispatch_flags = ['-DPLAID_RSP', '-DPLAID_RSP_ROM', '-I', str(T.ROOT / 'crates/plaid-lower/src'),
                          *dispatch_objects, active_registry]
        native = T.build(exe, cc, 'rsp-rom-dispatch-' + str(mutation), variant, runtime, dispatch_flags)
        result = subprocess.run([str(native)], capture_output=True, text=True, timeout=30)
        lines = {k: v for line in result.stdout.splitlines() if line.startswith('{') for k, v in json.loads(line).items()}
        if mutation in ('target', 'fallthrough'):
            assert result.returncode == 1 and lines['stop'] == 'unlowered RSP code', (mutation, result.stdout, result.stderr)
            assert 'IMEM ' + ('040' if mutation == 'target' else '044') in result.stderr, result.stderr
        elif mutation == 'ambiguous':
            assert result.returncode == 1 and lines['stop'] == 'unknown or ambiguous ROM-derived RSP microcode', result.stdout
        else:
            assert result.returncode == 0, (mutation, result.stdout, result.stderr)
    import check_rsp_rom
    snaps = out / 'rsp-rom-oracle'
    snaps.mkdir(exist_ok=True)
    snapshot = bytearray(4096)
    snapshot[:len(boot_words) * 4] = b''.join(w.to_bytes(4, 'big') for w in boot_words)
    snapshot[0x80:0x80 + len(T.UCODE_WORDS) * 4] = b''.join(w.to_bytes(4, 'big') for w in T.UCODE_WORDS)
    sample = snaps / 'imem-080-synthetic.bin'
    sample.write_bytes(snapshot)
    assert check_rsp_rom.check(texts / 'rsp-files.json', snaps)['covered'] == 1
    snapshot[0x80:0x84] = bytes.fromhex('ffffffff')
    sample.write_bytes(snapshot)
    assert check_rsp_rom.check(texts / 'rsp-files.json', snaps)['covered'] == 0
    print('ROM RSP: 15 task contracts; short-overlay DMA/return; startup ambiguity/reachable corruption refuse; JR target and fallthrough mutations fault at fetch; unexecuted data accepted')
