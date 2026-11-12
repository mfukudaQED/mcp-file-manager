"""Resolve File Manager UI defaults without host-specific frontend builds."""

from __future__ import annotations

import os
import socket
from html import escape
from typing import Mapping, Optional, Tuple

TABBY_TOKEN = "__MCPFM_V26_TABBY_PROFILE__"
WINSCP_TOKEN = "__MCPFM_V26_WINSCP_SITE__"


def _valid_value(value: str) -> str:
    """Validate a saved application target before inserting it into HTML."""
    value = value.strip()
    if not value or len(value) > 128 or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError("Host UI default must have 1-128 printable characters")
    return value


def resolve_host_defaults(
    hostname: Optional[str] = None,
    environ: Optional[Mapping[str, str]] = None,
) -> Tuple[str, str, str]:
    """Return the host label, Tabby profile, and WinSCP site for this server."""
    name = (hostname if hostname is not None else socket.gethostname()).split(".")[0].lower()
    if name.startswith("ohtaka"):
        host = "ohtaka"
    elif name.startswith("sham"):
        host = "sham"
    else:
        host = name
    env = os.environ if environ is None else environ
    return (
        host,
        _valid_value(env.get("MCP_FILE_MANAGER_TABBY_PROFILE", host)),
        _valid_value(env.get("MCP_FILE_MANAGER_WINSCP_SITE", host)),
    )


def render_host_defaults(template: str, tabby_profile: str, winscp_site: str) -> str:
    """Render exactly two HTML attribute values in the shared UI template."""
    if template.count(TABBY_TOKEN) != 1 or template.count(WINSCP_TOKEN) != 1:
        raise ValueError("Unexpected v26 UI host-default placeholders")
    return (template
            .replace(TABBY_TOKEN, escape(_valid_value(tabby_profile), quote=True))
            .replace(WINSCP_TOKEN, escape(_valid_value(winscp_site), quote=True)))
