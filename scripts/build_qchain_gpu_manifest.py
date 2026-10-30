#!/usr/bin/env python3
"""Fail-closed GPU-source manifest for one fresh CP-F Vulkan run."""
from pathlib import Path
import hashlib,json,sys,csv
def sha(data): return hashlib.sha256(data).hexdigest()
def need(ok,msg):
 if not ok: raise ValueError(msg)
def create(raw,cpu,receipt,log,output):
 need(not output.exists(),"REFUSE_OVERWRITE")
 c=json.loads(receipt.read_text())
 need(c["verdict"]=="F2_F3_F4_CPU_CHAIN_PASS_BRIDGE_NOT_RUN","BAD_CPU_BASELINE")
 l=log.read_text()
 need("QCHAIN_CP_F_PERSISTENT_SESSION_PASS states=5 materials=4 frames=40 devices=1 pipelines=3 reusable_buffers=5 submits=40" in l,"GPU_RUN_NOT_ATTESTED")
 stat=(raw/"session-stats.tsv").read_text().splitlines()
 need(len(stat)==2 and stat[1].strip()=="1\t3\t5\t40","SESSION_REUSE_NOT_ATTESTED")
 with (raw/"resident-ledger.tsv").open() as f: records=list(csv.DictReader(f,delimiter="\t"))
 need(len(records)==40,"MISSING_GPU_FRAMES")
 stages=[]
 for i in range(5):
  proof=c["stages"][i]
  scene=(cpu/f"scene-{i:02}.scene.txt").read_bytes()
  need(sha(scene)==proof["scene_sha256"],"CPU_SCENE_CHANGED")
  row=[r for r in records if r["stage"]==str(i) and r["material"]=="ceramic" and r["frame"]=="0"]
  need(len(row)==1 and row[0]["digest"]==format(int(proof["f2_semantic_digest"]),"016x"),"SEMANTIC_BINDING")
  need(row[0]["backend"]=="vulkan_wgsl_gpu" and (row[0]["dispatches"],row[0]["submits"],row[0]["intermediate_host_transfers"])==("6","1","0"),"GPU_COMPUTE_LINEAGE")
  gpu=(raw/f"state{i}-ceramic-frame0-dpr2.gpu-rgba.bin").read_bytes()
  need(len(gpu)==512*384*4 and all(gpu[k]==255 for k in range(3,len(gpu),4)),"GPU_RGBA_FORMAT")
  stages.append({"stage":i,"epoch":i,"scene_sha256":proof["scene_sha256"],
     "semantic_digest":proof["f2_semantic_digest"],"gpu_rgba_sha256":sha(gpu),
     "gpu_file":f"state{i}-ceramic-frame0-dpr2.gpu-rgba.bin"})
 manifest={"schema":"gnu6.qchain.gpu_source_manifest.v1",
   "transport_version":"QCHAIN-GPU-FRAME-v1",
   "compute_run_log_sha256":sha(log.read_bytes()),
   "cpu_receipt_sha256":sha(receipt.read_bytes()),
   "backend":"Vulkan/WGSL",
   "compute_source_commit":"5132cf59b3842e27dcacf89bfe7060e807706e90",
   "compute_run":"CP-F persistent session 40 frames; 1 device; 3 pipelines; 5 buffers",
   "gpu_readback_into_sealed_memfd":True,
   "physical_gpu_attestation":False,"compositor_observed":False,
   "stages":stages}
 output.write_text(json.dumps(manifest,indent=2)+"\n")
 print("GPU_SOURCE_MANIFEST_PASS",len(stages),"gpu_rgba_distinct",len({v["gpu_rgba_sha256"] for v in stages}))
if __name__=="__main__":
 if len(sys.argv)!=6: raise SystemExit("usage: build_qchain_gpu_manifest.py GPU_RAW CPU_RAW CPU_RECEIPT COMPUTE_LOG OUTPUT")
 create(*map(Path,sys.argv[1:]))
