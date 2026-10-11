import unittest
from verify import verify,expected_facts,NEW


class VisibilityTests(unittest.TestCase):
    def test_four_reported_controls_do_not_certify_provenance(self):
        result=verify(expected_facts())
        self.assertEqual(result['scenarios'],4)
        self.assertFalse(result['producer_ancestry_certified'])
        self.assertFalse(result['native_complete'])

    def test_store_and_writeback_do_not_refresh_old_icache(self):
        for field in ('normal_after_store','normal_after_writeback','foreign_after_store'):
            facts=expected_facts();facts[field]=2
            with self.assertRaises(AssertionError):
                verify(facts)

    def test_early_refill_cannot_inherit_later_backing(self):
        for field,value in (('prefill_final',2),('prefill_icache',NEW)):
            facts=expected_facts();facts[field]=value
            with self.assertRaises(AssertionError):
                verify(facts)

    def test_bool_and_extra_certificate_fields_rejected(self):
        for field,value in (('normal_after_store',True),('native_complete',True),('exception',False)):
            facts=expected_facts();facts[field]=value
            with self.assertRaises(AssertionError):
                verify(facts)


if __name__=='__main__':
    unittest.main()
