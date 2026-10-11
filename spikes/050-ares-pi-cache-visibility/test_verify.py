import copy
import unittest
from verify import verify,expected_facts,expected_events,FIRST,SECOND
from adversaries import check


def fixture():
    data=expected_facts();data['events']=expected_events();return data


def find(data,kind,stage):
    return next(e for e in data['events'] if e['kind']==kind and e['stage']==stage)


class PiCacheTests(unittest.TestCase):
    def test_two_directional_controls_keep_certificate_gates_open(self):
        summary=verify(fixture())
        self.assertEqual(summary['events'],117)
        self.assertFalse(summary['completion_promotes_resident'])
        self.assertFalse(summary['completion_required_for_byte_effect'])
        self.assertFalse(summary['producer_ancestry_certified'])
        self.assertFalse(summary['queue_completion_identity_certified'])
        self.assertEqual(len(check(fixture())),10)

    def test_completion_cannot_promote_stale_fetch(self):
        data=fixture();find(data,'fetch_end',4)['value']=FIRST
        with self.assertRaises(AssertionError): verify(data)

    def test_current_backing_cannot_replace_stale_second_fetch(self):
        data=fixture();find(data,'fetch_end',9)['value']=SECOND
        with self.assertRaises(AssertionError): verify(data)

    def test_every_source_halfword_is_checked(self):
        for stage in (2,8):
            data=fixture();events=[e for e in data['events'] if e['kind']=='pi_source_half' and e['stage']==stage]
            for e in events:
                forged=copy.deepcopy(data)
                forged['events'][e['seq']-1]['value']^=0xffff
                with self.assertRaises(AssertionError): verify(forged)

    def test_tail_write_cannot_move_or_change(self):
        for key,value in (('address',0x4040),('value',255)):
            data=fixture();next(e for e in data['events'] if e['kind']=='pi_rdram_write' and e['address']==0x4004)[key]=value
            with self.assertRaises(AssertionError): verify(data)

    def test_exact_fetch_virtual_translated_bus_bindings(self):
        for key,value in (('vaddr',0xffffffff80008000),('translated',0x8000),('bus',0x8000),('cached',False)):
            data=fixture();find(data,'fetch_end',1)[key]=value
            with self.assertRaises(AssertionError): verify(data)

    def test_full_fill_span_and_location_are_checked(self):
        for key,value in (('physical',0x8000),('slot',1),('index',32),('words',[FIRST]+[1]*7)):
            data=fixture();find(data,'icache_fill',6)[key]=value
            with self.assertRaises(AssertionError): verify(data)

    def test_fill_must_follow_exact_backing_read(self):
        data=fixture();i=find(data,'icache_fill',6)['seq']-1
        data['events'][i-1],data['events'][i]=data['events'][i],data['events'][i-1]
        for seq,e in enumerate(data['events'],1): e['seq']=seq
        with self.assertRaises(AssertionError): verify(data)

    def test_queue_less_copy_cannot_be_deleted(self):
        data=fixture();data['events']=[e for e in data['events'] if e['stage']!=8]
        for seq,e in enumerate(data['events'],1): e['seq']=seq
        with self.assertRaises(AssertionError): verify(data)

    def test_completion_cannot_be_invented_for_second_copy(self):
        data=fixture();e=copy.deepcopy(find(data,'pi_completion',3));e.update(stage=8,transfer=2)
        data['events'].insert(111,e)
        for seq,e in enumerate(data['events'],1): e['seq']=seq
        with self.assertRaises(AssertionError): verify(data)

    def test_types_extra_fields_and_checkpoints_are_strict(self):
        for mutate in (lambda d:find(d,'fetch_end',1).update(seq=True),
                lambda d:d.update(native_complete=True),
                lambda d:d['checkpoints'].append(copy.deepcopy(d['checkpoints'][0])),
                lambda d:d['state'].update(busy=False)):
            data=fixture();mutate(data)
            with self.assertRaises(AssertionError): verify(data)


if __name__=='__main__': unittest.main()
