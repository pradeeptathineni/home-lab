from scripts.restore_test import _digest, _is_local_repository


def test_local_repository_detection() -> None:
    assert _is_local_repository("/tmp/restic")
    assert _is_local_repository("file:///tmp/restic")
    assert not _is_local_repository("s3:s3.amazonaws.com/example")


def test_fixture_digest_is_stable(tmp_path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.write_text("same\n")
    second.write_text("same\n")
    assert _digest(first) == _digest(second)
