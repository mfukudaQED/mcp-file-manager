from pathlib import Path
from mcp_file_viewer.viewer import FileViewer
from mcp_file_viewer.policy import FilePolicy
from mcp_file_viewer.log_diagnostics import analyze_suffix

def test_scf_success_and_failure():
    a=analyze_suffix("SCF converged in 12 steps\n",start_byte=0,end_byte=26,file_size=26,revision="x")
    assert a["scf_status"]=="converged"
    b=analyze_suffix("SCF converged\nSCF NOT converged\n",start_byte=0,end_byte=32,file_size=32,revision="y")
    assert b["scf_status"]=="not_converged"

def test_error_and_timing(tmp_path: Path):
    f=tmp_path/"calc.log";f.write_text("step\nERROR: SCF failed\nWARNING: issue\nTotal time: 12.3\n")
    r=FileViewer(FilePolicy(roots=(tmp_path,))).diagnose_log(str(f))
    assert r["counts_in_excerpt"]["error"]==1
    assert r["counts_in_excerpt"]["warning"]==1
    assert r["counts_in_excerpt"]["timing"]==1
    assert r["scf_status"]=="not_converged"

def test_large_log_is_partial(tmp_path: Path):
    f=tmp_path/"big.log";f.write_text("nothing\n"*500000+"SCF converged\n")
    r=FileViewer(FilePolicy(roots=(tmp_path,),max_file_bytes=1024)).diagnose_log(str(f))
    assert r["partial_log"] and r["scf_status"]=="converged"
