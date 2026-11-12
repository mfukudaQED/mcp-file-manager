"""UI v29 compact file cards, metadata, and immutable UI v28 compatibility."""

import hashlib
from pathlib import Path

from mcp_file_viewer import extension as ext
from mcp_file_viewer.extension import (
    UI_URI, V28_UI_URI, UI_V28_META, UI_V29_META, register_file_viewer,
)


class Registry:
    """Store registered MCP UI and tool metadata without a running service."""

    def __init__(self):
        """Create the resource and tool catalogs."""
        self.resources = {}
        self.resource_meta = {}
        self.tools = {}

    def resource(self, uri, **kwargs):
        """Return a decorator that records a UI resource."""
        self.resource_meta[uri] = kwargs.get("meta", {})

        def bind(fn):
            """Retain the resource callback."""
            self.resources[uri] = fn
            return fn

        return bind

    def tool(self, name, **kwargs):
        """Return a decorator that records a tool and its UI metadata."""
        self.tools[name] = kwargs.get("meta", {})
        return lambda fn: fn


def test_v29_inline_resource_and_legacy_v28(tmp_path: Path, monkeypatch):
    """Verify compact default and separately preserved v28 full viewer."""
    monkeypatch.setattr(ext, "resolve_host_defaults",
                        lambda: ("ohtaka", "ohtaka", "ohtaka"))
    registry = Registry()
    register_file_viewer(registry, roots=(tmp_path,))
    assert UI_URI == "ui://mcp-file-manager/v29/app.html"
    assert V28_UI_URI == "ui://mcp-file-manager/v28/app.html"
    assert registry.resource_meta[UI_URI] == UI_V29_META
    assert registry.resource_meta[V28_UI_URI] == UI_V28_META
    assert UI_V29_META["openai/ui"]["preferredDisplayMode"] == "inline"
    assert UI_V28_META["openai/ui"]["preferredDisplayMode"] == "fullscreen"
    assert registry.tools["file_viewer_open"]["ui"]["resourceUri"] == UI_URI
    assert registry.tools["file_manager_panel"]["ui"]["resourceUri"] == UI_URI

    html = registry.resources[UI_URI]()
    assert "UI v29" in html
    assert 'id="launch-card"' in html
    assert 'id="launch-open"' in html
    assert 'id="viewer-shell" class="viewer-shell" hidden' in html
    assert 'data-host="ohtaka"' in html
    assert "__MCPFM_V29_HOST__" not in html
    assert "__MCPFM_V26_" not in html
    assert "requestDisplayMode" in html

    preserved = registry.resources[V28_UI_URI]()
    assert "UI v28" in preserved
    assert 'id="launch-card"' not in preserved
    assert hashlib.sha256(Path("src/mcp_file_viewer/ui/app_v28.html").read_bytes()).hexdigest() == (
        "171bcbf50e134495f6362639b5c00b02de7a941bfe4b5041508c1982895c4361"
    )


def test_v29_host_escapes_template_data(tmp_path: Path, monkeypatch):
    """Ensure a hostile hostname is never interpolated into HTML syntax."""
    monkeypatch.setattr(ext, "resolve_host_defaults",
                        lambda: ('evil"><script>', "sham", "sham"))
    registry = Registry()
    register_file_viewer(registry, roots=(tmp_path,))
    html = registry.resources[UI_URI]()
    assert 'data-host="evil&quot;&gt;&lt;script&gt;"' in html
    assert 'data-host="evil"><script>' not in html
