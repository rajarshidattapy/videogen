from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from pipeline.errors import PipelineError, ToolUnavailable


def require_executable(executable: str, label: str) -> None:
    if Path(executable).is_file() or shutil.which(executable):
        return
    raise ToolUnavailable(
        f"{label} is not available. Install it and set the matching environment variable "
        f"({label.upper().replace(' ', '_')}_BIN) to its executable path."
    )


def run_command(
    command: Iterable[str | Path], *, cwd: Path | None = None, label: str
) -> subprocess.CompletedProcess[str]:
    args = [str(item) for item in command]
    try:
        result = subprocess.run(
            args,
            cwd=str(cwd) if cwd else None,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
    except FileNotFoundError as exc:
        raise ToolUnavailable(f"{label} executable was not found: {args[0]}") from exc
    if result.returncode != 0:
        tail = (result.stdout or "").strip()[-2_000:]
        detail = f"\n{tail}" if tail else ""
        raise PipelineError(f"{label} failed (exit code {result.returncode}).{detail}")
    return result

