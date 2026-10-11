"""Strict finite ingress fixture contract; not a general DMA certificate."""


def fixture_events():
    events = []

    def add(kind, **fields):
        events.append(dict(seq=len(events)+1, kind=kind, bytes=4, **fields))

    rows = [
        (0x1000, 0, 0x11223344, 0x11223344),
        (0x2000, 0, 0x11223344, 0x11223344),
        (0x3000, 0x20, 0xa0a1a2a3, 0xa4a5a6a7),
        (0x3010, 0x28, 0xb0b1b2b3, 0xb4b5b6b7),
        (0x4000, 0xff8, 0xc0c1c2c3, 0xc4c5c6c7),
        (0x4008, 0, 0xd0d1d2d3, 0xd4d5d6d7),
    ]
    for dram, dmem, low, high in rows:
        for lane, value in [(0, low), (4, high)]:
            add('rdram_read', dram=dram+lane, value=value)
        for lane, value in [(0, low), (4, high)]:
            add('dmem_dma_write', dram=dram+lane, dmem=(dmem+lane)&0xfff, value=value)
    for lane in [0, 4]:
        add('dmem_dma_write', dram=0x800000+lane, dmem=0x60+lane, value=0)
    add('dmem_direct_write', dmem=0x20, value=0xa0a1a2a3, origin_cpu=True)
    return events


def fixture_state():
    return dict(
        checkpoints=[0x11223344]*3 + [0xa0a1a2a3, 0xa4a5a6a7, 0xb0b1b2b3,
            0xb4b5b6b7, 0xc0c1c2c3, 0xc4c5c6c7, 0xd0d1d2d3, 0xd4d5d6d7,
            0, 0, 0xa0a1a2a3],
        dma_busy=0, dma_full=0,
        dmem_sha256='2e93a22bf995b066fd95a0f3a18c8d164a98dd9de11a9e7cbe2291ae5ddd9381',
        imem_sha256='ad7facb2586fc6e966c004d7d1d16b024f5805ff7cb47c7a85dabd8b48892ca7',
        rdram_sha256='5677e82cad52aea5d3a40badaac838af91ea3af035a76eb53cea32319c0d1e51')


def exact(actual, expected):
    """Check every field and type; Python bool/int equality is insufficient."""
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert actual.keys() == expected.keys()
        for key in expected:
            exact(actual[key], expected[key])
    elif type(expected) is list:
        assert len(actual) == len(expected)
        for item, control in zip(actual, expected):
            exact(item, control)
    else:
        assert actual == expected


def verify(data):
    exact(data, dict(events=fixture_events(), state=fixture_state()))
    # The complete finite census above authenticates the controlled lane order.
    # This replay reports successful read identities, not ultimate ROM ancestry.
    reads = {}
    cells = {}
    joins = []
    generation = 0
    for event in data['events']:
        if event['kind'] == 'rdram_read':
            assert event['dram'] not in reads
            reads[event['dram']] = event
            continue
        generation += 1
        source = None
        if event['kind'] == 'dmem_dma_write':
            source = reads.pop(event['dram'], None)
            if source is not None:
                assert source['seq'] < event['seq'] and source['value'] == event['value']
        for lane, value in enumerate(event['value'].to_bytes(4, 'big')):
            cells[(event['dmem']+lane)&0xfff] = dict(
                value=value, writer=event['seq'], generation=generation,
                source_read=source['seq'] if source else None,
                source_address=source['dram']+lane if source else None)
        joins.append(dict(writer=event['seq'], generation=generation,
            dmem=event['dmem'], source_read=source['seq'] if source else None,
            source_address=source['dram'] if source else None))
    assert not reads
    assert joins[0]['source_read'] == 1 and joins[1]['source_read'] == 2
    assert joins[2]['source_read'] == 5 and joins[2]['generation'] != joins[0]['generation']
    assert all(cells[0x60+i]['source_read'] is None for i in range(8))
    assert all(cells[0x20+i]['writer'] == 27 for i in range(4))
    assert all(cells[0x24+i]['source_read'] == 10 for i in range(4))
    assert all(cells[i]['source_read'] == 21 for i in range(4))
    return dict(schema_version=0, events=27, successful_source_words=12,
        dma_sink_words=14, unknown_dma_sink_words=2, direct_sink_words=1,
        local_generations=15, word_joins=joins,
        nearest_value_counterexample=dict(writer=3, source_read=1, wrong_nearest_read=2),
        source_storage_ancestry_certified=False, dma_request_lifecycle_certified=False,
        cpu_instruction_producer_certified=False, producer_census_certified=False,
        executable_lifetime_certified=False, native_complete=False)
