"""Render-layer unit tests: durations, heat line, table, suggestions text."""
import unittest

from timesink.analyze import suggest
from timesink.model import Entry
from timesink.render import (
    HEAT_TICKS,
    fmt_duration,
    heat_line,
    render_heat,
    render_suggestions,
    render_table,
    truncate,
)

PS = lambda cmd: Entry(cmd=cmd, src="powershell")  # noqa: E731
Z = lambda cmd, ts, el: Entry(cmd=cmd, ts=ts, elapsed=el, src="zsh")  # noqa: E731


class TestDuration(unittest.TestCase):
    def test_cases(self):
        self.assertEqual(fmt_duration(0), "0s")
        self.assertEqual(fmt_duration(59), "59s")
        self.assertEqual(fmt_duration(60), "1m00s")
        self.assertEqual(fmt_duration(3599), "59m59s")
        self.assertEqual(fmt_duration(3600), "1h00m00s")
        self.assertEqual(fmt_duration(3661), "1h01m01s")

    def test_none(self):
        self.assertEqual(fmt_duration(None), "–")


class TestHeat(unittest.TestCase):
    def test_line_width_and_intensity(self):
        values = [0] * 23 + [64]
        line = heat_line(values)
        self.assertEqual(len(line), 24)
        self.assertEqual(line[-1], "█")       # peak → hottest char
        self.assertEqual(line[0], "▁")        # zero → minimum char

    def test_relative_levels(self):
        line = heat_line([0, 4, 8])
        self.assertLess(line.index("▅"), line.index("█"))
        self.assertEqual(line, heat_line([0, 4, 8]))  # deterministic

    def test_empty_values(self):
        self.assertEqual(len(heat_line([])), 0)

    def test_ticks_width(self):
        self.assertEqual(len(HEAT_TICKS), 24)
        self.assertTrue(HEAT_TICKS.startswith("0"))

    def test_render_heat_roundtrip(self):
        text = render_heat([1, 2, 3])
        self.assertIn("最闲", text)
        self.assertIn("最忙", text)


class TestTable(unittest.TestCase):
    def test_contains_commands_and_header(self):
        rows = [("git status", 9, 338), ("vim", 2, 360)]
        text = render_table(rows, top=15, has_time=True, sort="time")
        self.assertIn("Top 15 命令", text)
        self.assertIn("git status", text)
        self.assertIn("6m00s", text)  # 360s
        self.assertNotIn("\x1b", text)   # no ANSI escapes — pipe-friendly

    def test_no_elapsed_shows_dash(self):
        rows = [("ls", 3, 0)]
        text = render_table(rows, top=5, has_time=False, sort="freq")
        self.assertIn("ls", text)
        self.assertIn("–", text)

    def test_empty_rows(self):
        text = render_table([], top=5, has_time=True, sort="auto")
        self.assertIn("无命令数据", text)

    def test_truncate(self):
        self.assertEqual(truncate("short", 20), "short")
        long = "x" * 100
        self.assertEqual(len(truncate(long, 10)), 10)
        self.assertTrue(truncate(long, 10).endswith("…"))


class TestSuggestionsRender(unittest.TestCase):
    def test_alias_suggestion(self):
        seq = ["git status"] * 6
        sugs = suggest([PS(c) for c in seq], threshold=5)
        text = render_suggestions(sugs)
        self.assertIn("连续执行 6 次", text)
        self.assertIn("alias gs='git status'", text)

    def test_script_suggestion(self):
        seq = ["npm run test"] * 5 + ["ls"] + ["npm run build"] * 5
        sugs = suggest([PS(c) for c in seq], threshold=5)
        text = render_suggestions(sugs)
        self.assertIn("前缀 `npm` 连续出现 5 次", text)
        self.assertIn("累计 10 次", text)  # the two bursts are merged
        self.assertIn("脚本", text)

    def test_empty(self):
        text = render_suggestions([])
        self.assertIn("未发现", text)


if __name__ == "__main__":
    unittest.main()