"""Synthetic SP source-witness adversaries independent of the oracle capture."""
import copy
import unittest
from verify import verify, reject_forgeries


def fixture():
    events = []
    words = [0xac220000,0xac220000,0xa0220001,0xe4200000,0xe4210000,0xe4210000,0xe4210000]
    offsets = [0,0,0,4,8,12,0]
    payloads = [0x55667788,0x55667788,0x77880000,0x55667788,0x11223344,0xddeeff00]

    def effect(phase, context, word, address, offset, value):
        return dict(kind=1,ordinal=len(events)+1,context=context,phase=phase,
            pc=0xffffffffa0006000 if context else 0xffffffffa0006004,word=word,
            address=address,bank=1,offset=offset,value=value,exception=0,cop_error=0,
            fr=False,cu1=False,cpu=True,gpr=[],fpr=[])

    for phase, word in enumerate(words,1):
        gpr, fpr = [0]*32, [0]*32
        gpr[1],gpr[2] = 0xffffffffa4001000+offsets[phase-1],0x1122334455667788
        if phase >= 4:
            fpr[0],fpr[1] = 0x1122334455667788,0x99aabbccddeeff00
        context = len(events)+1
        begin = dict(kind=0,ordinal=context,context=context,phase=phase,pc=0xffffffffa0006000,
            word=word,address=0,bank=0,offset=0,value=0,exception=0,cop_error=0,
            fr=phase in (6,7),cu1=phase in (4,5,6),cpu=True,gpr=gpr,fpr=fpr)
        events.append(begin)
        if phase != 7:
            address = 0x04001000+offsets[phase-1]+int(phase == 3)
            events.append(effect(phase,context,word,address,offsets[phase-1],payloads[phase-1]))
        end = copy.deepcopy(begin)
        end.update(kind=2,ordinal=len(events)+1,exception=11 if phase == 7 else 0,
            cop_error=int(phase == 7))
        events.append(end)
        if phase == 2:
            events.append(effect(0,0,0,0x04001000,0,0x55667788))
    return dict(initial_imem=list(range(0xa0,0xb0)), events=events,
        checkpoints=['synthetic independent fixture state']*8,
        final_imem=list(bytes.fromhex('778800005566778811223344ddeeff00')))


class ProducerContract(unittest.TestCase):
    def test_six_producers_and_one_unknown_effect(self):
        result = verify(fixture())
        self.assertEqual(len(result['witnesses']),6)
        self.assertEqual(result['unknown_effect_ordinals'],[7])
        self.assertEqual(result['fault_without_sink'],1)

    def test_same_value_has_distinct_actual_instruction_contexts(self):
        witnesses = verify(fixture())['witnesses']
        self.assertEqual(witnesses[0]['payload'],witnesses[1]['payload'])
        self.assertNotEqual(witnesses[0]['context'],witnesses[1]['context'])

    def test_subword_source_is_replayed_as_the_pinned_full_word_sink(self):
        witness = verify(fixture())['witnesses'][2]
        self.assertEqual((witness['physical'],witness['payload']),(0x04001001,0x77880000))

    def test_fr_sensitive_source_register_and_half(self):
        witnesses = verify(fixture())['witnesses']
        self.assertEqual((witnesses[4]['operand']['register'],witnesses[4]['operand']['shift']),(0,32))
        self.assertEqual((witnesses[5]['operand']['register'],witnesses[5]['operand']['shift']),(1,0))

    def test_original_and_additional_measured_history_forgeries_are_rejected(self):
        self.assertEqual(reject_forgeries(fixture()),16)

    def test_fault_cannot_manufacture_a_sink(self):
        data = fixture()
        effect = copy.deepcopy(next(e for e in data['events'] if e['kind'] == 1))
        effect.update(ordinal=21,context=20,phase=7,word=0xe4210000)
        data['events'][-1]['ordinal'] = 22
        data['events'].insert(-1,effect)
        with self.assertRaises(AssertionError):
            verify(data)

    def test_boolean_byte_is_not_a_typed_final_snapshot(self):
        data = fixture()
        data['final_imem'][2] = False
        with self.assertRaises(AssertionError):
            verify(data)

    def test_host_storage_order_cannot_be_labeled_as_guest_initial_bytes(self):
        data = fixture()
        data['initial_imem'] = [value for offset in range(0,16,4)
            for value in reversed(data['initial_imem'][offset:offset+4])]
        with self.assertRaises(AssertionError):
            verify(data)


if __name__ == '__main__':
    unittest.main()
