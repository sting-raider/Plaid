"""The retained-report shortcut rejects any selected new branch or bad interval."""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('retained',Path(__file__).with_name('check_retained.py'))
retained=importlib.util.module_from_spec(spec);spec.loader.exec_module(retained)


class RetainedTests(unittest.TestCase):
    def check(self,rows,expected=None):
        raw=b''.join(json.dumps(e,separators=(',',':')).encode()+b'\n' for e in rows)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'source.ndjson';path.write_bytes(raw)
            return retained.inspect(path,expected or hashlib.sha256(raw).hexdigest())

    def source(self):
        return [dict(record='pi_dma',ordinal=1,event=4,pc=12,value=7),
            dict(record='storage_effect',ordinal=2,kind=0,bytes=1,context=0,pc=12,value=7,address=4096),
            dict(record='scalar',ordinal=3,address=4096,pi=dict(transfer=1)),
            dict(record='pi_dma',ordinal=4,event=5,dram=4096)]

    def test_unchanged_identity_and_missing_primitive(self):
        result=self.check(self.source())
        self.assertEqual((result['attempts'],result['unchanged_wrapper_writers']),(1,1))
        rows=self.source();rows=rows[:1]+rows[-1:]
        self.assertEqual(self.check(rows)['missing_primitives'],1)

    def test_changed_parent_interval_and_digest_cannot_reuse_report(self):
        for variant in range(5):
            rows=self.source()
            if variant==0: rows.pop(2)
            elif variant==1: rows[1]['address']=8192
            elif variant==2: rows[1]['value']=8
            elif variant==3: rows.insert(2,dict(rows[1]))
            else: rows[-1]['ordinal']=5
            with self.subTest(variant=variant),self.assertRaises(AssertionError): self.check(rows)
        with self.assertRaises(AssertionError): self.check(self.source(),'0'*64)


if __name__=='__main__': unittest.main()
