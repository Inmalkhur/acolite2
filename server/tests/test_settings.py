import os
from pathlib import Path

from app.settings import resolve_data_dir


def test_data_dir_env_override(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "custom"))
    got = resolve_data_dir()
    assert got == (tmp_path / "custom").resolve()
    assert got.is_dir()


def test_data_dir_falls_back_when_hosted_unwritable(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    got = resolve_data_dir()
    assert got.is_dir()
    if not os.access("/app", os.W_OK):
        assert got == (tmp_path / "runtime").resolve()
