"""Deterministic built-in demo dataset (zsh EXTENDED_HISTORY shape).

One fixed night of work: 2022-12-31 22:00 UTC → 2023-01-01 02:13 UTC,
deliberately crossing midnight so the 24h heat bar has life in buckets
22..02. Includes a 6-run ``git status`` burst, a 5-run ``npm run test``
burst and a 4-run ``pytest -q`` burst (below the default threshold — good
for eyeballing the suggestion engine's threshold behaviour).
"""
from __future__ import annotations

from typing import List, Tuple

from .model import Entry

_BASE = 1672524000  # 2022-12-31T22:00:00Z

# (offset_seconds_from_base, elapsed_seconds, command)
DEMO: Tuple[Tuple[int, int, str], ...] = (
    # 22:00 — cd / git burst (6 consecutive git)
    (0, 12, "cd ~/work/timesink"),
    (12, 38, "git status"),
    (50, 45, "git status"),
    (95, 60, "git status"),
    (155, 30, "git status"),
    (185, 75, "git status"),
    (260, 90, "git status"),
    (350, 180, "vim README.md"),
    (530, 300, "npm install -D vitest"),
    # 22:13 — npm run test burst (5 consecutive)
    (830, 45, "npm run test"),
    (875, 52, "npm run test"),
    (927, 61, "npm run test"),
    (988, 48, "npm run test"),
    (1036, 77, "npm run test"),
    (1113, 25, "cd .."),
    # 22:19 — pytest burst (4 consecutive, below threshold)
    (1138, 40, "pytest -q"),
    (1178, 55, "pytest -q"),
    (1233, 66, "pytest -q"),
    (1299, 88, "pytest -q"),
    (1387, 240, "python tools/gen_data.py"),
    (1627, 540, "python tools/gen_data.py"),
    (2167, 1200, "python analysis.py"),
    # 23:00 — git work again (three consecutive git, then a long pytest)
    (3600, 180, "git diff --stat"),
    (3780, 90, "git add -A"),
    (3870, 150, "git commit -m 'wip: heatmap'"),
    (4020, 300, "python -m pytest --benchmark --durations=5"),
    (4320, 60, "git log --oneline -10"),
    # 00:11 (Jan 1) — after midnight
    (7860, 120, "cd ~/work/timesink"),
    (7980, 45, "git status"),
    (8025, 360, "npm run build"),
    (8385, 600, "pytest -q --slow"),
    # 01:07
    (11220, 45, "git status"),
    (11265, 90, "git status"),
    (11355, 120, "cd .."),
    # 02:12
    (15120, 180, "vim notes.md"),
    (15300, 240, "python tools/report.py"),
)


def demo_entries() -> List[Entry]:
    return [
        Entry(cmd=cmd, ts=_BASE + off, elapsed=el, src="zsh")
        for off, el, cmd in DEMO
    ]


def demo_text() -> str:
    """The demo dataset serialised in raw zsh EXTENDED_HISTORY format."""
    return "".join(f": {_BASE + off}:{el};{cmd}\n" for off, el, cmd in DEMO)