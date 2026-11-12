"""Regression tests for host-independent UI binaries and per-host defaults."""

from hashlib import sha256
from importlib.resources import files

import pytest

from mcp_file_viewer.host_defaults import (
    TABBY_TOKEN, WINSCP_TOKEN, render_host_defaults, resolve_host_defaults,
)


def test_host_aliases_and_overrides():
    """Map actual login-node names without changing service configuration."""
    assert resolve_host_defaults("sham", {}) == ("sham", "sham", "sham")
    assert resolve_host_defaults("ohtaka1.issp.u-tokyo.ac.jp", {}) == (
        "ohtaka", "ohtaka", "ohtaka"
    )
    assert resolve_host_defaults("custom01.example.org", {}) == (
        "custom01", "custom01", "custom01"
    )
    assert resolve_host_defaults("sham", {
        "MCP_FILE_MANAGER_TABBY_PROFILE": "My Tabby",
        "MCP_FILE_MANAGER_WINSCP_SITE": "Site-A",
    }) == ("sham", "My Tabby", "Site-A")


def test_template_substitution_is_escaped_and_strict():
    """Protect HTML attributes against injection and malformed templates."""
    template = '<input value="' + TABBY_TOKEN + '"><input value="' + WINSCP_TOKEN + '">'
    html = render_host_defaults(template, 'A" & B', "<server>")
    assert 'value="A&quot; &amp; B"' in html
    assert 'value="&lt;server&gt;"' in html
    with pytest.raises(ValueError):
        render_host_defaults("bad template", "sham", "sham")
    with pytest.raises(ValueError):
        render_host_defaults(template, "sham\nunsafe", "sham")


def test_unified_v26_bundle_is_reproducible():
    """Verify the exact bundled UI and placeholder count."""
    bundle = files("mcp_file_viewer").joinpath("ui/app_v26.html").read_bytes()
    assert sha256(bundle).hexdigest() == (
        "1ab4138a7ba927cde208d56de4466b82d600f8f314330264d460c77cddf86854"
    )
    html = bundle.decode("utf-8")
    assert html.count(TABBY_TOKEN) == 1
    assert html.count(WINSCP_TOKEN) == 1
    assert "UI v26" in html
    assert "katex" in html.lower()
    assert "Load more" in html
