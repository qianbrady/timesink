"""History-format parsers: zsh EXTENDED_HISTORY, bash HISTTIMEFORMAT, PowerShell.

Every parser is a pure function over text lines; file I/O lives in
:func:`load_file`. Encoding is handled defensively (BOM sniffing) so the same
code works for PS 5.1's UTF-16 ConsoleHost_history.txt and modern UTF-8.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .model import Entry

_ZSH_RE = re.compile(r"^:\s+(\d+):(\d+);(.*)$")
_TS_RE = re.compile(r"^#(\d{9,11})\s*$")


def detect_format(text: str) -> str:
    """Guess the history format from the first non-empty line."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if _ZSH_RE.match(line):
            return "zsh"
        if _TS_RE.match(line):
            return "bash"
        return "powershell"
    return "powershell"


def parse_zsh(lines: List[str]) -> List[Entry]:
    """zsh EXTENDED_HISTORY: ``: <ts>:<elapsed>;<cmd>`` per line."""
    entries: List[Entry] = []
    for line in lines:
        line = line.rstrip("\n")
        m = _ZSH_RE.match(line)
        if not m:
            continue  # malformed / metadata lines are skipped, never fatal
        entries.append(
            Entry(
                cmd=m.group(3).strip(),
                ts=int(m.group(1)),
                elapsed=int(m.group(2)),
                src="zsh",
            )
        )
    return entries


def parse_bash(lines: List[str]) -> List[Entry]:
    """bash with HISTTIMEFORMAT: two-line groups ``#<ts>`` + ``<cmd>``.

    No elapsed data is recorded by bash (best effort: None).
    Blank lines and stray lines are tolerated; a trailing bare ``#ts``
    without a following command is ignored.
    """
    entries: List[Entry] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].rstrip("\n").strip()
        m = _TS_RE.match(line)
        if not m:
            i += 1
            continue
        ts = int(m.group(1))
        i += 1
        while i < n and lines[i].strip() == "":
            i += 1
        if i >= n:
            break  # dangling timestamp with no command
        cmd = lines[i].strip()
        if cmd and not _TS_RE.match(cmd):
            entries.append(Entry(cmd=cmd, ts=ts, elapsed=None, src="bash"))
        i += 1
    return entries


def parse_powershell(lines: List[str]) -> List[Entry]:
    """ConsoleHost_history.txt: plain command lines, frequency mode only."""
    entries: List[Entry] = []
    for line in lines:
        cmd = line.strip()
        if cmd:
            entries.append(Entry(cmd=cmd, ts=None, elapsed=None, src="powershell"))
    return entries


PARSERS = {
    "zsh": parse_zsh,
    "bash": parse_bash,
    "powershell": parse_powershell,
}


def _decode(raw: bytes) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16", errors="replace")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig", errors="replace")
    return raw.decode("utf-8", errors="replace")


def load_file(path: str, fmt: str = "auto") -> Tuple[List[Entry], str]:
    """Read a history file and return (entries, resolved_format).

    Raises OSError on unreadable files — CLI layer turns that into a friendly
    message instead of a traceback.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    text = _decode(raw)
    if fmt == "auto":
        fmt = detect_format(text)
    parser = PARSERS[fmt]
    entries = parser(text.splitlines())
    return entries, fmt