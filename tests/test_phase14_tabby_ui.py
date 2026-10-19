"""Regression tests for the UI v18 Tabby launch and transfer-button removal."""

from importlib.resources import files
from pathlib import Path

from mcp_file_viewer.extension import V18_UI_URI, V17_UI_URI


def test_tabby_launch_v18_bundle() -> None:
    """Ensure the new UI advertises only a safe, profile-based Tabby launch."""
    html = files("mcp_file_viewer").joinpath("ui/app_v18.html").read_text("utf-8")
    assert V18_UI_URI == "ui://mcp-file-manager/v18/app.html"
    assert "UI v18" in html
    assert 'id="tabby-profile"' in html
    assert 'id="tabby-open"' in html
    assert "tabby://profile?profileName=sham" in html
    assert "tabby://run" not in html
    for element in (
        'id="transfer-download"',
        'id="transfer-upload"',
        'id="transfer-cancel"',
        'id="transfer-file-picker"',
        'id="transfer-host-note"',
    ):
        assert element not in html


def test_tabby_launch_preserves_old_resource() -> None:
    """Verify the published v17 bundle remains a separate resource."""
    old = files("mcp_file_viewer").joinpath("ui/app_v17.html").read_bytes()
    new = files("mcp_file_viewer").joinpath("ui/app_v18.html").read_bytes()
    assert V17_UI_URI == "ui://mcp-file-manager/v17/app.html"
    assert b"UI v17" in old
    assert old != new


def test_v18_still_contains_old_profile_link() -> None:
    """Ensure old clients can still use the unchanged v18 resource."""
    html = files("mcp_file_viewer").joinpath("ui/app_v18.html").read_text("utf-8")
    assert 'id="tabby-open"' in html
    assert "tabby://profile?profileName=sham" in html
    assert 'id="copy-winscp"' not in html
