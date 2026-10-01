from __future__ import annotations

import io
import json
import subprocess
import urllib.error
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from benchmarks.fault import run as fault
from labctl import lima, sandbox
from labctl.runner import CommandRunner


def test_sandbox_name_can_never_target_primary() -> None:
    assert sandbox.NODE_NAME != lima.NODE_NAME
    assert sandbox.destroy_command() == ["limactl", "delete", "home-lab-sandbox"]


def test_destroy_requires_explicit_approval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sandbox, "state", lambda: "stopped")
    monkeypatch.setattr(sandbox.sys.stdin, "isatty", lambda: False)
    with pytest.raises(RuntimeError, match="requires --yes"):
        sandbox.destroy(CommandRunner(), approved=False)


def test_state_reports_absent_running_and_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sandbox, "_list", lambda: [])
    assert sandbox.state() == "absent"
    monkeypatch.setattr(
        sandbox, "_list", lambda: [{"name": sandbox.NODE_NAME, "status": "Running"}]
    )
    assert sandbox.state() == "running"
    monkeypatch.setattr(
        sandbox, "_list", lambda: [{"name": sandbox.NODE_NAME, "status": "Stopped"}]
    )
    assert sandbox.state() == "stopped"


def test_create_dry_run_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    template = tmp_path / "infra" / "lima"
    template.mkdir(parents=True)
    (template / "sandbox.yaml").write_text("mounts: []\nportForwards: []\n")
    monkeypatch.setattr(sandbox, "state", lambda: "absent")
    assert sandbox.create(tmp_path, CommandRunner(dry_run=True)) == 0
    output = capsys.readouterr().out
    assert "--name home-lab-sandbox" in output
    assert "--mount-only" not in output


def test_template_has_no_host_mount_or_port_forward() -> None:
    root = Path(__file__).resolve().parents[2]
    template = (root / "infra" / "lima" / "sandbox.yaml").read_text()
    assert "mounts: []" in template
    assert "portForwards: []" in template
    assert "plain: true" in template
    assert "overVsock: false" in template


def test_fault_percentile_uses_bounded_nearest_rank() -> None:
    assert fault._percentile(list(range(1, 21)), 0.95) == 19
    assert fault._percentile([], 0.95) is None


def test_fault_measurement_keeps_errors_toxic_config_and_recovery(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    def urlopen(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls % 2:
            return Response(b'{"status":"synthetic-ok"}')
        raise urllib.error.URLError("synthetic failure")

    monkeypatch.setattr(fault.urllib.request, "urlopen", urlopen)
    toxic = {"proxy_enabled": True, "toxics": []}
    scenario = fault._measure("recovery", toxic)
    assert scenario["successes"] == scenario["failures"] == 10
    assert scenario["aggregate"]["failure_rate"] == 0.5
    assert scenario["toxic_configuration"] == toxic
    assert scenario["scenario"] == "recovery"


def test_fault_schema_accepts_recovery_result(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.close()

    monkeypatch.setattr(
        fault.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: Response(b'{"status":"synthetic-ok"}'),
    )
    scenario = fault._measure("recovery", {"proxy_enabled": True})
    payload = {
        "schema_version": "1",
        "experiment": "synthetic-http-dependency-degradation",
        "timestamp": "2026-09-30T20:00:00+00:00",
        "sandbox_version": "test",
        "toxiproxy_version": "2.12.0",
        "scenarios": [scenario] * 5,
        "recovery_success": True,
        "caveats": [],
    }
    root = Path(__file__).resolve().parents[2]
    schema = json.loads((root / "benchmarks" / "schema" / "fault-http.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def test_verify_surfaces_primary_reachability_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        sandbox,
        "node_record",
        lambda: {
            "status": "running",
            "config": {"plain": True, "mounts": [], "portForwards": [], "networks": []},
        },
    )
    guest = {
        "dns": {"resolved": True},
        "internet_egress": {"reachable": True},
        "primary_vm_dns": {"resolved": True},
        "primary_vm_caddy": {"reachable": False},
        "mac_host_dns": {"resolved": True},
        "mac_host_owned_port": {"reachable": True},
        "host_mounts": [],
        "docker_socket_present": False,
        "primary_state_present": False,
    }
    monkeypatch.setattr(
        sandbox.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, json.dumps(guest), ""),
    )
    monkeypatch.setattr(sandbox, "_probe_dynamic_forwarding", lambda: False)
    assert sandbox.verify(tmp_path / "home-lab") == 1
