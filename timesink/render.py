"""ASCII rendering: duration formatting, Top-N table, 24h heat bar, suggestions.

All output is plain text (no ANSI) so it is safe to redirect into files or
paste into chat; only Unicode block characters are used for the heat bar.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .analyze import Suggestion

LEVEL_CHARS = "▁▂▃▄▅▆▇█"  # 8 intensities, minimum visible


def fmt_duration(seconds: Optional[int]) -> str:
    """Human duration: ``1h02m03s`` / ``45m00s`` / ``12s`` / ``0s``."""
    if seconds is None:
        return "–"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def truncate(cmd: str, width: int = 44) -> str:
    if len(cmd) <= width:
        return cmd
    return cmd[: width - 1] + "…"


def heat_line(values: List[int]) -> str:
    """Map 24 bucket values to one 24-char intensity line."""
    peak = max(values) if values else 1
    peak = peak or 1
    out = []
    for v in values:
        idx = min(7, v * 8 // peak)
        out.append(LEVEL_CHARS[idx])
    return "".join(out)


HEAT_TICKS = "0   4   8   12  16  20  "  # 24 chars, aligned under the 24 buckets


def render_heat(values: List[int]) -> str:
    legend = "▁=最闲 █=最忙"
    if not values:
        return legend
    return heat_line(values) + "\n" + HEAT_TICKS + "\n" + legend


def render_table(
    rows: List[Tuple[str, int, int]], top: int, has_time: bool, sort: str = "auto"
) -> str:
    """Top-N table with stable, padding-based columns (no printf tricks)."""
    total_col = "TOTAL" if has_time else "TOTAL(无耗时)"
    lines = [f"Top {top} 命令 · 排序: {'总耗时' if has_time or sort == 'time' else '频次'}"]
    header = "  #  COUNT   TOTAL      AVG    COMMAND"
    lines.append(header)
    if not rows:
        lines.append("（无命令数据）")
        return "\n".join(lines)
    for rank, (cmd, cnt, tot) in enumerate(rows, start=1):
        avg = tot // cnt if has_time else None
        line = (
            f"{rank:>3}  {cnt:>5}  {fmt_duration(tot if has_time else None):<8}"
            f"  {fmt_duration(avg):<8}  {truncate(cmd)}"
        )
        lines.append(line)
    return "\n".join(lines)


def _alias_name(cmd: str) -> str:
    """Deterministic alias-name hint: initials of the command words, e.g.
    ``git status`` -> ``gs`` (only a suggestion; users may rename freely)."""
    name = "".join(w[0] for w in cmd.split() if w)[:6]
    return name or "x"


def render_suggestions(sugs: List[Suggestion]) -> str:
    if not sugs:
        return "建议: 未发现需要优化的重复模式（阈值内）。"
    lines = ["建议（规则引擎）:"]
    for s in sugs:
        sample = s.distinct[0] if s.all_same else s.prefix
        if s.all_same:
            lines.append(
                f"  - `{s.prefix}` 连续执行 {s.max_run} 次（累计 {s.total} 次），"
                f"且每次都是 `{sample}` → 建议配置 alias（如 `alias {_alias_name(sample)}='{sample}'`）"
            )
        else:
            lines.append(
                f"  - 前缀 `{s.prefix}` 连续出现 {s.max_run} 次（累计 {s.total} 次，"
                f"含 {len(s.distinct)} 种命令）→ 建议封装为脚本/工作流"
            )
    return "\n".join(lines)