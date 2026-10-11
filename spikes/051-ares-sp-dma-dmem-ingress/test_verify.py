import copy
import unittest
from verify import verify, fixture_events, fixture_state
from adversaries import check


class Contracts(unittest.TestCase):
    def setUp(self):
        self.data = dict(events=fixture_events(), state=fixture_state())

    def test_full_census_and_distinct_reload_writers(self):
        result = verify(self.data)
        self.assertEqual(result['word_joins'][0]['source_read'], 1)
        self.assertEqual(result['word_joins'][2]['source_read'], 5)
        self.assertFalse(result['source_storage_ancestry_certified'])
        self.assertFalse(result['native_complete'])

    def test_all_twelve_forgeries(self):
        self.assertEqual(len(check(self.data)), 12)

    def test_every_effect_payload_is_checked(self):
        for index in range(27):
            with self.subTest(index=index):
                forged = copy.deepcopy(self.data)
                forged['events'][index]['value'] ^= 1
                with self.assertRaises(AssertionError):
                    verify(forged)

    def test_every_effect_has_exact_schema(self):
        for index in range(27):
            with self.subTest(index=index):
                forged = copy.deepcopy(self.data)
                forged['events'][index]['extra'] = 0
                with self.assertRaises(AssertionError):
                    verify(forged)

    def test_missing_sink_and_extra_sink(self):
        for delta in [-1, 1]:
            forged = copy.deepcopy(self.data)
            if delta == -1:
                forged['events'].pop()
            else:
                forged['events'].append(forged['events'][-1].copy())
            with self.assertRaises(AssertionError):
                verify(forged)

    def test_reported_state_has_exact_types(self):
        forged = copy.deepcopy(self.data)
        forged['state']['dma_busy'] = False
        with self.assertRaises(AssertionError):
            verify(forged)


if __name__ == '__main__':
    unittest.main()
