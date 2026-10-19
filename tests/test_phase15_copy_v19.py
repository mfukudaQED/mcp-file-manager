"""Validate UI v19 copy controls and legacy resource isolation."""

from importlib.resources import files

from mcp_file_viewer.extension import (
    V19_UI_URI,
    UI_V19_META,
    V18_UI_URI,
    V17_UI_URI,
    V16_UI_URI,
    register_file_viewer,
)


def test_v19_copy_controls_and_transfer_removal() -> None:
    """Expose three copy buttons with an explicit fallback and no transfer buttons."""
    html = files("mcp_file_viewer").joinpath("ui/app_v19.html").read_text("utf-8")
    assert V19_UI_URI == "ui://mcp-file-manager/v19/app.html"
    assert "UI v19" in html
    for item in (
        'id="copy-tabby"',
        'id="copy-winscp"',
        'id="copy-path"',
        'id="copy-fallback"',
        'id="copy-fallback-text"',
        'id="winscp-site"',
        "winscp-sftp://",
        "tabby://profile?profileName=",
    ):
        assert item in html
    for item in (
        'id="transfer-download"',
        'id="transfer-upload"',
        'id="transfer-cancel"',
        'id="tabby-open"',
    ):
        assert item not in html
    assert "tabby://run" not in html
    assert "file_manager_upload_chunk" not in html
    assert "file_manager_download_chunk" not in html


def test_v19_new_ui_meta_and_legacy_resources(tmp_path) -> None:
    """Register distinct immutable resources and request clipboard only for v19."""

    class Stub:
        """Track registered resource functions and metadata."""

        def __init__(self) -> None:
            """Allocate empty resource and tool registries."""
            self.resources = {}
            self.metadata = {}

        def resource(self, uri, **kwargs):
            """Capture the resource decorator."""

            def accept(func):
                """Register resource handler for the supplied URI."""
                self.resources[uri] = func
                self.metadata[uri] = kwargs.get("meta", {})
                return func

            return accept

        def tool(self, name, **kwargs):
            """Allow tool registration without executing handlers."""
            return lambda func: func

    stub = Stub()
    register_file_viewer(stub, roots=(tmp_path,))
    assert stub.metadata[V19_UI_URI] == UI_V19_META
    assert UI_V19_META["ui"]["permissions"]["clipboardWrite"] == {}
    assert len({V19_UI_URI, V18_UI_URI, V17_UI_URI, V16_UI_URI}) == 4
    for uri, version in (
        (V19_UI_URI, "UI v19"),
        (V18_UI_URI, "UI v18"),
        (V17_UI_URI, "UI v17"),
        (V16_UI_URI, "UI v16"),
    ):
        assert version in stub.resources[uri]()
    for uri in (V18_UI_URI, V17_UI_URI, V16_UI_URI):
        assert "ui" not in stub.metadata[uri] or (
            "permissions" not in stub.metadata[uri]["ui"]
        )
