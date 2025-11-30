"""Tests for shared UI helpers."""

from src.cli.ui.shared import create_bottom_toolbar


def test_create_bottom_toolbar_escapes_working_dir(mock_context, monkeypatch):
    """Ensure working directory is escaped before embedding in HTML."""
    monkeypatch.setattr("src.cli.ui.shared.get_version", lambda: "0.0.0")

    working_dir = "example/<foo&bar>"
    toolbar = create_bottom_toolbar(mock_context, working_dir)

    assert "example/&lt;foo&amp;bar&gt;" in toolbar.value
    assert "<foo&bar>" not in toolbar.value


def test_create_bottom_toolbar_accepts_path(mock_context, monkeypatch, tmp_path):
    """Path inputs should be converted to strings before escaping."""
    monkeypatch.setattr("src.cli.ui.shared.get_version", lambda: "0.0.0")

    working_dir = tmp_path / "<danger&chars>"
    toolbar = create_bottom_toolbar(mock_context, working_dir)

    assert "&lt;danger&amp;chars&gt;" in toolbar.value
