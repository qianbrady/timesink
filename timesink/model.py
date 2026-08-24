"""Core data model: one log entry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

FORMATS = ("auto", "zsh", "bash", "powershell")


@dataclass(frozen=True)
class Entry:
    """A single recorded shell command.

    ts      — unix epoch seconds (int) when the command started, or None when
               the history format does not carry timestamps (PowerShell).
    elapsed — duration of the command in seconds, or None when unknown
               (bash HISTTIMEFORMAT, PowerShell).
    src     — "zsh" | "bash" | "powershell".
    """

    cmd: str
    ts: Optional[int] = None
    elapsed: Optional[int] = None
    src: str = "unknown"