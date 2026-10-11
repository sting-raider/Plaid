"""Finite executed context/cache behavior; no measured generation certificate."""
import copy


def expected():
    return dict(idx_switch=0, idx_global=256,
        first_a=dict(value=0x1111, paddr=0x1000),
        global_b=dict(value=0x7777, paddr=0x7000),
        global_a=dict(value=0x7777, paddr=0x7000),
        fault=dict(exception=2, badvaddr=0x4000),
        stale_reactivated_a=dict(value=0x1111, paddr=0x1000),
        equal_c=dict(value=0x1111, paddr=0x5000),
        fresh_a=dict(value=0x4444, paddr=0x1000),
        tlbp_context_unchanged=True, same_value_tlbr_unchanged=True,
        out_of_range_tlbr_unchanged=True, installed_entries_unchanged=True,
        inactive_backing_word=0x34094444, initial_tag=0x1001, equal_tag=0x5001,
        misses=dict(start=0, first_a=1, fault_before=2, fault_after=2,
            reactivate_before=2, reactivate_after=2, equal_before=2, equal_after=3,
            fresh_before=3, fresh_after=4),
        icache_sha256='130c3e8f7638eb65c18bbc3e5690f667ddf0d3796c03ae3af4908d99e2fad1ea')


def exact(actual, control):
    assert type(actual) is type(control)
    if type(control) is dict:
        assert actual.keys() == control.keys()
        for key in control:
            exact(actual[key], control[key])
    else:
        assert actual == control


def verify(data):
    exact(data, expected())
    return dict(schema_version=0, temporary_inactivity_preserves_resident=True,
        reactivated_stale_value=0x1111, replacement_refill_value=0x4444,
        guest_context_writer_history_certified=False, mapping_generation_certified=False,
        successful_tlbr_writer_history_certified=False,
        backing_fill_ancestry_certified=False, producer_census_certified=False,
        executable_lifetime_certified=False, hardware_index_policy_certified=False,
        native_complete=False)


def reject_forgeries(data):
    cases = []
    for key, value in data.items():
        fields = value.items() if type(value) is dict else [(None, value)]
        for subkey, leaf in fields:
            forged = copy.deepcopy(data)
            bad = not leaf if type(leaf) is bool else leaf ^ 1 if type(leaf) is int else 'f'*64
            if subkey is None:
                forged[key] = bad
            else:
                forged[key][subkey] = bad
            cases.append((key+(':'+subkey if subkey else ''), forged))
    shifted = copy.deepcopy(data)
    shifted['misses'] = {key: value+100 for key, value in shifted['misses'].items()}
    cases.append(('offset_all_miss_counts', shifted))
    invalid_tags = copy.deepcopy(data)
    invalid_tags['initial_tag'] &= ~1
    invalid_tags['equal_tag'] &= ~1
    cases.append(('invalid_resident_tags', invalid_tags))
    boolean = copy.deepcopy(data)
    boolean['idx_switch'] = False
    cases.append(('boolean_index', boolean))
    unknown = copy.deepcopy(data)
    unknown['source_generation'] = 'fabricated'
    cases.append(('unknown_generation_field', unknown))
    rejected = []
    for label, forged in cases:
        try:
            verify(forged)
        except AssertionError:
            rejected.append(label)
        else:
            raise AssertionError('forged finite facts accepted: '+label)
    return rejected
