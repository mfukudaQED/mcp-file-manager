"""Exercise opt-in binary transfer across a real, isolated MCP stdio session.

This does not touch the running systemd service, its config or ChatGPT Tunnel.
Fixtures and all child-process state stay below the pytest-approved user directory.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from hpc_mcp.config import Settings
from hpc_mcp.server import build_server


async def _invoke(session: ClientSession, name: str, params: dict) -> dict:
    """Decode one actual MCP tool response across the stdio boundary."""
    response = await session.call_tool(name, params)
    assert not response.isError, name
    assert response.content and response.content[0].type == "text"
    data = json.loads(response.content[0].text)
    assert "error" not in data, (name, data)
    return data


async def _exercise(root: Path) -> None:
    """Transfer binary payloads bidirectionally and verify create-only behavior."""
    payload = bytes(range(256)) * 19 + b"\x00\xff\xfe"
    source = root / "download.bin"
    source.write_bytes(payload)
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(Path(__file__).resolve()), "--serve", "--root", str(root)],
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            expected = {
                "file_manager_transfer_capabilities", "file_manager_transfer_info",
                "file_manager_download_chunk", "file_manager_upload_start",
                "file_manager_upload_chunk", "file_manager_upload_finish",
                "file_manager_upload_cancel",
            }
            assert expected.issubset(tools)
            for name in expected:
                assert tools[name].meta["ui"]["visibility"] == ["app"]
            capabilities = await _invoke(session, "file_manager_transfer_capabilities", {})
            assert capabilities["download"] is True
            assert capabilities["upload"] is True
            assert capabilities["max_file_bytes"] == 65536
            assert capabilities["chunk_bytes"] == 4096
            assert str(root) in capabilities["upload_roots"]

            info = await _invoke(
                session, "file_manager_transfer_info", {"path": str(source)},
            )
            assert info["size_bytes"] == len(payload)
            assert info["revision"] == "sha256:" + hashlib.sha256(payload).hexdigest()
            reconstructed = bytearray()
            offset = 0
            while offset < len(payload):
                chunk = await _invoke(
                    session, "file_manager_download_chunk",
                    {"path": str(source), "offset": offset, "revision": info["revision"]},
                )
                data = base64.b64decode(chunk["content_base64"], validate=True)
                assert 0 < len(data) <= 4096
                reconstructed.extend(data)
                offset = chunk["next_offset"]
            assert bytes(reconstructed) == payload

            start = await _invoke(
                session, "file_manager_upload_start",
                {
                    "directory": str(root), "filename": "uploaded.bin",
                    "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                },
            )
            session_id = start["session_id"]
            for offset in range(0, len(payload), 4096):
                data = payload[offset:offset + 4096]
                chunk = await _invoke(
                    session, "file_manager_upload_chunk",
                    {
                        "session_id": session_id, "offset": offset,
                        "content_base64": base64.b64encode(data).decode("ascii"),
                    },
                )
                assert chunk["received_bytes"] == offset + len(data)
            result = await _invoke(
                session, "file_manager_upload_finish", {"session_id": session_id},
            )
            assert result["revision"] == info["revision"]
            assert (root / "uploaded.bin").read_bytes() == payload
            assert not list(root.glob(".mcpfm-upload-*"))

            conflict = await session.call_tool(
                "file_manager_upload_start",
                {
                    "directory": str(root), "filename": "uploaded.bin",
                    "size_bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
                },
            )
            data = json.loads(conflict.content[0].text)
            assert data["error"]["code"] == "file_changed"
            assert (root / "uploaded.bin").read_bytes() == payload


def test_isolated_transfer_stdio(tmp_path: Path) -> None:
    """Check the real MCP framing, registration, revision and byte integrity."""
    root = tmp_path / "approved"
    root.mkdir(mode=0o700)
    asyncio.run(_exercise(root))


if __name__ == "__main__" and "--serve" in sys.argv:
    root = Path(sys.argv[sys.argv.index("--root") + 1])
    build_server(Settings(
        roots=(root,), scheduler_type="none", enable_file_viewer=True,
        enable_file_manager_download=True, enable_file_manager_upload=True,
        file_manager_upload_roots=(root,), enable_writes=True,
    )).run(transport="stdio")
