from pathlib import Path


def test_local_gui_files_exist() -> None:
    root = Path(__file__).resolve().parents[2]
    assert (root / "local" / "gui.py").is_file()
    html = (root / "local" / "admin.html").read_text(encoding="utf-8")
    assert "Админ закрытого чата" in html
    assert "Локальная панель" in html
