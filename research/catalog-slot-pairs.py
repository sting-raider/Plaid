"""ROM-only experiment: recover constant-initialized 1172 pair catalogs.

No title IDs, ROM offsets, guest loader addresses or captured RAM inputs.
This is research evidence, not authority to exclude executable targets.
Usage: python research/catalog-slot-pairs.py ROM BOOT_OFFSET BOOT_SIZE
       python research/catalog-slot-pairs.py --test
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

LIMIT = 8 * 1024 * 1024


def stream(rom, at):
    if rom[at:at + 2] != b'\x11\x72' or at + 6 > len(rom):
        raise ValueError('not a 1172 stream')
    size = int.from_bytes(rom[at + 2:at + 6], 'big')
    if not 0 < size <= LIMIT:
        raise ValueError('decoded size outside image bound')
    decoder = zlib.decompressobj(-15)
    # Limit input as well as output; reject truncated and excessive streams.
    source = rom[at + 6:at + 6 + LIMIT]
    try:
        data = decoder.decompress(source, size + 1)
    except zlib.error as error:
        raise ValueError('invalid raw DEFLATE') from error
    if not decoder.eof or len(data) != size:
        raise ValueError('truncated stream or decoded size mismatch')
    return data, at + 6 + len(source) - len(decoder.unused_data)


def pair(rom, start, end):
    if not 0 <= start < end <= len(rom):
        raise ValueError('pair outside ROM')
    text, middle = stream(rom[:end], start)
    data, consumed = stream(rom[:end], middle)
    if consumed > end or end - consumed >= 16:
        raise ValueError('pair does not end at next aligned file boundary')
    if len(text) % 16 or len(data) % 16 or len(text) + len(data) > LIMIT:
        raise ValueError('unaligned or oversized executable pair')
    return text, data


def constants_and_stores(boot):
    """Only straight-line LUI/ADDIU/ORI/SW constant construction, fail closed.

    A JR's delay slot belongs to its block. Unknown instructions end the
    candidate; no control-flow merge, memory read or guest execution is used.
    """
    registers = {0: 0}
    stores, blocks, constants = {}, [], set()
    delay = False

    def finish():
        if stores:
            blocks.append(dict(stores))
        stores.clear()
        registers.clear()
        registers[0] = 0

    for at in range(0, len(boot) - 3, 4):
        w = int.from_bytes(boot[at:at + 4], 'big')
        op, rs, rt = w >> 26, w >> 21 & 31, w >> 16 & 31
        imm = w & 0xffff
        signed = imm if imm < 0x8000 else imm - 0x10000
        was_delay = delay
        delay = False
        if w == 0:
            pass
        elif op == 15 and rs == 0:
            registers[rt] = imm << 16
        elif op in (9, 13) and rs in registers:
            registers[rt] = ((registers[rs] + signed) if op == 9 else
                             (registers[rs] | imm)) & 0xffffffff
        elif op == 43 and rs in registers and rt in registers:
            destination = (registers[rs] + signed) & 0xffffffff
            if destination in stores and stores[destination] != registers[rt]:
                value = registers[rt]
                finish()
                blocks.append({destination: value})
            else:
                stores[destination] = registers[rt]
        elif op == 0 and w & 63 == 8:
            delay = True
        else:
            finish()
        registers[0] = 0
        constants.update(registers.values())
        if was_delay:
            finish()
    finish()
    return constants, blocks


def catalogs(rom, blocks):
    found = {}
    values, conflicts = {}, set()
    for stores in blocks:
        for address, value in stores.items():
            if address in values and values[address] != value:
                conflicts.add(address)
            values[address] = value
    for stores in blocks:
        addresses = sorted(stores)
        for lo in addresses:
            if lo % 4 or lo - 4 in stores:
                continue
            rows, at = [], lo
            while at in stores and at + 4 in stores:
                start, end = stores[at], stores[at + 4]
                try:
                    text, data = pair(rom, start, end)
                except ValueError:
                    break
                rows.append((start, end, text, data))
                at += 8
            if (len(rows) >= 3 and at not in stores and at + 4 not in stores
                    and not any(lo <= address < at for address in conflicts)):
                found[lo] = rows
    return found


def segment_record(image, at):
    if at < 0 or at + 44 > len(image):
        return False
    r = struct.unpack_from('>11I', image, at)
    _, start, end, _, _, ts, te, ds, de, bs, be = r
    return (0x80000000 <= start < end <= 0x80800000 and
            (not any(r[5:]) or start == ts < te == ds <= de == bs <= be == end))


def metadata(images, rows):
    matches = []
    for source, image in images.items():
        for at in range(0, len(image) - 44 * len(rows) + 1, 4):
            entries = []
            for index, (_, _, text, data) in enumerate(rows):
                r = struct.unpack_from('>11I', image, at + 44 * index)
                _, start, end, _, _, ts, te, ds, de, bs, be = r
                # The empty loader entry has no executable segment metadata.
                if not any(r[5:]):
                    if not (0x80000000 <= start < end <= 0x80800000 and len(text) + len(data) <= 64):
                        break
                    entries.append(None)
                    continue
                if not (0x80000000 <= start == ts < te == ds <= de == bs <= be == end <= 0x80800000
                        and te - ts == len(text) and de - ds == len(data)):
                    break
                entries.append(dict(index=index, destination=start, text=len(text),
                                    data=len(data), bss=be - bs))
            else:
                if sum(e is not None for e in entries) >= 3:
                    if segment_record(image, at - 44) or segment_record(image, at + 44 * len(rows)):
                        continue
                    matches.append(dict(container=source, offset=at, entries=entries))
    return matches


def analyze(rom, boot):
    constants, blocks = constants_and_stores(boot)
    tables = catalogs(rom, blocks)
    # Only ROM streams named by boot constants are metadata candidates.
    images = {}
    for start in sorted(constants):
        if rom[start:start + 2] != b'\x11\x72':
            continue
        try:
            text, middle = stream(rom, start)
            data, _ = stream(rom, middle)
            images[start] = text + data
        except ValueError:
            continue
    results = []
    for address, rows in tables.items():
        matches = metadata(images, rows)
        if len(matches) != 1:
            continue
        match = matches[0]
        entries = []
        for index, (start, end, text, data) in enumerate(rows):
            entry = dict(index=index, rom=start, rom_end=end, text=len(text),
                         data=len(data), sha256=hashlib.sha256(text + data).hexdigest())
            if match['entries'][index]:
                entry.update(match['entries'][index])
            entries.append(entry)
        results.append(dict(source_table=address, metadata_container=match['container'],
                            metadata_offset=match['offset'], entries=entries))
    return dict(format='plaid-paired-stream-catalog-experiment-v1',
                rom_sha256=hashlib.sha256(rom).hexdigest(), catalogs=results)


def encoded(data):
    compressor = zlib.compressobj(wbits=-15)
    return b'\x11\x72' + len(data).to_bytes(4, 'big') + compressor.compress(data) + compressor.flush()


class Contracts(unittest.TestCase):
    def test_stream_boundaries_and_refusals(self):
        a, b = bytes(range(32)), b'data' * 8
        raw = encoded(a) + encoded(b)
        self.assertEqual(pair(raw, 0, len(raw)), (a, b))
        for bad in (raw[:-1], raw + bytes(16), b'xx' + raw[2:], raw[:5]):
            with self.assertRaises(ValueError):
                pair(bad, 0, len(bad))
        for size in (0, LIMIT + 1, 31, 33):
            with self.assertRaises(ValueError):
                stream(raw[:2] + size.to_bytes(4, 'big') + raw[6:], 0)

    def test_constant_stores_and_delay_slot(self):
        words = [0x3c088040, 0x2508fe10, 0x3c0900fd, 0x25299ef0,
                 0xad090000, 0x03e00008, 0xad090004]
        _, blocks = constants_and_stores(b''.join(w.to_bytes(4, 'big') for w in words))
        self.assertEqual(blocks, [{0x803ffe10: 0xfc9ef0, 0x803ffe14: 0xfc9ef0}])
        words.insert(4, 0x8d290000)  # Unknown LW destroys the claimed constant.
        _, blocks = constants_and_stores(b''.join(w.to_bytes(4, 'big') for w in words))
        self.assertEqual(blocks, [])

    def test_metadata_identity_and_sizes(self):
        rows = [(0, 0, bytes(32), bytes(16))] * 3
        records = b''.join(struct.pack('>11I', 0, 0x80001000, 0x80001040,
                                      0, 0, 0x80001000, 0x80001020,
                                      0x80001020, 0x80001030, 0x80001030,
                                      0x80001040) for _ in rows)
        self.assertEqual(len(metadata({99: records}, rows)), 1)
        changed = bytearray(records)
        changed[27] ^= 4  # Alter text end without changing the stream.
        self.assertEqual(metadata({99: changed}, rows), [])
        self.assertEqual(metadata({99: bytes(44 * 3)}, rows), [])

    def test_metadata_refuses_partial_segment_tables(self):
        row = struct.pack('>11I', 0, 0x80001000, 0x80001040, 0, 0,
                          0x80001000, 0x80001020, 0x80001020, 0x80001030,
                          0x80001030, 0x80001040)
        rows = [(0, 0, bytes(32), bytes(16))] * 4
        self.assertEqual(len(metadata({99: row * 4}, rows)), 1)
        self.assertEqual(metadata({99: row * 4}, rows[:3]), [])

    def test_catalog_initializers_must_agree(self):
        rom = bytearray(1024)
        stores = {}
        for i in range(3):
            source = 0x100 + i * 0x100
            data = encoded(bytes([i]) * 32) + encoded(bytes(16))
            rom[source:source + len(data)] = data
            stores[0x80001000 + 8 * i] = source
            stores[0x80001004 + 8 * i] = source + len(data)
        self.assertEqual(len(catalogs(rom, [stores, stores])), 1)
        self.assertEqual(catalogs(rom, [stores, {0x80001000: 0xffffff}]), {})
        words = [0x3c088000, 0x35081000, 0x34090100, 0xad090000,
                 0x34090200, 0xad090000, 0x03e00008, 0]
        _, blocks = constants_and_stores(b''.join(w.to_bytes(4, 'big') for w in words))
        self.assertEqual(blocks, [{0x80001000: 0x100}, {0x80001000: 0x200}])


if __name__ == '__main__':
    if sys.argv[1:] == ['--test']:
        unittest.main(argv=[sys.argv[0]])
    else:
        path, offset, size = sys.argv[1:]
        rom = Path(path).read_bytes()
        start, length = int(offset, 0), int(size, 0)
        print(json.dumps(analyze(rom, rom[start:start + length]), indent=2))
