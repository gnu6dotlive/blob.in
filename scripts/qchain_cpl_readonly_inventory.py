#!/usr/bin/env python3
"""CP-L static inventory only. Never executes sabotage or upgrades G06."""
import argparse,json,re
from pathlib import Path
CANDIDATES={
 "N01":("PARTIAL","scripts/qchain_cpe_oracle.py","Existing SHA checks cover files/receipts, not altered executable source"),
 "N02":("CANDIDATE","scripts/test_qchain_cpi01_weston.py","Identity substitution is rejected but full injection scope not executed"),
 "N03":("PARTIAL","crates/blob-frame/src/qchain_gpu.rs","Overflow/request revisions checked, full ordered replay campaign pending"),
 "N04":("UNMAPPED",None,"No directly attributable forged GPU topology-ID negative test located"),
 "N05":("PARTIAL","scripts/test_qchain_cpd_oracle.py","Mask pixel mutation detected; component/hole mutation not independently exercised"),
 "N06":("CANDIDATE","scripts/test_qchain_cpd_oracle.py","Fake GPU-mask provenance mutation exists"),
 "N07":("CANDIDATE","scripts/test_qchain_gpu_oracles.py","F3 NaN field mutation exists"),
 "N08":("CANDIDATE","scripts/test_qchain_cpd_oracle.py","F4 dispatch count manipulation exists; reordering still unqualified"),
 "N09":("PARTIAL","scripts/test_qchain_cpd_oracle.py","Reduced-motion counters audited; live unexpected temporal mutation pending"),
 "N10":("CANDIDATE","docs/QCHAIN-CP-H2-20261010.md","Vulkan ICD unavailable caused fail-closed in separate runs"),
 "N11":("PARTIAL","crates/blob-frame/src/qchain_gpu.rs","Pixel SHA and alpha checked; stride mutation needs isolated control"),
 "N12":("PARTIAL","crates/blob-frame/src/qchain_gpu.rs","Unsealed and extra FDs tested; foreign UID injection not executed"),
 "N13":("CANDIDATE","scripts/test_qchain_cpi01_weston.py","Central captured PNG pixel tampering is rejected"),
 "N14":("CANDIDATE","scripts/test_qchain_gpu_compositor_gate.py","Enlarged compositor-corner mask is rejected"),
 "N15":("PARTIAL","docs/QCHAIN-CP-H-20261010.md","SHA-bound altered receipts rejected, but no independent signed-evidence issuer"),
 "N16":("PARTIAL","crates/blob-frame/src/qchain_gpu.rs","Compute-log binding; no independent GPU driver proof of actual dispatch"),
 "N17":("CANDIDATE","scripts/test_qchain_cpi01_weston.py","Equal-pixel scenes cannot substitute distinct semantic identities")
}

def execute(root,out):
    assert not out.exists(),"REFUSE_OVERWRITE"
    dispatch=json.loads((root/"contracts/qchain-gpu-execution-01/dispatch.json").read_text())
    laws=dispatch["negative_laws"]
    assert sorted(laws)==sorted(CANDIDATES),"LAW_SET_DRIFT"
    text=(root/"docs/QCHAIN-GPU-EXECUTION-01.md").read_text()
    items=[]
    for law in laws:
        matched=re.search(r"^\| ("+law+r") \| ([^|]+) \| `([^\x60]+)` \|",text,re.M)
        assert matched is not None,"LAW_REFUSAL_MISSING_"+law
        status,path,note=CANDIDATES[law]
        # Correct mismatched historical source paths without inventing evidence
        if path is not None:
            assert (root/path).is_file(), "MISSING_CANDIDATE_"+law+":"+path
        items.append({"id":law,"injection":matched.group(2).strip(),
          "required_refusal":matched.group(3),
          "assessment":"NOT_EXECUTED_UNDER_CP_L",
          "prior_candidate":status,"source_path":path,
          "remaining_gap":note})
    report={"schema":"gnu6.qchain.cpl_readonly_inventory.v1",
      "contract":"QCHAIN-GPU-EXECUTION-01",
      "scope":"static inventory only; no mutations in CP-L",
      "laws_count":len(items),"g06_full_pass":False,
      "observed_cp_l_negatives":0,
      "candidate_count":sum(r["prior_candidate"]!="UNMAPPED" for r in items),
      "unmapped_count":sum(r["prior_candidate"]=="UNMAPPED" for r in items),
      "canonical_source_worktrees_not_modified_by_inventory":True,
      "items":items}
    out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    print("CPL_READONLY_INVENTORY_PASS laws",len(items),
      "unmapped",report["unmapped_count"],"G06_FULL_NOT_RUN")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    execute(a.root,a.out)
if __name__=="__main__":main()
