"""Parser correctness for the three history formats + auto detection + BOM."""
import unittest

from timesink.parse import (
    detect_format,
    load_file,
    parse_bash,
    parse_powershell,
    parse_zsh,
)

try:  # unittest discover -s tests imports modules top-level; package mode otherwise
    from .util import tmp_file
except ImportError:
    from util import tmp_file

ZSH_SAMPLE = (
    ": 1672500000:12;cd ~/work\n"
    ": 1672500012:45;git status\n"
    ": 1672500057:0;true\n"
    ": 1672500057:120;python build.py --fast\n"
)
BASH_SAMPLE = (
    "#1672500000\n"
    "cd ~/work\n"
    "\n"
    "#1672500012\n"
    "git status\n"
    "#1672500099\n"
)
PS_SAMPLE = "Get-Process\n\n  set-location ..\npython build.py\n"


class TestParseZsh(unittest.TestCase):
    def test_basic_fields(self):
        entries = parse_zsh(ZSH_SAMPLE.splitlines())
        self.assertEqual(len(entries), 4)
        self.assertEqual(entries[1].cmd, "git status")
        self.assertEqual(entries[1].ts, 1672500012)
        self.assertEqual(entries[1].elapsed, 45)
        self.assertEqual(entries[1].src, "zsh")

    def test_zero_elapsed_is_kept(self):
        entries = parse_zsh(ZSH_SAMPLE.splitlines())
        self.assertEqual(entries[2].elapsed, 0)
        self.assertEqual(entries[2].cmd, "true")

    def test_malformed_lines_are_skipped(self):
        text = ": 1:2;ok\nnot a history line\n: broken;\n: 3:4;also ok\n"
        entries = parse_zsh(text.splitlines())
        self.assertEqual([e.cmd for e in entries], ["ok", "also ok"])
        self.assertEqual(entries[0].ts, 1)

    def test_empty_input(self):
        self.assertEqual(parse_zsh([]), [])


class TestParseBash(unittest.TestCase):
    def test_two_line_groups(self):
        entries = parse_bash(BASH_SAMPLE.splitlines())
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0].cmd, "cd ~/work")
        self.assertEqual(entries[0].ts, 1672500000)
        self.assertIsNone(entries[0].elapsed)
        self.assertEqual(entries[1].cmd, "git status")
        self.assertEqual(entries[1].src, "bash")

    def test_dangling_timestamp_ignored(self):
        entries = parse_bash(["#1672500000\n", "cd /\n", "#1672500099\n"])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].cmd, "cd /")

    def test_blank_lines_between_groups(self):
        text = "#1672500000\n\n\ncd /\n#1672500010\n\nls\n"
        entries = parse_bash(text.splitlines())
        self.assertEqual([e.cmd for e in entries], ["cd /", "ls"])


class TestParsePowerShell(unittest.TestCase):
    def test_plain_lines_only(self):
        entries = parse_powershell(PS_SAMPLE.splitlines())
        self.assertEqual([e.cmd for e in entries], ["Get-Process", "set-location ..", "python build.py"])
        for e in entries:
            self.assertIsNone(e.ts)
            self.assertIsNone(e.elapsed)
            self.assertEqual(e.src, "powershell")

    def test_empty_input(self):
        self.assertEqual(parse_powershell([]), [])


class TestDetect(unittest.TestCase):
    def test_detect_all_three(self):
        self.assertEqual(detect_format(ZSH_SAMPLE), "zsh")
        self.assertEqual(detect_format(BASH_SAMPLE), "bash")
        self.assertEqual(detect_format(PS_SAMPLE), "powershell")


class TestLoadFile(unittest.TestCase):
    def test_utf8_file_roundtrip(self):
        with tmp_file(": 1:2;echo 中文\n") as path:
            entries, fmt = load_file(path)
        self.assertEqual(fmt, "zsh")
        self.assertEqual(entries[0].cmd, "echo 中文")

    def test_utf16_bom_powershell(self):
        raw = "\ufeffGet-Process\nset-location ..\r\n".encode("utf-16-le")
        with tmp_file(raw, suffix=".txt") as path:
            entries, fmt = load_file(path)
        self.assertEqual(fmt, "powershell")
        self.assertEqual([e.cmd for e in entries], ["Get-Process", "set-location .."])

    def test_force_format_override(self):
        with tmp_file("git status\nls\n") as path:
            entries, fmt = load_file(path, fmt="zsh")
        self.assertEqual(fmt, "zsh")
        self.assertEqual(len(entries), 0)  # no : ts:el; lines → nothing parses

    def test_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            load_file("no/such/file.txt")


if __name__ == "__main__":
    unittest.main()