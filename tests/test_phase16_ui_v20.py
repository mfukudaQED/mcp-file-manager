"""UI v20 SVG controls and collapsed status regression coverage."""

from importlib.resources import files
from pathlib import Path

from mcp_file_viewer.extension import (
    UI_URI, V22_UI_URI, V21_UI_URI, V20_UI_URI, V19_UI_URI, V18_UI_URI, V17_UI_URI, V16_UI_URI,
    UI_V21_META, UI_V20_META, UI_V19_META, register_file_viewer,
)


def test_v20_compact_svg_and_status() -> None:
    """V20 ships local icon symbols, compact controls, and default-hidden diagnostics."""
    html = files("mcp_file_viewer").joinpath("ui/app_v20.html").read_text("utf-8")
    assert V20_UI_URI == "ui://mcp-file-manager/v20/app.html"
    assert "UI v20" in html
    for icon in ("file-copy", "square-terminal", "folders", "panel-left", "activity"):
        assert 'id="icon-' + icon + '"' in html
    for button in ("copy-path", "copy-tabby", "copy-winscp", "explorer-toggle",
                   "open", "edit", "save", "history", "status-toggle"):
        assert 'id="' + button + '"' in html
    assert 'id="status-panel" class="status-panel" hidden' in html
    assert 'id="icon-tooltip" role="tooltip" hidden' in html
    assert "pointermove" in html and "focusin" in html
    assert 'aria-controls="status-panel" aria-expanded="false"' in html
    js_source = (Path(__file__).resolve().parents[1] / "frontend/src/main.ts").read_text("utf-8")
    assert 'button.setAttribute("aria-expanded", String(expanded))' in js_source
    assert "flashCopiedIcon" in js_source
    assert "navigator.clipboard" in js_source
    assert 'id="copy-fallback"' in html
    for forbidden in ('id="transfer-download"', 'id="transfer-upload"',
                      'id="transfer-cancel"', 'id="tabby-open"'):
        assert forbidden not in html
    assert 'src="http' not in html
    assert UI_V20_META == UI_V19_META


def test_v20_legacy_resources_are_distinct(tmp_path) -> None:
    """Ensure v16-v19 retain original resources and current tools use v20."""
    class Stub:
        def __init__(self):
            self.resources = {}
            self.tool_metadata = {}

        def resource(self, uri, **kwargs):
            def capture(fn):
                self.resources[uri] = fn
                return fn
            return capture

        def tool(self, name, **kwargs):
            self.tool_metadata[name] = kwargs.get("meta", {})
            return lambda fn: fn

    stub = Stub()
    register_file_viewer(stub, roots=(tmp_path,))
    assert stub.tool_metadata["file_viewer_open"]["ui"]["resourceUri"] == UI_URI
    assert stub.tool_metadata["file_manager_panel"]["ui"]["resourceUri"] == UI_URI
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
        assert name in stub.resources[uri]()
