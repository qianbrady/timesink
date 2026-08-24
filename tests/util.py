"""Test helpers: temp fixture files under the workspace .build-tmp dir.

Sandbox rule: all test temp files live in ``D:\\earn money\\001\\.build-tmp``
under a per-test uuid subdir (self-created, self-cleaned). The root is derived
as the parent of the project root so it stays OUTSIDE the git repo and is
never committed. No ``tempfile.mkdtemp`` (the sandbox rejects its directory).
"""
import shutil
import uuid
from contextlib import contextmanager
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = PROJECT_ROOT.parent / ".build-tmp"


def _root() -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    return TMP_ROOT


@contextmanager
def tmp_file(content: str, suffix: str = ".txt"):
    """Write ``content`` into a fresh uuid subdir; yield its path; clean up."""
    if isinstance(content, str):
        raw = content.encode("utf-8")
    else:
        raw = bytes(content)
    sub = _root() / ("timesink-" + uuid.uuid4().hex[:12])
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / ("history" + suffix)
    path.write_bytes(raw)
    try:
        yield str(path)
    finally:
        shutil.rmtree(sub, ignore_errors=True)