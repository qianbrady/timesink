"""Aggregation, ranking, heat-bucket math and the rule-based suggestion engine.

All functions are pure (no I/O) so they are trivially unit-testable.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from .model import Entry


def aggregate(entries: List[Entry]) -> Dict[str, List[int]]:
    """Group by exact command string -> [count, total_elapsed]."""
    stats: Dict[str, List[int]] = {}
    for e in entries:
        s = stats.setdefault(e.cmd, [0, 0])
        s[0] += 1
        if e.elapsed is not None:
            s[1] += e.elapsed
    return stats


def has_elapsed(entries: List[Entry]) -> bool:
    return any(e.elapsed is not None for e in entries)


def sort_key(row: Tuple[str, int, int], use_time: bool) -> Tuple:
    cmd, cnt, tot = row
    primary = -tot if use_time else -cnt
    return (primary, -cnt, cmd)


def top_n(entries: List[Entry], n: int, sort: str = "auto") -> List[Tuple[str, int, int]]:
    """Return top-N (cmd, count, total_elapsed) rows.

    sort: "auto" -> by total elapsed when available else by frequency;
    "time" -> by elapsed (falls back to frequency when no elapsed data);
    "freq" -> always by frequency.
    """
    stats = aggregate(entries)
    rows = [(cmd, s[0], s[1]) for cmd, s in stats.items()]
    use_time = has_elapsed(entries)
    if sort == "freq":
        use_time = False
    elif sort == "time" and not use_time:
        use_time = False
    rows.sort(key=lambda r: sort_key(r, use_time))
    return rows[: n if n >= 0 else len(rows)]


def total_tracked(entries: List[Entry]) -> Tuple[int, bool]:
    """Sum of elapsed seconds when any exists; (0, False) otherwise."""
    total = sum(e.elapsed for e in entries if e.elapsed is not None)
    return total, has_elapsed(entries)


def time_range(entries: List[Entry]) -> Optional[Tuple[int, int]]:
    ts = [e.ts for e in entries if e.ts is not None]
    if not ts:
        return None
    return (min(ts), max(ts))


_LOCALTIME: Callable[[float], "time.struct_time"] = time.localtime


def heat_buckets(entries: List[Entry], tz: str = "utc") -> List[int]:
    """24 ints, one per hour-of-day bucket.

    Weights: elapsed seconds when the format carries them, else 1 per entry
    (frequency mode). Hour is derived with :func:`time.gmtime` for "utc"
    (deterministic across machines) or :func:`time.localtime` for "local".
    Bucketing by hour-of-day makes entries that cross midnight land in their
    own hour naturally (23:59:59 -> bucket 23, 00:00:01 -> bucket 0).
    """
    f = _LOCALTIME if tz == "local" else time.gmtime
    values = [0] * 24
    for e in entries:
        if e.ts is None:
            continue
        hour = f(e.ts).tm_hour
        values[hour] += e.elapsed if e.elapsed is not None else 1
    return values


def first_token(cmd: str) -> str:
    parts = cmd.split()
    return parts[0] if parts else ""


@dataclass(frozen=True)
class Suggestion:
    """Rule-engine finding: a command prefix seen repeatedly in a row."""

    prefix: str
    max_run: int          # longest consecutive run length
    total: int            # total occurrences (all runs merged)
    distinct: Tuple[str, ...]  # distinct full commands inside the runs
    all_same: bool        # every command in the runs is identical


def suggest(entries: List[Entry], threshold: int = 5) -> List[Suggestion]:
    """Same-prefix consecutive-run detector.

    Scans the *chronological* command sequence (file order); whenever the
    first token of the command stays the same for >= threshold consecutive
    entries, a suggestion is triggered. Runs are then merged per prefix
    (max run length + total occurrences), so a prefix that appears in several
    bursts is reported once with its worst-case burst.
    """
    runs: List[Tuple[str, int, List[Entry]]] = []
    cur_prefix: Optional[str] = None
    cur_run: List[Entry] = []
    for e in entries:
        p = first_token(e.cmd)
        if p != cur_prefix:
            if cur_run:
                runs.append((cur_prefix or "", len(cur_run), cur_run))
            cur_prefix = p
            cur_run = [e]
        else:
            cur_run.append(e)
    if cur_run:
        runs.append((cur_prefix or "", len(cur_run), cur_run))

    merged: Dict[str, Dict] = {}
    for prefix, run_len, run_entries in runs:
        if run_len < threshold:
            continue
        cmds = tuple(e.cmd for e in run_entries)
        m = merged.setdefault(
            prefix, {"max_run": 0, "total": 0, "distinct": set(), "all_same": True}
        )
        m["max_run"] = max(m["max_run"], run_len)
        m["total"] += run_len
        m["distinct"].update(cmds)
        # all_same only when every command across ALL qualifying runs is identical
        m["all_same"] = len(m["distinct"]) == 1

    out = []
    for prefix, m in merged.items():
        out.append(
            Suggestion(
                prefix=prefix,
                max_run=m["max_run"],
                total=m["total"],
                distinct=tuple(sorted(m["distinct"])),
                all_same=m["all_same"],
            )
        )
    out.sort(key=lambda s: (-s.max_run, -s.total, s.prefix))
    return out