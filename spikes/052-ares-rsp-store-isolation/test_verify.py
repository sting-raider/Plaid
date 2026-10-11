import copy
import unittest
from verify import expected, verify, reject_forgeries


class Contracts(unittest.TestCase):
    def test_pinned_report_has_no_closure_claim(self):
        result = verify(expected())
        self.assertEqual(result['probe_count'], 29)
        self.assertEqual(result['aligned_srv_changed_bytes'], 0)
        self.assertFalse(result['native_complete'])

    def test_every_probe_and_final_field_is_attacked(self):
        self.assertEqual(len(reject_forgeries(expected())), 122)

    def test_missing_probe_and_duplicate_probe_reject(self):
        for append in [False, True]:
            data = expected()
            if append:
                data['probes'].append(copy.deepcopy(data['probes'][0]))
            else:
                data['probes'].pop()
            with self.assertRaises(AssertionError):
                verify(data)

    def test_duplicate_name_cannot_stand_for_a_missing_opcode(self):
        data = expected()
        data['probes'][1]['name'] = data['probes'][0]['name']
        with self.assertRaises(AssertionError):
            verify(data)


if __name__ == '__main__':
    unittest.main()
