"""Check source byte reconstruction across storage rows and fetch scopes."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('projection', HERE/'check_legacy_projection.py')
projection = importlib.util.module_from_spec(spec)
spec.loader.exec_module(projection)

OLD = b'''{"record":"header","format":"plaid-ares-access-history-v3","policy":"identity_ram_pi_queue_and_observed_sp_backing"}
{"record":"fetch_begin","ordinal":1,"context":1,"pc":12}
{"record":"fetch_end","ordinal":2,"context":1,"pc":12}
{"record":"fetch","ordinal":3,"context":0,"pc":12,"fetch_context":1,"word":55}
{"record":"fetch_begin","ordinal":4,"context":4,"pc":16}
{"record":"fetch_end","ordinal":5,"context":4,"pc":16}
{"record":"fetch","ordinal":6,"context":0,"pc":16,"fetch_context":4,"word":66}
{"record":"end","record_count":6,"fetch_count":2}
'''
RAW = b'''{"record":"header","format":"plaid-ares-access-history-v5","policy":"observed_ordinary_storage_mutations_and_pi_queue_sp_backing"}
{"record":"fetch_begin","ordinal":1,"context":1,"pc":12}
{"record":"storage_effect","ordinal":2,"context":1,"pc":12,"kind":0,"address":4,"bytes":1,"value":7}
{"record":"fetch_end","ordinal":3,"context":1,"pc":12}
{"record":"fetch","ordinal":4,"context":0,"pc":12,"fetch_context":1,"word":55}
{"record":"storage_effect","ordinal":5,"context":0,"pc":16,"kind":0,"address":5,"bytes":1,"value":8}
{"record":"fetch_begin","ordinal":6,"context":6,"pc":16}
{"record":"fetch_end","ordinal":7,"context":6,"pc":16}
{"record":"fetch","ordinal":8,"context":0,"pc":16,"fetch_context":6,"word":66}
{"record":"end","record_count":8,"fetch_count":2}
'''


class ProjectionTests(unittest.TestCase):
    def inspect(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'history.ndjson'
            path.write_bytes(data)
            return projection.inspect(path)

    def test_original_bytes_and_two_distinct_fetch_scopes(self):
        self.assertEqual(self.inspect(RAW), dict(raw_records=8, legacy_records=6,
            storage_effects=2, legacy_sha256=hashlib.sha256(OLD).hexdigest()))

    def test_incomplete_or_inconsistent_source_rejects(self):
        variants = (
            RAW.replace(b'"ordinal":7', b'"ordinal":9'),
            RAW.replace(b'"context":6', b'"context":5', 1),
            RAW.replace(b'"fetch_context":6', b'"fetch_context":5'),
            RAW.replace(b'"record_count":8', b'"record_count":7'),
            RAW.rsplit(b'{"record":"end"', 1)[0],
            RAW + b'{}\n',
        )
        for data in variants:
            with self.subTest(data=data), self.assertRaises(AssertionError):
                self.inspect(data)


if __name__ == '__main__':
    unittest.main()
