"""Finite reported cache behavior; no mapping/fill ancestry certificate."""


def expected_facts():
    return dict(select16=0x4000,select64=0x10000,mask16=0x6000,mask64=0x1e000,
        first=0x1111,stale=0x1111,equal_remap=0x1111,stale_new=0x1111,
        fresh_original=0x2222,away_back=0x2222,asid_exception=2,
        asid_return=0x2222,geometry_remap=0x2222,odd=0x5555,
        tags=dict(first=0x11001,equal=0x31001,original_again=0x11001,
            geometry=0x51001,odd=0xa0001),
        resident_preservation=dict(same_value_tlbwi=True,away_back=True,asid_fail=True),
        misses=dict(start=0,first=1,stale=1,equal=2,fresh_original=3,away_back=3,
            asid_fail=3,asid_return=3,geometry=4,odd=5),
        icache_sha256='9929c6d182ea6efd93fe325a9c71040c944babd9037fba2f7254ca944471125d')


def exact(actual,expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual)==set(expected)
        for key in expected:
            exact(actual[key],expected[key])
    else:
        assert actual==expected


def verify(facts):
    exact(facts,expected_facts())
    return dict(scope='finite_unmodified_pagemask_cache_remap',page_sizes=[16384,65536],
        same_value_mapping_preserves_resident=True,temporary_unreachability_preserves_resident=True,
        geometry_remap_refills=True,producer_ancestry_certified=False,
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
