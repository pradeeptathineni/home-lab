#!/usr/bin/env python3
"""record one bounded mlflow tracking run"""

from __future__ import annotations

import mlflow


def main() -> None:
    mlflow.set_tracking_uri("http://127.0.0.1:5000")
    mlflow.set_experiment("home-lab-smoke")
    with mlflow.start_run(run_name="service-check") as run:
        mlflow.log_param("source", "repository-smoke")
        mlflow.log_metric("healthy", 1.0)
        mlflow.set_tag("purpose", "tracking-path-proof")
        print(run.info.run_id)


if __name__ == "__main__":
    main()
