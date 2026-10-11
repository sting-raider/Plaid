"""Strict reported behavior for four original unmodified-reference scenarios."""
OLD=0x24020001
NEW=0x24020002


def expected_facts():
    return dict(normal_after_store=1,normal_after_writeback=1,normal_final=2,
        normal_source=NEW^255,normal_transform=NEW,normal_backing=NEW,normal_icache=NEW,
        foreign_after_store=1,foreign_after_writeback=1,foreign_final=2,
        foreign_backing=NEW,foreign_icache=NEW,prefill_after_store=1,
        prefill_after_writeback=1,prefill_final=1,prefill_backing=NEW,prefill_icache=OLD,
        identity_source=NEW,identity_transform=NEW,identity_final=2,identity_backing=NEW,
        exception=0)


def verify(facts):
    assert type(facts) is dict and set(facts)==set(expected_facts())
    assert all(type(v) is int and 0<=v<1<<32 for v in facts.values())
    assert facts==expected_facts()
    return dict(scope='finite_unmodified_xori_cache_visibility',scenarios=4,
        stale_after_store=True,stale_after_writeback=True,prefill_remains_stale=True,
        identity_transform_executed=True,producer_ancestry_certified=False,
        mutation_coverage_certified=False,executable_lifetime_certified=False,native_complete=False)
