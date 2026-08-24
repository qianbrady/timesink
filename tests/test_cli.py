"""End-to-end CLI tests: demo determinism, file inputs, flags, AI fallback.

All tests call ``timesink.cli.main(argv)`` directly (no subprocess — the
sandbox forbids child pipelines; the CLI logic is importable by design).
"""
import contextlib
import io
import unittest
from unittest import mock

from timesink.cli import main
from timesink.demo import DEMO, demo_entries

try:  # unittest discover -s tests imports modules top-level; package mode otherwise
    from .util import tmp_file
except ImportError:
    from util import tmp_file

ZSH_FILE = (
    ": 1672500000:120;vim notes.md\n"
    ": 1672500120:45;git status\n"
    ": 1672500165:60;git status\n"
    ": 1672500225:30;git status\n"
    ": 1672500255:40;git status\n"
    ": 1672500295:50;git status\n"
    ": 1672500345:25;ls -la\n"
)
BASH_FILE = "#1672500000\nvim notes.md\n#1672500010\ngit status\ngit add -A\n"
PS_FILE = "Get-Process\nset-location ..\npython build.py\npython build.py\n"


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = main(argv)
    return rc, out.getvalue(), err.getvalue()


class TestDemo(unittest.TestCase):
    def test_default_is_demo_and_exit_zero(self):
        rc, out, _ = run_cli([])
        self.assertEqual(rc, 0)
        self.assertIn("timesink 0.1.0", out)
        self.assertIn("Top 15 命令", out)
        self.assertIn("git status", out)

    def test_demo_deterministic(self):
        _, out1, _ = run_cli(["--demo"])
        _, out2, _ = run_cli(["--demo"])
        self.assertEqual(out1, out2)

    def test_demo_key_stats(self):
        rc, out, _ = run_cli(["--demo", "--tz", "utc"])
        self.assertEqual(rc, 0)
        self.assertIn("追踪时长估算: 总计", out)
        self.assertIn("时段热力 24h（UTC", out)
        self.assertIn("建议（规则引擎）", out)
        self.assertIn("连续执行 6 次", out)   # git burst
        self.assertIn("前缀 `npm` 连续出现 6 次", out)

    def test_demo_aggregation_consistent_with_constants(self):
        total = sum(el for _, el, _ in DEMO)
        self.assertEqual(len(demo_entries()), len(DEMO))
        rc, out, _ = run_cli(["--demo", "--top", "1"])
        self.assertEqual(rc, 0)
        self.assertIn(f"命令条数: {len(DEMO)}", out)


class TestCliFiles(unittest.TestCase):
    def test_missing_file_friendly_error(self):
        rc, out, err = run_cli(["--file", "no/such/history.txt"])
        self.assertEqual(rc, 1)
        self.assertIn("无法读取", err)
        self.assertNotIn("Traceback", err)

    def test_empty_file_friendly_error(self):
        with tmp_file("") as path:
            rc, out, err = run_cli(["--file", path])
        self.assertEqual(rc, 1)
        self.assertIn("未解析到任何命令", err)

    def test_zsh_file_top_and_time_sort(self):
        with tmp_file(ZSH_FILE) as path:
            rc, out, _ = run_cli(["--file", path, "--top", "3"])
        self.assertEqual(rc, 0)
        self.assertIn("Top 3 命令", out)
        self.assertIn("git status", out)
        self.assertIn("2m00s", out)  # vim notes.md 120s
        self.assertIn("3m45s", out)  # git status 45+60+30+40+50 = 225s

    def test_bash_file_frequency_sort(self):
        with tmp_file(BASH_FILE) as path:
            rc, out, _ = run_cli(["--file", path, "--sort", "freq"])
        self.assertEqual(rc, 0)
        self.assertIn("bash HISTTIMEFORMAT", out)
        self.assertIn("无耗时字段", out)
        self.assertIn("git status", out)

    def test_powershell_file(self):
        with tmp_file(PS_FILE) as path:
            rc, out, _ = run_cli(["--file", path, "--top", "3"])
        self.assertEqual(rc, 0)
        self.assertIn("格式: PowerShell", out)
        self.assertIn("python build.py", out)  # count 2 → rank 1 by freq

    def test_threshold_flag(self):
        with tmp_file(": 1672500000:1;pip install aaa\n" * 4) as path:
            rc_hi, out_hi, _ = run_cli(["--file", path, "--threshold", "5"])
            rc_lo, out_lo, _ = run_cli(["--file", path, "--threshold", "4"])
        self.assertEqual(rc_hi, 0)
        self.assertIn("未发现需要优化的重复模式", out_hi)
        self.assertEqual(rc_lo, 0)
        self.assertIn("连续执行 4 次", out_lo)

    def test_force_format(self):
        with tmp_file("git status\nls\n") as path:
            rc, out, err = run_cli(["--file", path, "--format", "zsh"])
        self.assertEqual(rc, 1)
        self.assertIn("未解析到任何命令", err)


class TestCliAi(unittest.TestCase):
    def test_incomplete_ai_config_falls_back(self):
        # endpoint without key: no network attempted, rule engine still shown
        with mock.patch("timesink.cli.safe_ai_suggest", return_value=(None, "需同时提供 --ai-endpoint 与 --ai-key")):
            rc, out, err = run_cli(["--demo", "--ai-endpoint", "http://127.0.0.1:1/v1"])
        self.assertEqual(rc, 0)
        self.assertIn("已回退规则引擎", err)
        self.assertIn("建议（规则引擎）", out)

    def test_ai_success_prints_section(self):
        with mock.patch(
            "timesink.cli.safe_ai_suggest",
            return_value=("给 git 配个别名 gs=git status。", None),
        ):
            rc, out, _ = run_cli(["--demo", "--ai-endpoint", "http://x", "--ai-key", "k"])
        self.assertEqual(rc, 0)
        self.assertIn("AI 建议（LLM）", out)
        self.assertIn("gs=git status", out)

    def test_ai_failure_falls_back(self):
        with mock.patch(
            "timesink.cli.safe_ai_suggest",
            return_value=(None, "URLError: down"),
        ):
            rc, out, err = run_cli(["--demo", "--ai-endpoint", "http://x", "--ai-key", "k"])
        self.assertEqual(rc, 0)
        self.assertIn("AI 建议失败（URLError: down）", err)
        self.assertIn("规则引擎", out)


class TestCliMisc(unittest.TestCase):
    def test_top_default_15(self):
        rc, out, _ = run_cli(["--demo"])
        self.assertIn("Top 15 命令", out)

    def test_version(self):
        with self.assertRaises(SystemExit) as cm:
            run_cli(["--version"])
        self.assertEqual(cm.exception.code, 0)

    def test_help(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as cm:
            main(["--help"])
        self.assertEqual(cm.exception.code, 0)
        self.assertIn("usage", out.getvalue())


if __name__ == "__main__":
    unittest.main()