"""Optional LLM suggestion source (--ai-endpoint/--ai-key).

Zero third-party deps: we speak a minimal OpenAI-style chat-completions
protocol over urllib. Any failure (network down, bad key, non-JSON reply)
surfaces as ``(None, reason)`` so the CLI can always fall back to the
rule-based engine — the default is zero network.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import List, Optional, Tuple

DEFAULT_MODEL = "gpt-4o-mini"


def _build_prompt(rows: List[Tuple[str, int, int]], top: int) -> str:
    lines = ["以下是终端命令统计 Top %d（命令/次数/总耗时秒/平均秒）：" % top]
    for cmd, cnt, tot in rows:
        avg = (tot // cnt) if cnt else 0
        lines.append(f"- {cmd} | 次数={cnt} | 总耗时={tot}s | 平均={avg}s")
    lines.append(
        "请用中文给出 3-5 条可落地的自动化/别名/脚本化建议（例如 alias、"
        "git 别名、工作流脚本），保持简洁，不要复述统计数字。"
    )
    return "\n".join(lines)


def ai_suggest(
    rows: List[Tuple[str, int, int]],
    endpoint: str,
    key: str,
    model: str = DEFAULT_MODEL,
    timeout: int = 8,
) -> str:
    """POST to an OpenAI-compatible chat endpoint and return the content text.

    Raises on any failure; callers should use :func:`safe_ai_suggest`.
    """
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_prompt(rows, len(rows))}],
    }
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (user-supplied endpoint)
        body = json.loads(resp.read().decode("utf-8", "replace"))
    try:
        text = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(f"unexpected response shape: {exc}") from exc
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty assistant reply")
    return text.strip()


def safe_ai_suggest(
    rows: List[Tuple[str, int, int]],
    endpoint: Optional[str],
    key: Optional[str],
    model: str = DEFAULT_MODEL,
    timeout: int = 8,
) -> Tuple[Optional[str], Optional[str]]:
    """Never raises. Returns (text, None) on success, (None, reason) on failure."""
    if not endpoint or not key:
        return None, "需同时提供 --ai-endpoint 与 --ai-key"
    try:
        return ai_suggest(rows, endpoint, key, model, timeout), None
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"{type(exc).__name__}: {exc}"