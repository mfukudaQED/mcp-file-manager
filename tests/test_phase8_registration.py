"""Check that editor tools are registered only when explicitly enabled."""
from pathlib import Path
from mcp_file_viewer.extension import register_file_viewer, UI_URI

class MCPStub:
    """Record registered MCP resources and callable tools."""
    def __init__(self):
        """Initialize registry."""
        self.tools = {}
        self.resources = {}

    def resource(self, uri, **kwargs):
        """Record resource registration and return an inert decorator."""
        def inner(func):
            """Bind the UI resource."""
            self.resources[uri] = func
            return func
        return inner

    def tool(self, name, **kwargs):
        """Record tool registration and return an inert decorator."""
        def inner(func):
            """Bind the tool callable."""
            self.tools[name] = func
            return func
        return inner

def test_opt_in_registration(tmp_path: Path):
    """Keep writing disabled by default and register the editing tools when enabled."""
    first = MCPStub()
    register_file_viewer(first, roots=(tmp_path,))
    assert UI_URI == "ui://mcp-file-manager/v15/app.html"
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
