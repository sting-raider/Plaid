"""Copy-shaped source candidates through the public CLI, with authored code."""
import json
import struct


def run_contract(run, directory):
    base, helper, leaf, destination = 0x80000000, 0x80000100, 0x80000200, 0x80004000
    rom = bytearray(0x2400)
    rom[:4] = bytes.fromhex('80371240')
    struct.pack_into('>I', rom, 8, base)

    def instruction(op, rs, rt, immediate):
        return op << 26 | rs << 21 | rt << 16 | (immediate & 0xffff)

    def arithmetic(function, rd, rs, rt):
        return rs << 21 | rt << 16 | rd << 11 | function

    def li(register, value):
        return [instruction(15, 0, register, value >> 16),
                instruction(13, register, register, value)]

    def jal(target):
        return 3 << 26 | (target >> 2 & 0x3ffffff)

    def put(address, words):
        offset = 0x1000 + address - base
        struct.pack_into(f'>{len(words)}I', rom, offset, *words)

    put(base, [jal(base+0x40), 0, jal(base+0x80), 0, 2 << 26 | 4, 0])
    for entry, source in [(base+0x40, 0x2000), (base+0x80, 0x2100)]:
        put(entry, [*li(4, source), *li(5, source+0x100), *li(6, destination),
                    jal(helper), 0, jal(destination), 0, 0x03e00008, 0])
    put(helper, [
        arithmetic(0x21, 16, 4, 0), arithmetic(0x21, 17, 5, 0),
        arithmetic(0x21, 18, 6, 0), arithmetic(0x23, 19, 17, 16),
        arithmetic(0x21, 4, 16, 0), arithmetic(0x21, 5, 18, 0),
        instruction(9, 0, 6, 16), jal(leaf), 0,
        instruction(9, 0, 20, 16), arithmetic(0x21, 4, 16, 20),
        arithmetic(0x21, 5, 18, 20), arithmetic(0x23, 6, 19, 20),
        jal(leaf), 0, 0x03e00008, 0,
    ])
    put(leaf, [0x03e00008, 0])
    for source, value in [(0x2000, 7), (0x2100, 11)]:
        rom[source:source+0x100] = b'\xff' * 0x100
        struct.pack_into('>3I', rom, source, instruction(9, 0, 2, value), 0x03e00008, 0)
    source = directory/'copy-calls.z64'; source.write_bytes(rom)
    loads = directory/'copy-calls.loads.json'
    loads.write_text(json.dumps(dict(format='plaid-loads-v0', source='authored fixture', loads=[])))
    program = directory/'copy-calls.map.json'
    discover = ('discover', source, '0x1000', hex(base), '0x240', hex(base), program)
    run(*discover)
    # A newer fixed declaration may reserve the slot since this map was made.
    reserved = directory/'copy-calls.reserved.json'
    reserved.write_text(json.dumps(dict(format='plaid-loads-v0', source='reserved RAM', loads=[
        dict(rom='0x2200', size='0x100', destination=hex(destination), encoding='raw')
    ])))
    reserved_bytes = reserved.read_bytes()
    run('infer-call-loads', source, program, reserved)
    assert reserved.read_bytes() == reserved_bytes
    run('infer-call-loads', source, program, loads)
    doc = json.loads(loads.read_bytes())
    assert [(load['rom'], load['size'], load['destination'], load['slot'])
            for load in doc['loads']] == [('0x2000', '0x100', hex(destination), True),
                                         ('0x2100', '0x100', hex(destination), True)], doc
    unchanged = loads.read_bytes()
    run('infer-call-loads', source, program, loads)
    assert loads.read_bytes() == unchanged
    run(*discover, '--loads', loads)
    run('check-map', program)
    # Removing/changing an original source cannot reuse the older map's witness.
    doc['loads'][0]['rom'] = '0x2040'
    loads.write_text(json.dumps(doc))
    changed = loads.read_bytes()
    run('infer-call-loads', source, program, loads, ok=False)
    assert loads.read_bytes() == changed
    loads.write_bytes(unchanged)
    # Header identity is part of the source, even when instruction bytes agree.
    rom[0x20] = 1; source.write_bytes(rom)
    run('infer-call-loads', source, program, loads, ok=False)
    assert loads.read_bytes() == unchanged
    print('PASS copy-call CLI: source candidates, slot bounds, idempotence and stale/foreign source refusal')
