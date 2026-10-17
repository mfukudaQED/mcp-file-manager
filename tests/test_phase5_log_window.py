from pathlib import Path
import pytest
from mcp_file_viewer.policy import FilePolicy, FileViewerError
from mcp_file_viewer.viewer import FileViewer

def test_window_unicode_navigation(tmp_path: Path):
    p=tmp_path/"calc.log"
    p.write_text("αβγ\n"*1000+"DONE\n",encoding="utf-8")
    v=FileViewer(FilePolicy(roots=(tmp_path,),max_file_bytes=1024))
    last=v.log_window(str(p),max_bytes=257)
    before=v.log_window(str(p),direction="before",offset=last["start_byte"],max_bytes=257)
    assert before["end_byte"]==last["start_byte"]
    assert (before["content"]+last["content"]).endswith("DONE\n")
    assert len(last["content"].encode()) <= 260
    after=v.log_window(str(p),direction="after",offset=before["end_byte"],max_bytes=257)
    assert after["start_byte"]==last["start_byte"]
    assert before["identity"]==after["identity"]
    assert v.log_status(str(p))["revision"]==last["revision"]

def test_window_append_and_truncation(tmp_path: Path):
    p=tmp_path/"job.log";p.write_text("start\n")
    v=FileViewer(FilePolicy(roots=(tmp_path,)))
    before=v.log_status(str(p))
    with p.open("a") as f:f.write("end\n")
    after=v.log_status(str(p))
    assert before["identity"]==after["identity"]
    assert before["revision"]!=after["revision"]
    assert before["size_bytes"]<after["size_bytes"]
    p.write_text("x")
    with pytest.raises(FileViewerError):
        v.log_window(str(p),direction="after",offset=after["size_bytes"])

def test_window_security(tmp_path: Path):
    v=FileViewer(FilePolicy(roots=(tmp_path,)))
    with pytest.raises(FileViewerError):v.log_status("/etc/passwd")
    with pytest.raises(FileViewerError):v.log_window("/etc/passwd")
    with pytest.raises(FileViewerError):v.log_window(str(tmp_path/"no.log"),max_bytes=20000)
