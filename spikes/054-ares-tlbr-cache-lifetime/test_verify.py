import unittest
from verify import expected, verify, reject_forgeries


class Contracts(unittest.TestCase):
    def test_stale_reactivation_has_open_proof_obligations(self):
        result = verify(expected())
        self.assertTrue(result['temporary_inactivity_preserves_resident'])
        self.assertFalse(result['executable_lifetime_certified'])
        self.assertFalse(result['native_complete'])
        self.assertFalse(result['successful_tlbr_writer_history_certified'])

    def test_all_report_leaves_and_structural_forgeries_reject(self):
        self.assertEqual(len(reject_forgeries(expected())), 38)

    def test_missing_miss_counter_rejects(self):
        data = expected()
        del data['misses']['fault_before']
        with self.assertRaises(AssertionError):
            verify(data)

    def test_snapshot_equality_is_not_integer_truthiness(self):
        data = expected()
        data['installed_entries_unchanged'] = 1
        with self.assertRaises(AssertionError):
            verify(data)


if __name__ == '__main__':
    unittest.main()
