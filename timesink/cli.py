"""timesink CLI: argparse front end, report assembly, deterministic output."""
from __future__ import annotations

import argparse
import datetime
import sys
from typing import List, Optional

from . import __version__
from . import parse as parse_mod
from .ai import DEFAULT_MODEL, safe_ai_suggest
from .analyze import (
    has_elapsed,
    heat_buckets,
    suggest,
    time_range,
    top_n,
    total_tracked,
)
from .demo import demo_entries
from .model import FORMATS
from .render import fmt_duration, render_heat, render_suggestions, render_table


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="timesink",
        description="终端时间去向复盘：解析 zsh / bash / PowerShell 历史文件，"
        "输出 Top-N 命令、24 小时时段热力与自动化建议。",
        epilog="示例：python -m timesink（内置演示数据）；"
        "python -m timesink --file ~/.zsh_history",
    )
    p.add_argument(
        "--demo",
        action="store_true",
        help="使用内置确定性演示数据（默认行为；提供 --file 时忽略）。",
    )
    p.add_argument(
        "--file",
        metavar="PATH",
        help="历史文件路径（显式传参；zsh/.bash_history/ConsoleHost_history.txt 均可，格式自动识别）。",
    )
    p.add_argument(
        "--format",
        choices=FORMATS,
        default="auto",
        help="历史格式：auto 自动识别（默认）、zsh、bash、powershell。",
    )
    p.add_argument(
        "--top",
        type=int,
        default=15,
        metavar="N",
        help="Top-N 命令条数（默认 15）。",
    )
    p.add_argument(
        "--sort",
        choices=("auto", "time", "freq"),
        default="auto",
        help="排序键：auto=有耗时按总耗时否则按频次（默认）、time=总耗时、freq=频次。",
    )
    p.add_argument(
        "--threshold",
        type=int,
        default=5,
        metavar="N",
        help="重复前缀建议阈值：同一前缀连续出现 >=N 次触发建议（默认 5）。",
    )
    p.add_argument(
        "--tz",
        choices=("utc", "local"),
        default="utc",
        help="热力时段时区：utc=可跨机器复现（默认）、local=本机时区。",
    )
    p.add_argument(
        "--ai-endpoint",
        metavar="URL",
        help="OpenAI 兼容 chat completions 端点（与 --ai-key 同时提供才联网；失败自动回退规则引擎）。",
    )
    p.add_argument(
        "--ai-key",
        metavar="KEY",
        help="API 密钥（Bearer）。",
    )
    p.add_argument(
        "--ai-model",
        default=DEFAULT_MODEL,
        metavar="NAME",
        help=f"AI 模型名（默认 {DEFAULT_MODEL}）。",
    )
    p.add_argument(
        "--version",
        action="version",
        version=f"timesink {__version__}",
    )
    return p


def _fmt_ts(ts: int, tz: str) -> str:
    if tz == "local":
        dt = datetime.datetime.fromtimestamp(ts)
        suffix = datetime.datetime.now().astimezone().tzname() or "local"
    else:
        dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
        suffix = "UTC"
    return f"{dt:%Y-%m-%d %H:%M:%S} {suffix}"


def build_report(args: argparse.Namespace, entries: List, fmt: str) -> str:
    rows = top_n(entries, args.top, args.sort)
    total, has_t = total_tracked(entries)
    rng = time_range(entries)
    heat = heat_buckets(entries, args.tz) if rng else []
    sugs = suggest(entries, args.threshold)

    out = [f"timesink {__version__} · 终端时间去向复盘"]
    kind = {"zsh": "zsh EXTENDED_HISTORY", "bash": "bash HISTTIMEFORMAT", "powershell": "PowerShell"}.get(
        fmt, fmt
    )
    out.append(f"格式: {kind} · 命令条数: {len(entries)}")
    if rng:
        out.append(f"时间范围: {_fmt_ts(rng[0], args.tz)} → {_fmt_ts(rng[1], args.tz)}")
    out.append("")
    if has_t:
        out.append(f"追踪时长估算: 总计 {fmt_duration(total)}（zsh elapsed 求和）")
    else:
        out.append("追踪时长估算: 该格式无耗时字段，仅能做频次分析")
    out.append("")

    if heat:
        out.append(f"时段热力 24h（{args.tz.upper()}，按{'耗时' if has_elapsed(entries) else '频次'}）:")
        out.append(render_heat(heat))
        out.append("")

    out.append(render_table(rows, args.top, has_t, args.sort))
    out.append("")
    out.append(render_suggestions(sugs))
    return "\n".join(out)


def _force_utf8_stdio() -> None:
    """Keep Chinese output safe even when stdout/stderr are piped on Windows
    (ANSI code pages would otherwise raise UnicodeEncodeError)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv: Optional[List[str]] = None) -> int:
    _force_utf8_stdio()
    args = build_parser().parse_args(argv)

    if args.file:
        try:
            entries, fmt = parse_mod.load_file(args.file, args.format)
        except OSError as exc:
            print(f"错误：无法读取历史文件 {args.file}：{exc}", file=sys.stderr)
            return 1
        if not entries:
            print(f"错误：{args.file} 中未解析到任何命令记录。", file=sys.stderr)
            return 1
    else:
        entries = demo_entries()
        fmt = "zsh"
        if sys.stderr:
            sys.stderr.write(
                "提示：未提供 --file，使用内置演示数据；对真实历史用 --file 指定路径。\n"
            )

    report = build_report(args, entries, fmt)

    ai_text: Optional[str] = None
    if args.ai_endpoint or args.ai_key:
        text, err = safe_ai_suggest(
            top_n(entries, args.top, args.sort), args.ai_endpoint, args.ai_key, args.ai_model
        )
        if text is not None:
            ai_text = text
        else:
            sys.stderr.write(f"AI 建议失败（{err}），已回退规则引擎。\n")

    if ai_text is not None:
        report += "\n\nAI 建议（LLM）:\n" + ai_text

    print(report)
    return 0


def entry() -> None:
    sys.exit(main())


if __name__ == "__main__":
    entry()