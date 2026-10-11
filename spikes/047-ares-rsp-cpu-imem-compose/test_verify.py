"""Independent finite history controls; no reference binary is required."""
import copy
import unittest
from verify import fixture_events, replay, verify, reject_forgeries


def fixture():
    events=fixture_events()
    initial_dmem=list(bytes.fromhex('340800aaaaee7722'))
    initial_imem=list(bytes.fromhex('deadbeef')*5)
    summary=replay(events,initial_dmem,initial_imem)
    begins=[e for e in events if e['kind']=='cpu_begin']
    ends=[e for e in events if e['kind']=='cpu_end']
    steps=[dict(index=i,phase=b['phase'],pc=b['pc'],word=b['word'],before=b['gpr'][:],after=e['gpr'][:])
        for i,(b,e) in enumerate(zip(begins,ends))]
    return dict(events=events,initial_dmem=initial_dmem,initial_imem=initial_imem,
        final_dmem=summary['final_dmem'],final_imem=summary['final_imem'],
        checkpoints=['synthetic']*16,steps=steps,state={})


class CompositionTests(unittest.TestCase):
    def test_mixed_unknown_and_distinct_same_value(self):
        result=verify(fixture())
        a,b,c=result['certificates']
        self.assertEqual(a['value'],b['value'])
        self.assertNotEqual(a['source']['ancestry'],b['source']['ancestry'])
        self.assertIsNone(c['source']['ancestry'][1])
        self.assertEqual(c['source']['context'],44)
        self.assertEqual(result['resident_writer_ordinals'][16:],[None]*4)

    def test_same_value_clobber_does_not_restore_lineage(self):
        data=fixture()
        begin=next(e for e in data['events'] if e['phase']==14 and e['kind']=='cpu_begin')
        end=next(e for e in data['events'] if e['phase']==14 and e['kind']=='cpu_end')
        self.assertEqual(begin['gpr'],end['gpr'])
        self.assertEqual([c['phase'] for c in verify(data)['certificates']],[3,6,13])

    def test_all_measured_adversaries(self):
        self.assertEqual(reject_forgeries(fixture()),20)

    def test_high_bits_cannot_disappear_between_load_and_store(self):
        data=fixture()
        for e in data['events']:
            if e['phase']==3 and e['gpr']:
                e['gpr'][8]^=1<<40
        with self.assertRaises(AssertionError):
            verify(data)

    def test_unknown_sink_cannot_borrow_equal_known_source(self):
        data=fixture()
        sink=next(e for e in data['events'] if e['phase']==8)
        sink.update(kind='rsp_sink',context=15)
        with self.assertRaises(AssertionError):
            verify(data)

    def test_host_order_snapshot_and_boolean_byte_rejected(self):
        for value in (True,0xef):
            data=fixture()
            data['initial_imem'][0]=value
            with self.assertRaises(AssertionError):
                verify(data)

    def test_decoy_equal_bits_are_a_distinct_definition(self):
        data=fixture()
        decoy=next(e for e in data['events'] if e['phase']==12 and e['kind']=='cpu_end')
        self.assertEqual(decoy['gpr'][8],decoy['gpr'][9])
        cert=verify(data)['certificates'][-1]
        self.assertEqual(cert['source']['register'],8)
        self.assertEqual(cert['source']['read_ordinal'],45)

    def test_boolean_register_in_baseline_projection_rejected(self):
        data=fixture()
        data['steps'][0]['before'][0]=False
        with self.assertRaises(AssertionError):
            verify(data)

    def test_break_context_cannot_authenticate_producing_stores(self):
        data=fixture()
        for event in data['events']:
            if event['kind'] in ('rsp_begin','rsp_sink','rsp_end'):
                event['word']=13
        with self.assertRaises(AssertionError):
            verify(data)

    def test_intervening_decoy_cannot_hide_register_discontinuity(self):
        data=fixture()
        for event in data['events']:
            if event['phase']==12 and event['gpr']:
                event['gpr'][8]^=1<<40
        with self.assertRaises(AssertionError):
            verify(data)

    def test_same_value_rsp_rewrite_cannot_reuse_old_context_identity(self):
        data=fixture()
        for event in data['events']:
            if event['phase']==4 and event['kind'] in ('rsp_begin','rsp_sink','rsp_end'):
                event['context']=1
        with self.assertRaises(AssertionError):
            verify(data)


if __name__=='__main__':
    unittest.main()
