"""UI v21 defaults file identity/metadata to collapsed, preserving legacy UIs."""

from importlib.resources import files
from pathlib import Path

from mcp_file_viewer.extension import (
    UI_URI, V22_UI_URI, V21_UI_URI, V20_UI_URI, V19_UI_URI, V18_UI_URI, V17_UI_URI, V16_UI_URI,
    UI_V21_META, UI_V20_META, register_file_viewer,
)


def test_v21_file_details_are_collapsed_and_toggleable() -> None:
    """The existing info text remains intact, behind an accessible icon toggle."""
    html = files("mcp_file_viewer").joinpath("ui/app_v21.html").read_text("utf-8")
    assert V21_UI_URI == "ui://mcp-file-manager/v21/app.html"
    assert V22_UI_URI == "ui://mcp-file-manager/v22/app.html"
    assert UI_URI == "ui://mcp-file-manager/v23/app.html"
    assert "UI v21" in html
    assert '<div class="doc-head" id="file-details" hidden>' in html
    assert 'id="file-details-toggle"' in html
    assert 'aria-controls="file-details" aria-expanded="false"' in html
    assert 'aria-label="Show file details"' in html
    assert 'href="#icon-info"' in html
    for name in ('id="filename"', 'id="fullpath"', 'id="meta"'):
        assert name in html
    assert 'id="icon-tooltip" role="tooltip" hidden' in html
    assert 'id="status-panel" class="status-panel" hidden' in html
    for forbidden in ('id="transfer-download"', 'id="transfer-upload"'):
        assert forbidden not in html
    source = (Path(__file__).resolve().parents[1] / "frontend/src/main.ts").read_text("utf-8")
    assert "function setFileDetailsOpen(open: boolean)" in source
    assert 'details.hidden = !open;' in source
    assert 'toggle.setAttribute("aria-expanded", String(open))' in source
    assert 'setFileDetailsOpen(el("file-details").hidden)' in source
    assert 'el("meta").textContent' in source
    assert UI_V21_META == UI_V20_META


def test_v21_registration_retains_v16_through_v20(tmp_path) -> None:
    """Published UI resources remain separate; v22 is the default."""
    class Registry:
        def __init__(self):
            self.resources = {}
            self.meta = {}

        def resource(self, uri, **kwargs):
            def register(func):
                self.resources[uri] = func
                return func
            return register

        def tool(self, name, **kwargs):
            self.meta[name] = kwargs.get("meta", {})
            return lambda func: func

    reg = Registry()
    register_file_viewer(reg, roots=(tmp_path,))
    assert reg.meta["file_viewer_open"]["ui"]["resourceUri"] == UI_URI
    assert reg.meta["file_manager_panel"]["ui"]["resourceUri"] == UI_URI
    for uri, name in (
        (UI_URI, "UI v23"),
        (V22_UI_URI, "UI v22"),
        (V21_UI_URI, "UI v21"),
        (V20_UI_URI, "UI v20"),
        (V19_UI_URI, "UI v19"),
        (V18_UI_URI, "UI v18"),
        (V17_UI_URI, "UI v17"),
        (V16_UI_URI, "UI v16"),
    ):
        assert name in reg.resources[uri]()
