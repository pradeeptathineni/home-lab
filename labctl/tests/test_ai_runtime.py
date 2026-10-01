from __future__ import annotations

from pathlib import Path

from labctl import ai


def test_runtime_discovery_tolerates_optional_absence(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(ai.shutil, "which", lambda _name: None)
    monkeypatch.setattr(ai, "DEFAULT_LLAMA_BIN_DIR", tmp_path / "missing")
    identity = ai.runtime_identity()
    assert identity["llama_cli"] is None
    assert identity["ollama"] is None


def test_owned_process_requires_binary_and_model(monkeypatch) -> None:
    state = {"pid": 42, "model_path": "/models/known.gguf"}
    monkeypatch.setattr(
        ai,
        "_process_command",
        lambda _pid: "/usr/local/bin/llama-server --model /models/known.gguf",
    )
    assert ai._owned_process(state)
    monkeypatch.setattr(ai, "_process_command", lambda _pid: "python unrelated.py")
    assert not ai._owned_process(state)


def test_stop_does_not_kill_unowned_process(tmp_path: Path, monkeypatch) -> None:
    runtime = tmp_path / ".runtime"
    runtime.mkdir()
    (runtime / "ai-server.json").write_text('{"pid": 42, "model_path": "/models/known.gguf"}\n')
    monkeypatch.setattr(ai, "_process_command", lambda _pid: "python unrelated.py")

    from labctl.runner import CommandRunner

    try:
        ai.stop(tmp_path, CommandRunner())
    except RuntimeError as error:
        assert "ownership" in str(error)
    else:
        raise AssertionError("unowned process was accepted")


def test_route_ownership_requires_ssh_and_exact_socket(monkeypatch) -> None:
    state = {"pid": 77, "socket": ai.ROUTE_SOCKET}
    monkeypatch.setattr(
        ai,
        "_process_command",
        lambda _pid: f"/usr/bin/ssh -N -R {ai.ROUTE_SOCKET}:127.0.0.1:18080 lima-home-lab",
    )
    assert ai._owned_route(state)
    monkeypatch.setattr(ai, "_process_command", lambda _pid: "sleep 999")
    assert not ai._owned_route(state)
