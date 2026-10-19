"""End-to-end MCP Apps resource and metadata smoke tests (SDK v1 compatibility)."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from hpc_mcp.config import Settings
from hpc_mcp.server import build_server
from mcp_file_viewer.extension import UI_MIME, UI_URI, V20_UI_URI, V19_UI_URI, V18_UI_URI, V17_UI_URI, V16_UI_URI


async def _exercise(root: Path, fixture: Path) -> None:
    """Exercise the full MCP stdio path, not just FastMCP's managers."""
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", "--root", str(root)],
    )
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool = next(t for t in tools if t.name == "file_viewer_open")
            assert tool.meta["ui"]["resourceUri"] == UI_URI
            panel = next(t for t in tools if t.name == "file_manager_panel")
            assert panel.meta["ui"]["resourceUri"] == UI_URI
            assert {"type": "thread"} in panel.meta["openai/ui"]["entrypoints"]
            assert not panel.inputSchema.get("required", [])

            resources = (await session.list_resources()).resources
            resource = next(r for r in resources if str(r.uri) == UI_URI)
            assert resource.mimeType == UI_MIME

            data = await session.read_resource(UI_URI)
            assert len(data.contents) == 1
            html = data.contents[0].text
            assert data.contents[0].mimeType == UI_MIME
            assert "<title>MCP File Manager</title>" in html
            assert len(html) > 200_000  # official ext-apps SDK bundled into single HTML
            assert "file_viewer_read_text" in html
            assert "file_viewer_read_section" in html
            assert "file_viewer_list" in html
            assert 'src="http' not in html  # no external scripts
            assert "<script" in html
            assert "UI v21" in html
            old_resource = next(r for r in resources if str(r.uri) == V16_UI_URI)
            assert old_resource.mimeType == UI_MIME
            old_data = await session.read_resource(V16_UI_URI)
            assert len(old_data.contents) == 1
            old_html = old_data.contents[0].text
            assert "UI v16" in old_html
            assert "UI v17" not in old_html
            assert old_html != html
            v17_data = await session.read_resource(V17_UI_URI)
            v17_html = v17_data.contents[0].text
            assert "UI v17" in v17_html
            assert "UI v18" not in v17_html
            assert v17_html != html
            v18_data = await session.read_resource(V18_UI_URI)
            v18_html = v18_data.contents[0].text
            assert "UI v18" in v18_html
            assert "UI v19" not in v18_html
            assert v18_html != html
            v19_data = await session.read_resource(V19_UI_URI)
            v19_html = v19_data.contents[0].text
            assert "UI v19" in v19_html
            assert "UI v20" not in v19_html
            assert v19_html != html
            v20_data = await session.read_resource(V20_UI_URI)
            v20_html = v20_data.contents[0].text
            assert "UI v20" in v20_html
            assert "UI v21" not in v20_html
            assert v20_html != html

            empty_response = await session.call_tool("file_manager_panel", {})
            assert not empty_response.isError
            assert "entrypoint" in empty_response.content[0].text
            response = await session.call_tool("file_viewer_open", {"path": str(fixture)})
            assert not response.isError
            assert response.content
            assert "revision" in response.content[0].text


def test_ui_stdio_resource(tmp_path: Path) -> None:
    fixture = tmp_path / "example.md"
    fixture.write_text("# MCP File Manager\nhello\n", encoding="utf-8")
    asyncio.run(_exercise(tmp_path, fixture))


if __name__ == "__main__" and "--serve" in sys.argv:
    root = Path(sys.argv[sys.argv.index("--root") + 1])
    build_server(
        Settings(roots=(root,), scheduler_type="none", enable_file_viewer=True)
    ).run(transport="stdio")
