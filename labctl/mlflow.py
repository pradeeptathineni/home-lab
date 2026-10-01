"""log reviewed local evidence through the existing MLflow container"""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path

from labctl.compose import compose_command


def log_evidence(repo: Path, kind: str, artifacts: list[Path]) -> str | None:
    if not artifacts:
        raise ValueError("at least one MLflow artifact is required")
    for artifact in artifacts:
        if artifact.parent.resolve() != (repo / "benchmarks" / "results").resolve():
            raise ValueError("MLflow artifacts must come from ignored benchmark results")
        if not artifact.is_file():
            raise FileNotFoundError(artifact)
    container_paths = [f"/opt/home-lab/benchmarks/results/{path.name}" for path in artifacts]
    command = compose_command(
        repo,
        [
            "--profile",
            "ai",
            "exec",
            "-T",
            "mlflow",
            "python",
            "/opt/home-lab/mlflow-log.py",
            "--kind",
            kind,
            *container_paths,
        ],
    )
    print(f"$ {shlex.join(command)}", flush=True)
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode:
        print("MLflow is not active; evidence remains in ignored local JSON")
        return None
    run_ids = [
        line.strip()
        for line in result.stdout.splitlines()
        if re.fullmatch(r"[0-9a-f]{32}", line.strip())
    ]
    if not run_ids:
        print("MLflow accepted the evidence but did not return a parseable run ID")
        return None
    run_id = run_ids[-1]
    print(f"MLflow run: {run_id}")
    return run_id
