"""Aggregation/sorting, heat-bucket math (incl. midnight crossing), suggestions."""
import unittest
import time

from timesink.analyze import (
    aggregate,
    first_token,
    has_elapsed,
    heat_buckets,
    suggest,
    time_range,
    top_n,
    total_tracked,
)
from timesink.model import Entry

MIDNIGHT_DEC31 = 1672531199  # 2022-12-31 23:59:59 UTC
MIDNIGHT_JAN1 = 1672531201  # 2023-01-01 00:00:01 UTC

Z = lambda cmd, ts, el: Entry(cmd=cmd, ts=ts, elapsed=el, src="zsh")  # noqa: E731
PS = lambda cmd: Entry(cmd=cmd, src="powershell")  # noqa: E731


class TestAggregate(unittest.TestCase):
    def test_count_and_totals(self):
        entries = [
            Z("a", 1, 10), Z("a", 2, 20), Z("b", 3, 5),
        ]
        stats = aggregate(entries)
        self.assertEqual(stats["a"], [2, 30])
        self.assertEqual(stats["b"], [1, 5])

    def test_total_tracked(self):
        entries = [Z("a", 1, 10), Z("b", 2, None)]
        total, has_t = total_tracked(entries)
        self.assertTrue(has_t)
        self.assertEqual(total, 10)

    def test_total_tracked_no_elapsed(self):
        entries = [PS("a"), PS("b")]
        total, has_t = total_tracked(entries)
        self.assertFalse(has_t)
        self.assertEqual(total, 0)


class TestSorting(unittest.TestCase):
    def _entries(self, with_elapsed=True):
        if with_elapsed:
            return [
                Z("freqwin", 1, 1),   # high count, low total
                Z("times", 2, 100),   # low count, high total
                Z("freqwin", 3, 1),
                Z("freqwin", 4, 1),
            ]
        return [PS("freqwin"), PS("times"), PS("freqwin"), PS("freqwin")]

    def test_auto_uses_time_when_elapsed_present(self):
        rows = top_n(self._entries(True), 10, "auto")
        self.assertEqual(rows[0][0], "times")
        self.assertEqual(rows[0][2], 100)

    def test_auto_uses_freq_without_elapsed(self):
        rows = top_n(self._entries(False), 10, "auto")
        self.assertEqual(rows[0][0], "freqwin")
        self.assertEqual(rows[0][1], 3)

    def test_forced_sort_freq_on_elapsed_data(self):
        rows = top_n(self._entries(True), 10, "freq")
        self.assertEqual(rows[0][0], "freqwin")

    def test_tie_break_deterministic(self):
        entries = [Z("zeta", 1, 5), Z("alpha", 2, 5)]
        rows = top_n(entries, 10, "time")
        self.assertEqual([r[0] for r in rows], ["alpha", "zeta"])  # asc cmd after desc total

    def test_top_limit(self):
        entries = [Z(f"c{i}", i, i * 10) for i in range(20)]
        rows = top_n(entries, 3, "time")
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0][2], 190)

    def test_time_range(self):
        entries = [Z("a", 5, 1), Z("b", 2, 1)]
        self.assertEqual(time_range(entries), (2, 5))
        self.assertIsNone(time_range([PS("a")]))


class TestHeatBuckets(unittest.TestCase):
    def test_midnight_crossing_maps_to_own_hours(self):
        # 23:59:59 -> bucket 23, 00:00:01 -> bucket 0 (UTC)
        entries = [
            Z("late", MIDNIGHT_DEC31, 60),
            Z("early", MIDNIGHT_JAN1, 30),
        ]
        values = heat_buckets(entries, tz="utc")
        self.assertEqual(values[23], 60)
        self.assertEqual(values[0], 30)
        self.assertEqual(sum(values), 90)

    def test_hour_assignment_and_sum(self):
        base = 1672524000  # 22:00 UTC
        entries = [
            Z("a", base, 10),        # bucket 22
            Z("b", base + 3600, 20),  # bucket 23
            Z("c", base + 7200, 40),  # bucket 0 (00:00 next day)
        ]
        values = heat_buckets(entries, tz="utc")
        self.assertEqual(values[22], 10)
        self.assertEqual(values[23], 20)
        self.assertEqual(values[0], 40)
        self.assertEqual(sum(values), 70)

    def test_frequency_mode_weights_one(self):
        entries = [PS("x"), PS("y"), PS("x")]
        values = heat_buckets(entries, tz="utc")
        self.assertEqual(sum(values), 0)  # no timestamps → excluded
        self.assertEqual(values, [0] * 24)

    def test_empty_entries(self):
        self.assertEqual(heat_buckets([], tz="utc"), [0] * 24)

    def test_local_tz_switch_uses_localtime(self):
        entries = [Z("a", 1672531200, 5)]  # 2023-01-01T00:00Z
        utc = heat_buckets(entries, tz="utc")
        local = heat_buckets(entries, tz="local")
        self.assertEqual(utc[0], 5)
        # local must be computed via time.localtime's hour, in [0,23]
        hour = time.localtime(1672531200).tm_hour
        self.assertEqual(local[hour], 5)
        self.assertEqual(sum(local), 5)


class TestSuggestions(unittest.TestCase):
    def _seq(self, cmds):
        return [PS(c) for c in cmds]

    def test_below_threshold_no_suggestion(self):
        seq = ["git status"] * 4 + ["ls"]
        self.assertEqual(suggest(self._seq(seq), threshold=5), [])

    def test_threshold_triggers(self):
        seq = ["git status"] * 5
        sugs = suggest(self._seq(seq), threshold=5)
        self.assertEqual(len(sugs), 1)
        self.assertEqual(sugs[0].prefix, "git")
        self.assertEqual(sugs[0].max_run, 5)
        self.assertTrue(sugs[0].all_same)

    def test_non_consecutive_prefix_not_a_run(self):
        seq = ["git status", "cd ..", "git add", "cd ..", "git log", "cd .."]
        self.assertEqual(suggest(self._seq(seq), threshold=3), [])

    def test_runs_merged_per_prefix(self):
        seq = ["git add"] * 5 + ["ls"] + ["git status"] * 6
        sugs = suggest(self._seq(seq), threshold=5)
        self.assertEqual(len(sugs), 1)
        self.assertEqual(sugs[0].prefix, "git")
        self.assertEqual(sugs[0].max_run, 6)   # worst burst
        self.assertEqual(sugs[0].total, 11)    # 5 + 6 (qualifying bursts only)
        self.assertEqual(len(sugs[0].distinct), 2)
        self.assertFalse(sugs[0].all_same)

    def test_custom_threshold(self):
        seq = ["pytest -q"] * 4
        self.assertEqual(suggest(self._seq(seq), threshold=5), [])
        sugs = suggest(self._seq(seq), threshold=4)
        self.assertEqual(len(sugs), 1)
        self.assertEqual(sugs[0].max_run, 4)

    def test_sorted_by_worst_burst(self):
        seq = ["b"] * 3 + ["a"] * 7
        sugs = suggest(self._seq(seq), threshold=3)
        self.assertEqual([s.prefix for s in sugs], ["a", "b"])

    def test_first_token(self):
        self.assertEqual(first_token("  git  status "), "git")
        self.assertEqual(first_token(""), "")

    def test_has_elapsed(self):
        self.assertTrue(has_elapsed([Z("a", 1, 0)]))
        self.assertFalse(has_elapsed([PS("a")]))


if __name__ == "__main__":
    unittest.main()