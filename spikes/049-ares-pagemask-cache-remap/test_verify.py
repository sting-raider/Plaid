import unittest
from verify import verify,expected_facts


class RemapTests(unittest.TestCase):
    def test_actual_controls_do_not_certify_ancestry_or_hardware(self):
        summary=verify(expected_facts())
        self.assertFalse(summary['producer_ancestry_certified'])
        self.assertFalse(summary['executable_lifetime_certified'])
        self.assertFalse(summary['native_complete'])

    def test_fixed_4k_decoy_tags_rejected_even_with_equal_results(self):
        for key,tag in (('first',0x20001),('geometry',0x70001),('odd',0x80001)):
            facts=expected_facts();facts['tags'][key]=tag
            with self.assertRaises(AssertionError): verify(facts)

    def test_current_backing_cannot_replace_resident_bits(self):
        for key,value in (('stale',0x2222),('stale_new',0x3333),('away_back',0x4444),('asid_return',0x4444)):
            facts=expected_facts();facts[key]=value
            with self.assertRaises(AssertionError): verify(facts)

    def test_mapping_context_changes_cannot_invent_cache_retirement(self):
        for key in ('same_value_tlbwi','away_back','asid_fail'):
            facts=expected_facts();facts['resident_preservation'][key]=False
            with self.assertRaises(AssertionError): verify(facts)
        for key in ('away_back','asid_fail','asid_return'):
            facts=expected_facts();facts['misses'][key]+=1
            with self.assertRaises(AssertionError): verify(facts)

    def test_equal_payload_remap_must_observe_new_tag_and_miss(self):
        for group,key,value in (('tags','equal',0x11001),('misses','equal',1),('misses','geometry',3)):
            facts=expected_facts();facts[group][key]=value
            with self.assertRaises(AssertionError): verify(facts)

    def test_strict_types_census_and_hash(self):
        for mutate in (lambda f:f['misses'].update(first=True),
                lambda f:f['resident_preservation'].update(asid_fail=1),
                lambda f:f.update(native_complete=True),
                lambda f:f.update(icache_sha256='0'*64),
                lambda f:f['misses'].pop('start')):
            facts=expected_facts();mutate(facts)
            with self.assertRaises(AssertionError): verify(facts)


if __name__=='__main__': unittest.main()
