"""Verify offline math preview and the preserved historical UI resources."""

from hashlib import sha256

from mcp_file_viewer import extension
from mcp_file_viewer.extension import (
    UI_URI, V28_UI_URI, V27_UI_URI, V26_UI_URI, V23_UI_URI, V24_UI_URI, V25_UI_URI,
    UI_V29_META, UI_V28_META, UI_V27_META, UI_V26_META, UI_V23_META, UI_V24_META, UI_V25_META,
    register_file_viewer,
)


class Stub:
    """Collect resource and tool registrations without an MCP server."""

    def __init__(self):
        """Initialize the recorded registration maps."""
        self.resources = {}
        self.resource_meta = {}
        self.tools = {}

    def resource(self, uri, **kwargs):
        """Capture each registered UI resource."""
        self.resource_meta[uri] = kwargs.get("meta")

        def register(func):
            """Store one resource handler."""
            self.resources[uri] = func
            return func

        return register

    def tool(self, *args, **kwargs):
        """Capture tool-to-UI associations."""
        def register(func):
            """Store the UI metadata of one tool."""
            self.tools[kwargs.get("name", func.__name__)] = kwargs.get("meta")
            return func
        return register


def test_unified_ui_v27_preserves_math_and_legacy(tmp_path, monkeypatch):
    """Check common v26 resources and exact pre-unification bytes."""
    assert UI_URI == "ui://mcp-file-manager/v29/app.html"
    stub = Stub()
    register_file_viewer(stub, roots=(tmp_path,))
    for uri, meta in (
        (UI_URI, UI_V29_META), (V28_UI_URI, UI_V28_META), (V27_UI_URI, UI_V27_META), (V26_UI_URI, UI_V26_META), (V25_UI_URI, UI_V25_META),
        (V24_UI_URI, UI_V24_META), (V23_UI_URI, UI_V23_META),
    ):
        assert stub.resource_meta[uri] == meta
    assert "UI v29" in stub.resources[UI_URI]()
    assert "UI v28" in stub.resources[V28_UI_URI]()
    assert "katex" in stub.resources[UI_URI]().lower()
    assert "UI v27" in stub.resources[V27_UI_URI]()
    assert "UI v26" in stub.resources[V26_UI_URI]()
    assert "__MCPFM_V26_" not in stub.resources[UI_URI]()
    assert "__MCPFM_V26_" not in stub.resources[V26_UI_URI]()
    assert sha256(stub.resources[V23_UI_URI]().encode()).hexdigest() == (
        "3cf73ef1f76bef31e7b8aed69c3c907432cb421e341fe8fbe992eed73b0c037c"
    )
    assert sha256(stub.resources[V25_UI_URI]().encode()).hexdigest() == (
        "2eb8ba099a3454d2df09a7020f84c5d9c44f0793914be22067edddfa76f52d1c"
    )
    monkeypatch.setattr(extension, "resolve_host_defaults", lambda: ("sham", "sham", "sham"))
    assert sha256(stub.resources[V24_UI_URI]().encode()).hexdigest() == (
        "bbafb0e63a33e1cff371152da12a2643b30e63f8b3c59a39075942fc6274447a"
    )
    monkeypatch.setattr(extension, "resolve_host_defaults", lambda: ("ohtaka", "ohtaka", "ohtaka"))
    assert sha256(stub.resources[V24_UI_URI]().encode()).hexdigest() == (
        "723af3eb851154df5b9f52f62d2cca0f8e9a2ce339308429c2fd155fe3b310d7"
    )
    assert stub.tools["file_viewer_open"]["ui"]["resourceUri"] == UI_URI
    assert stub.tools["file_manager_panel"]["ui"]["resourceUri"] == UI_URI
