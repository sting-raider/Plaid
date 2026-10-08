import unittest

from chronology import (
    CacheOp,
    Fetch,
    Fill,
    Joiner,
    Other,
    RdramRead,
    RdramWrite,
    ResetOrRestore,
    _words,
    controlled_sequence,
)


class ChronologyTests(unittest.TestCase):
    def test_controlled_sequence(self):
        joiner = Joiner()
        events, expected = controlled_sequence()
        for event in events:
            joiner.push(event)
        self.assertEqual([r.origin_witness_id for r in joiner.fetches], expected)
        self.assertEqual([w.burst_ordinal for w in joiner.witnesses], [1, 7, 13, 18])
        self.assertEqual([w.fill_ordinal for w in joiner.witnesses], [2, 8, 14, 19])
        self.assertEqual(joiner.rejected_fills, [])

    def test_fill_without_backing_read_is_rejected(self):
        words = _words((3, 0, 0, 0, 0, 0, 0, 0))
        joiner = Joiner()
        joiner.push(Fill(0, 0, 0, words))
        joiner.push(Fetch(0, 0, 1, words, 0, 3))
        self.assertEqual(len(joiner.witnesses), 0)
        self.assertIsNone(joiner.fetches[-1].origin_witness_id)
        self.assertIn("immediately preceding", joiner.rejected_fills[-1][1])

    def test_equal_payload_wrong_address_is_rejected(self):
        words = _words((1, 2, 3, 4, 5, 6, 7, 8))
        joiner = Joiner()
        joiner.push(RdramRead(0x4000, words))
        joiner.push(Fill(0, 0x0000, 0, words))
        joiner.push(Fetch(0, 0x0000, 1, words, 0, 1))
        self.assertIsNone(joiner.fetches[-1].origin_witness_id)
        self.assertIn("address", joiner.rejected_fills[-1][1])

    def test_non_identity_read_is_rejected_even_if_bytes_match(self):
        words = _words((1, 1, 1, 1, 1, 1, 1, 1))
        joiner = Joiner()
        joiner.push(RdramRead(0, words, identity_mapped=False))
        joiner.push(Fill(0, 0, 0, words))
        self.assertEqual(len(joiner.witnesses), 0)
        self.assertIn("outside", joiner.rejected_fills[-1][1])

    def test_intervening_event_breaks_causal_pair(self):
        words = _words(range(8))
        joiner = Joiner()
        joiner.push(RdramRead(0, words))
        joiner.push(Other("some independently observed event"))
        joiner.push(Fill(0, 0, 0, words))
        self.assertEqual(len(joiner.witnesses), 0)
        self.assertIn("immediately preceding", joiner.rejected_fills[-1][1])

    def test_tag_mutation_without_fill_clears_lineage(self):
        words = _words((9, 0, 0, 0, 0, 0, 0, 0))
        joiner = Joiner()
        joiner.push(RdramRead(0, words))
        joiner.push(Fill(0, 0, 0, words))
        joiner.push(CacheOp(0, 0x4001, words, 0x08))
        joiner.push(Fetch(0, 0x4000, 0x4001, words, 0, 9))
        self.assertIsNone(joiner.fetches[-1].origin_witness_id)

    def test_backing_write_does_not_rewrite_resident_origin(self):
        old = _words((9, 0, 0, 0, 0, 0, 0, 0))
        joiner = Joiner()
        joiner.push(RdramRead(0x4000, old))
        joiner.push(Fill(0, 0x4000, 0, old))
        joiner.push(RdramWrite(0x4000, _words((8, 0, 0, 0, 0, 0, 0, 0))))
        joiner.push(Fetch(0, 0x4000, 0x4001, old, 0, 9))
        self.assertEqual(joiner.fetches[-1].origin_witness_id, 1)

    def test_reset_or_restore_clears_lineage(self):
        words = _words((7, 0, 0, 0, 0, 0, 0, 0))
        joiner = Joiner()
        joiner.push(RdramRead(0, words))
        joiner.push(Fill(0, 0, 0, words))
        joiner.push(ResetOrRestore("savestate restore"))
        joiner.push(Fetch(0, 0, 1, words, 0, 7))
        self.assertIsNone(joiner.fetches[-1].origin_witness_id)

    def test_payload_mismatch_is_rejected(self):
        a = _words(range(8))
        b = _words(range(1, 9))
        joiner = Joiner()
        joiner.push(RdramRead(0, a))
        joiner.push(Fill(0, 0, 0, b))
        self.assertEqual(len(joiner.witnesses), 0)
        self.assertIn("payload", joiner.rejected_fills[-1][1])

    def test_non_icache_or_wrong_width_read_is_rejected(self):
        words = _words(range(8))
        for read in (
            RdramRead(0, words, icache_requestor=False),
            RdramRead(0, words, bytes=16),
        ):
            with self.subTest(read=read):
                joiner = Joiner()
                joiner.push(read)
                joiner.push(Fill(0, 0, 0, words))
                self.assertEqual(len(joiner.witnesses), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
