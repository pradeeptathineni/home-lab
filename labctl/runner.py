"""visible subprocess execution"""

from __future__ import annotations

import os
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CommandRunner:
    """print commands before running them"""

    dry_run: bool = False

    def run(
        self,
        command: Sequence[str],
        *,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        print(f"$ {shlex.join(str(part) for part in command)}", flush=True)
        if self.dry_run:
            return subprocess.CompletedProcess(command, 0, "", "")

        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        return subprocess.run(
            command,
            cwd=cwd,
            env=process_env,
            check=check,
            text=True,
        )
