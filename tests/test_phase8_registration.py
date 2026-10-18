"""Check that editor tools are registered only when explicitly enabled."""
from pathlib import Path
from mcp_file_viewer.extension import register_file_viewer, UI_URI

class MCPStub:
    """Record registered MCP resources and callable tools."""
    def __init__(self):
        """Initialize registry."""
        self.tools = {}
        self.tool_meta = {}
        self.resources = {}
        self.resource_meta = {}

    def resource(self, uri, **kwargs):
        """Record resource registration and return an inert decorator."""
        def inner(func):
            """Bind the UI resource."""
            self.resources[uri] = func
            self.resource_meta[uri] = kwargs.get("meta", {})
            return func
        return inner

    def tool(self, name, **kwargs):
        """Record tool registration and return an inert decorator."""
        def inner(func):
            """Bind the tool callable."""
            self.tools[name] = func
            self.tool_meta[name] = kwargs.get("meta", {})
            return func
        return inner

def test_opt_in_registration(tmp_path: Path):
    """Keep writing disabled by default and register the editing tools when enabled."""
    first = MCPStub()
    register_file_viewer(first, roots=(tmp_path,))
    assert UI_URI == "ui://mcp-file-manager/v16/app.html"
    assert UI_URI in first.resources
    assert "file_manager_edit_save" not in first.tools
    assert "file_manager_edit_read" not in first.tools

    second = MCPStub()
    register_file_viewer(second, roots=(tmp_path,), enable_edit=True)
    assert "file_manager_edit_save" in second.tools
    assert "file_manager_edit_read" in second.tools

def test_registered_edit_tool_contract(tmp_path: Path):
    """Verify read, successful save and revision conflict return MCP JSON."""
    import json
    path = tmp_path / "trial.txt"
    path.write_text("first\n", encoding="utf-8")
    server = MCPStub()
    register_file_viewer(server, roots=(tmp_path,), enable_edit=True)
    result = json.loads(server.tools["file_manager_edit_read"](str(path)))
    assert result["content"] == "first\n"
    saved = json.loads(server.tools["file_manager_edit_save"](str(path), result["revision"], "second\n"))
    assert saved["changed"] is True
    stale = json.loads(server.tools["file_manager_edit_save"](str(path), result["revision"], "clobber\n"))
    assert stale["error"]["code"] == "file_changed"
    assert path.read_text() == "second\n"



def test_thread_entrypoint_is_separate_from_inline_file_open(tmp_path: Path):
    """The host launches a thread tab through a dedicated no-argument tool."""
    import json

    doc = tmp_path / "README.md"
    doc.write_text("# Example\n", encoding="utf-8")
    stub = MCPStub()
    register_file_viewer(stub, roots=(tmp_path,))
    panel_meta = stub.tool_meta["file_manager_panel"]
    assert panel_meta["ui"]["resourceUri"] == UI_URI
    assert {"type": "thread"} in panel_meta["openai/ui"]["entrypoints"]
    assert "openai/ui" not in stub.tool_meta["file_viewer_open"]
    panel_result = json.loads(stub.tools["file_manager_panel"]())
    assert panel_result == {"ui_available": True, "entrypoint": "thread"}
    opened = json.loads(stub.tools["file_viewer_open"](str(doc)))
    assert opened["path"] == str(doc)
    assert opened["kind"] == "markdown"
    outside = json.loads(stub.tools["file_viewer_open"]("/etc/passwd"))
    assert outside["error"]["code"] == "permission_denied"


def test_fullscreen_display_preference(tmp_path: Path):
    """ChatGPT may start the UI in fullscreen; inline remains supported."""
    from mcp_file_viewer.extension import UI_DISPLAY_META

    stub = MCPStub()
    register_file_viewer(stub, roots=(tmp_path,))
    assert stub.resource_meta[UI_URI] == UI_DISPLAY_META
    assert UI_DISPLAY_META["openai/ui"] == {
        "preferredDisplayMode": "fullscreen",
        "availableDisplayModes": ["inline", "fullscreen"],
    }
