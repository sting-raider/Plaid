"""Strict finite PI/copy/cache behavior, not a general provenance certificate."""
OLD=0x34080000
FIRST=0x34081111
SECOND=0x34083333
TARGET=0x4000
VA=0xffffffff80004000


def expected_events():
    events=[]

    def add(stage,kind,**fields):
        events.append(dict(seq=len(events)+1,stage=stage,kind=kind,**fields))

    def fetch(stage,word,fill=False):
        add(stage,'fetch_begin',vaddr=VA,translated=TARGET,bus=TARGET,cached=True,value=0)
        if fill:
            words=[word]+[0]*7
            add(stage,'icache_backing_read',address=TARGET,bytes=32,device=1,words=words)
            add(stage,'icache_fill',slot=0,physical=TARGET,index=0,words=list(words))
        add(stage,'fetch_end',vaddr=VA,translated=TARGET,bus=TARGET,cached=True,value=word)

    def copy(stage,transfer,offset,word):
        add(stage,'pi_copy_begin',event=1,transfer=transfer,dram=TARGET,
            pbus=0x10000000+offset,length=32,lane=0,value=0)
        payload=word.to_bytes(4,'big')+bytes(28)
        for i in range(0,32,2):
            add(stage,'pi_source_half',transfer=transfer,offset=offset+i,
                value=int.from_bytes(payload[i:i+2],'big'))
        for i,value in enumerate(payload):
            add(stage,'pi_rdram_write',transfer=transfer,address=TARGET+i,bytes=1,device=5,value=value)
        # These post-copy register values are a pinned fixture fact, not a length certificate.
        add(stage,'pi_copy_return',event=7,transfer=transfer,dram=TARGET+32,
            pbus=0x10000000+offset+32,length=127,lane=0,value=0)

    fetch(1,OLD,True)
    copy(2,1,0x1000,FIRST)
    add(3,'pi_completion',event=8,transfer=1,dram=TARGET+32,
        pbus=0x10001020,length=127,lane=0,value=1)
    fetch(4,OLD)
    fetch(6,FIRST,True)
    copy(8,2,0x3000,SECOND)
    fetch(9,FIRST)
    fetch(11,SECOND,True)
    return events


def expected_facts():
    checkpoints=[]
    for stage,t0,backing,resident,busy,interrupt in (
            (1,0,OLD,OLD,0,0),(2,0,FIRST,OLD,1,0),(3,0,FIRST,OLD,0,1),
            (4,0,FIRST,OLD,0,1),(6,0x1111,FIRST,FIRST,0,1),
            (8,0x1111,SECOND,FIRST,1,0),(9,0x1111,SECOND,FIRST,1,0),
            (11,0x3333,SECOND,SECOND,1,0)):
        checkpoints.append(dict(stage=stage,t0=t0,backing=backing,resident=resident,
            resident_hit=1,busy=busy,interrupt=interrupt))
    return dict(checkpoints=checkpoints,state=dict(pc=VA+4,count=511,exception=0,
        t0=0x3333,backing=SECOND,busy=1,interrupt=0,
        ram_sha256='f344ada512d15cb8c28a5361fe018dc800f41f8226b8b947e9b803f2a6f53be7'))


def exact(actual,expected):
    assert type(actual) is type(expected)
    if type(expected) is dict:
        assert set(actual)==set(expected)
        for key in expected: exact(actual[key],expected[key])
    elif type(expected) is list:
        assert len(actual)==len(expected)
        for a,b in zip(actual,expected): exact(a,b)
    else: assert actual==expected


def verify(data):
    expected=expected_facts();expected['events']=expected_events()
    exact(data,expected)
    return dict(scope='finite_pi_copy_cache_visibility',events=len(expected['events']),
        pi_writes=[32,32],source_halves=[16,16],completion_transfers=[1],
        queue_less_transfer=2,completion_promotes_resident=False,
        completion_required_for_byte_effect=False,producer_ancestry_certified=False,
        queue_completion_identity_certified=False,mutation_coverage_certified=False,
        executable_lifetime_certified=False,native_complete=False)
