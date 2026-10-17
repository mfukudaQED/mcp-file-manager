"""End-to-end stdio MCP test for the optional file viewer extension."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from hpc_mcp.config import Settings
from hpc_mcp.server import build_server


async def _exercise(root: Path, fixture: Path) -> None:
    """Exercise the registered viewer through a real local stdio client."""
    server = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", "--root", str(root)],
        env=dict(os.environ),
    )
    async with stdio_client(server) as (reader, writer):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            registered = {tool.name for tool in (await session.list_tools()).tools}
            assert "file_viewer_read_text" in registered
            response = await session.call_tool(
                "file_viewer_read_text",
                {"path": str(fixture), "start_line": 1, "max_lines": 20},
            )
            assert not response.isError
            assert response.content
            result = json.loads(response.content[0].text)
            assert result["content"] == "# Test\nhello from stdio\n"
            assert result["total_lines"] == 2


def test_stdio_roundtrip(tmp_path: Path) -> None:
    """Validate the complete protocol path without touching the live service."""
    fixture = tmp_path / "safe.md"
    fixture.write_text("# Test\nhello from stdio\n", encoding="utf-8")
    asyncio.run(_exercise(tmp_path, fixture))


if __name__ == "__main__" and "--serve" in sys.argv:
    root = Path(sys.argv[sys.argv.index("--root") + 1])
    build_server(
        Settings(roots=(root,), scheduler_type="none", enable_file_viewer=True)
    ).run(transport="stdio")
