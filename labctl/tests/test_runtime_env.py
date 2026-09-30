from scripts.init_runtime_env import create, ensure


def test_runtime_env_is_created_once_with_private_permissions(tmp_path) -> None:
    destination = tmp_path / "runtime.env"
    assert create(destination)
    first = destination.read_text()
    assert "HOMARR_SECRET_ENCRYPTION_KEY=" in first
    assert destination.stat().st_mode & 0o777 == 0o600
    assert not create(destination)
    assert destination.read_text() == first


def test_runtime_env_adds_new_keys_without_replacing_values(tmp_path) -> None:
    destination = tmp_path / "runtime.env"
    destination.write_text("PIHOLE_PASSWORD=keep-this\n")

    assert ensure(destination) == "updated"
    payload = destination.read_text()
    assert "PIHOLE_PASSWORD=keep-this\n" in payload
    assert "OPEN_WEBUI_ADMIN_PASSWORD=" in payload
    assert ensure(destination) == "already complete"
