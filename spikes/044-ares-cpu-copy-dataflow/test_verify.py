"""Synthetic contract regressions independent of the captured oracle artifact."""
import copy
import unittest
from verify import replay


def pair(unsigned=False, zero=False):
    before = [0]*32
    before[16], before[17] = 0xffffffffa0001000, 0xffffffffa0002000
    register = 0 if zero else 8
    after = list(before)
    if register:
        after[register] = 0x89abcdef if unsigned else 0xffffffff89abcdef
    load = (0x27 if unsigned else 0x23) << 26 | 16 << 21 | register << 16
    store = 0x2b << 26 | 17 << 21 | register << 16
    instructions = []
    for ordinal, context, begin, pc, word, registers in (
            (1, 1, True, 0xffffffff80006000, load, before),
            (3, 1, False, 0xffffffff80006000, load, after),
            (4, 4, True, 0xffffffff80006004, store, after),
            (6, 4, False, 0xffffffff80006004, store, after)):
        instructions.append(dict(ordinal=ordinal, context=context, begin=begin,
            phase=1, pc=pc, word=word, gpr=list(registers)))
    scalars = [dict(ordinal=2, context=1, phase=1, pc=0xffffffff80006000,
        write=False, address=0x1000, bytes=4, uncached_cpu=True, value=0x89abcdef),
        dict(ordinal=5, context=4, phase=1, pc=0xffffffff80006004,
        write=True, address=0x2000, bytes=4, uncached_cpu=True, value=0 if zero else 0x89abcdef)]
    return dict(instruction_events=instructions, scalar_events=scalars)


class CopyContract(unittest.TestCase):
    def test_signed_and_unsigned_architectural_results(self):
        for unsigned in (False, True):
            certificates = replay(pair(unsigned=unsigned))[1]
            self.assertEqual(len(certificates), 1)
            self.assertEqual(certificates[0]['load_opcode'], 'LWU' if unsigned else 'LW')

    def test_zero_load_does_not_define_a_causal_writer(self):
        self.assertEqual(replay(pair(zero=True))[1], [])

    def test_equal_store_bits_do_not_hide_a_register_discontinuity(self):
        forged = pair()
        for event in forged['instruction_events'][2:]:
            event['gpr'][8] ^= 1 << 32
        with self.assertRaises(AssertionError):
            replay(forged)

    def test_matching_effect_pc_does_not_make_a_nonadjacent_instruction_adjacent(self):
        forged = pair()
        for event in forged['instruction_events'][2:] + forged['scalar_events'][1:]:
            event['pc'] += 0x100
        with self.assertRaises(AssertionError):
            replay(forged)

    def test_physical_address_equality_does_not_prove_uncached_access(self):
        for base in (16, 17):
            forged = pair()
            for event in forged['instruction_events']:
                event['gpr'][base] -= 0x20000000
            with self.assertRaises(AssertionError):
                replay(forged)

    def test_zero_context_effect_cannot_be_silently_dropped(self):
        forged = pair()
        forged['scalar_events'][0]['context'] = 0
        with self.assertRaises(AssertionError):
            replay(forged)

    def test_boolean_register_and_extra_fields_are_not_typed_integer_evidence(self):
        for mutate in ('bool', 'extra'):
            forged = copy.deepcopy(pair())
            if mutate == 'bool':
                forged['instruction_events'][0]['gpr'][0] = False
            else:
                forged['scalar_events'][0]['unclaimed'] = 0
            with self.assertRaises(AssertionError):
                replay(forged)


if __name__ == '__main__':
    unittest.main()
