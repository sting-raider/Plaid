"""Independent captured-history controls for the three-instruction contract."""
from pathlib import Path
import copy
import importlib.util
import unittest
from verify import replay, shared

spec = importlib.util.spec_from_file_location('copy_test_fixture',
    Path(__file__).resolve().parents[1]/'044-ares-cpu-copy-dataflow/test_verify.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def triple(mask=0xff, source_register=8):
    data = fixture.pair()
    instructions = data['instruction_events']
    before = list(instructions[1]['gpr'])
    # Equal-value t1 is a deliberate competing register definition.
    for event in instructions:
        event['gpr'][9] = before[8]
    before[9] = before[8]
    after = list(before)
    after[8] = before[source_register] ^ mask
    word = 0x0e << 26 | source_register << 21 | 8 << 16 | mask
    transform = [dict(ordinal=4, context=4, phase=1, pc=0xffffffff80006004,
        word=word, begin=True, gpr=before),
        dict(ordinal=5, context=4, phase=1, pc=0xffffffff80006004,
        word=word, begin=False, gpr=after)]
    for index, event in enumerate(instructions[2:]):
        event.update(ordinal=6 if index == 0 else 8, context=6, pc=0xffffffff80006008, gpr=list(after))
    instructions[2:2] = transform
    data['scalar_events'][1].update(ordinal=7, context=6, pc=0xffffffff80006008, value=after[8] & 0xffffffff)
    return data


class TransformContract(unittest.TestCase):
    def test_big_endian_byte_masks(self):
        certificate = replay(triple(0xf00f))[1][0]
        self.assertEqual([b['xor'] for b in certificate['byte_expr']], [0, 0, 0xf0, 0x0f])

    def test_zero_transform_retains_distinct_context(self):
        certificate = replay(triple(0))[1][0]
        self.assertEqual(certificate['source_word'], certificate['result_word'])
        self.assertEqual(len({certificate[k] for k in ('load_context', 'transform_context', 'store_context')}), 3)

    def test_equal_register_value_is_not_the_loaded_definition(self):
        self.assertEqual(replay(triple(source_register=9))[1], [])

    def test_copy_mode_does_not_silently_admit_transforms(self):
        with self.assertRaises(AssertionError):
            shared.replay(triple())

    def test_transform_pc_gap_is_rejected(self):
        data = triple()
        for event in data['instruction_events'][2:4]:
            event['pc'] += 0x100
        with self.assertRaises(AssertionError):
            replay(data)

    def test_equal_low_word_does_not_hide_a_generation_discontinuity(self):
        data = copy.deepcopy(triple())
        for event in data['instruction_events'][2:]:
            event['gpr'][8] ^= 1 << 32
        with self.assertRaises(AssertionError):
            replay(data)

    def test_abstract_low_word_xor_cannot_supply_an_oversized_instruction(self):
        # The harvested cache model accepts imm += 2**32 after truncation.
        # Actual captured XORI evidence must be a decoded 32-bit word/u16 operand.
        with self.assertRaises(AssertionError):
            replay(triple(0xff | 1 << 32))


if __name__ == '__main__':
    unittest.main()
