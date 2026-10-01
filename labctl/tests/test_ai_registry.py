from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from labctl import ai


def _write_registry(
    root: Path,
    *,
    model_id: str = "tiny-model",
    expected_bytes: int = 4,
    budget: int = 100,
    license_name: str = "Apache-2.0",
) -> Path:
    config = root / "config"
    config.mkdir()
    digest = hashlib.sha256(b"tiny").hexdigest()
    (config / "ai-models.toml").write_text(
        f"""registry_version = 1
download_budget_bytes = {budget}

[[models]]
id = "{model_id}"
role = "generation"
family = "test"
source = "owner/repository"
revision = "0123456789abcdef"
file = "tiny.gguf"
quantization = "Q4_K_M"
license = "{license_name}"
expected_bytes = {expected_bytes}
sha256 = "{digest}"
compatibility = "test fixture"
projector_required = false
"""
    )
    return root


def test_real_registry_is_valid() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = ai.load_registry(root)
    assert {model.role for model in registry.models} == {"generation", "embedding"}
    assert sum(model.expected_bytes for model in registry.models) < 7 * 1024**3


def test_registry_rejects_duplicate_ids(tmp_path: Path) -> None:
    repo = _write_registry(tmp_path)
    path = repo / "config" / "ai-models.toml"
    entry = path.read_text().split("[[models]]", maxsplit=1)[1]
    path.write_text(path.read_text() + "\n[[models]]" + entry)
    with pytest.raises(ValueError, match="duplicate"):
        ai.load_registry(repo)


def test_registry_rejects_missing_license(tmp_path: Path) -> None:
    repo = _write_registry(tmp_path, license_name="")
    with pytest.raises(ValueError, match="source and license"):
        ai.load_registry(repo)


def test_registry_enforces_budget(tmp_path: Path) -> None:
    repo = _write_registry(tmp_path, expected_bytes=101, budget=100)
    with pytest.raises(ValueError, match="download budget"):
        ai.load_registry(repo)


def test_model_root_override_must_be_absolute(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME_LAB_MODEL_ROOT", "relative/models")
    with pytest.raises(ValueError, match="absolute"):
        ai.model_root()


def test_model_path_stays_below_root(tmp_path: Path) -> None:
    repo = _write_registry(tmp_path)
    model = ai.load_registry(repo).models[0]
    assert ai.model_path(model, tmp_path / "models").is_relative_to(tmp_path / "models")


def test_existing_valid_artifact_is_reused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    repo = _write_registry(tmp_path)
    model_root = tmp_path / "models"
    monkeypatch.setenv("HOME_LAB_MODEL_ROOT", str(model_root))
    model = ai.load_registry(repo).models[0]
    destination = ai.model_path(model)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"tiny")

    from labctl.runner import CommandRunner

    assert ai.fetch(repo, CommandRunner(), model.id) == 0
    assert "reusing verified model" in capsys.readouterr().out


def test_digest_mismatch_fails_without_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _write_registry(tmp_path)
    model_root = tmp_path / "models"
    monkeypatch.setenv("HOME_LAB_MODEL_ROOT", str(model_root))
    model = ai.load_registry(repo).models[0]
    destination = ai.model_path(model)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(b"nope")

    from labctl.runner import CommandRunner

    with pytest.raises(RuntimeError, match="digest-mismatch"):
        ai.fetch(repo, CommandRunner(), model.id)
    assert destination.read_bytes() == b"nope"


def test_download_disable_flag_is_enforced(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _write_registry(tmp_path)
    monkeypatch.setenv("HOME_LAB_MODEL_ROOT", str(tmp_path / "models"))
    monkeypatch.setenv("HOME_LAB_ALLOW_MODEL_DOWNLOADS", "0")

    from labctl.runner import CommandRunner

    with pytest.raises(RuntimeError, match="disabled"):
        ai.fetch(repo, CommandRunner(), "tiny-model")


def test_unknown_model_is_rejected(tmp_path: Path) -> None:
    repo = _write_registry(tmp_path)
    with pytest.raises(ValueError, match="unknown model"):
        ai.load_registry(repo).get("not-registered")
