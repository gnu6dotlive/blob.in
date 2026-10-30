#!/usr/bin/env python3
"""Source-audited preflight only, never a CP03 HYBRID-60 PASS."""
import hashlib
import json
import subprocess
from pathlib import Path

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    repo=Path(__file__).resolve().parents[1]
    evidence=Path("/mnt/workbench/evidence/runs/blobin-cp03i01-20261012-01")
    output=evidence/"qualification-preflight-20261012.json"
    if output.exists():
        raise RuntimeError("REFUSE_OVERWRITE")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip()
    status=subprocess.check_output(["git","status","--porcelain"],cwd=repo,text=True).strip()
    if status:
        raise RuntimeError("WORKTREE_DIRTY")
    audit=json.loads((evidence/"source-audit/donor-inventory.json").read_text())
    tests=(evidence/"checks/source-audit-tests.log").read_text()
    core=(evidence/"checks/historical-core-tests.log").read_text()
    assert audit["status"]=="DONOR_INVENTORY_PASS"
    assert not audit["cp03_hybrid60_pass"]
    assert all(v=="HOLD" for v in audit["cp03_gates"].values())
    assert "Ran 5 tests" in tests and "OK" in tests
    assert "41 passed; 0 failed" in core
    sources=[
        "docs/CP03-I01-HYBRID-HERO-SCENE-CONTRACT-20261012.md",
        "docs/CP03-I01-SOURCE-TRUTH-AND-NEXT-ACTIONS-20261012.md",
        "scripts/cp03_i01_source_audit.py",
        "scripts/test_cp03_i01_source_audit.py",
        "scripts/cp03_i01_seal.py",
    ]
    hashes={"source:"+n:digest(repo/n) for n in sources}
    for directory in ("source-audit","checks"):
        for path in sorted((evidence/directory).rglob("*")):
            if path.is_file():
                hashes[str(path.relative_to(evidence))]=digest(path)
    result={
       "schema":"blob.in.cp03.i01_source_preflight.v1",
       "verdict":"CP03_I01_DONOR_SOURCE_PREFLIGHT_SCOPED_PASS",
       "commit":head,
       "parent":"977e3cb65041b5654a44fbf5d28cdabc8f47760f",
       "product":"blob.in",
       "workload":"HYBRID-HERO-60@1",
       "donors_inspected":len(audit["proofs"]),
       "source_audit_negative_tests":5,
       "historical_core_tests":41,
       "full_3d_mixed_geometry_built":False,
       "native_1280x720_scene_rendered":False,
       "cp03_gates":audit["cp03_gates"],
       "cp03_hybrid60_qualified":False,
       "merge_push_deploy":False,
       "source_and_evidence_sha256":hashes,
    }
    output.write_text(json.dumps(result,indent=2)+"\n")
    print(result["verdict"],"commit",head,"sha256",digest(output),
          "sha_entries",len(hashes))

if __name__=="__main__":
    main()
