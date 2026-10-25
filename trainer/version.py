"""Which version of the code is running, so a stale server can be told apart from the files on disk.

Zip installs (the Windows launcher) carry the commit id in .update_sha. Git checkouts ask git.
Anything else falls back to a fingerprint of the source files' modification times.
"""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from trainer.config import PROJECT_ROOT


def current_version() -> str:
    sha_file = PROJECT_ROOT / ".update_sha"
    if sha_file.exists():
        v = sha_file.read_text().strip()
        if v:
            return v
    try:
        out = subprocess.run(["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    h = hashlib.sha1()
    for p in sorted((PROJECT_ROOT / "trainer").rglob("*.py")) + sorted((PROJECT_ROOT / "web").glob("*")):
        h.update(f"{p.relative_to(PROJECT_ROOT)}:{p.stat().st_mtime_ns}".encode())
    return "files-" + h.hexdigest()[:12]
