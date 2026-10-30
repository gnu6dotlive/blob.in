#!/usr/bin/env python3
"""CP-G independent GPU-source sealed-IPC to Hyprland capture oracle."""
from pathlib import Path
import hashlib,json,re,subprocess,sys
from qchain_compositor_gate import compare_rgba
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def messages(s,pattern):return re.findall(pattern,s)
def evaluate(evidence,manifest_path,cpu_receipt,raw,compute_log):
 m=json.loads(manifest_path.read_text())
 cpu=json.loads(cpu_receipt.read_text())
 run=json.loads((evidence/"capture-reconciliation.json").read_text())
 require(m["schema"]=="gnu6.qchain.gpu_source_manifest.v1","GPU_MANIFEST_INVALID")
 require(m["transport_version"]=="QCHAIN-GPU-FRAME-v1","GPU_WIRE_VERSION_INVALID")
 require(m["backend"]=="Vulkan/WGSL" and m["gpu_readback_into_sealed_memfd"],"GPU_BACKEND_INVALID")
 require(m["compute_source_commit"]=="5132cf59b3842e27dcacf89bfe7060e807706e90","COMPUTE_SOURCE_UNKNOWN")
 require(not m["physical_gpu_attestation"] and not m["compositor_observed"],"PREQUALIFIED_SOURCE_FORGED")
 require(sha(cpu_receipt.read_bytes())==m["cpu_receipt_sha256"],"CPU_RECEIPT_TAMPER")
 require(sha(compute_log.read_bytes())==m["compute_run_log_sha256"],"COMPUTE_LOG_TAMPER")
 require("QCHAIN_CP_F_PERSISTENT_SESSION_PASS" in compute_log.read_text(),"GPU_COMPUTE_NOT_COMPLETED")
 require(len(m["stages"])==len(cpu["stages"])==5,"FIVE_SCENES_REQUIRED")
 require(run["viewer_exit_code"]==run["source_exit_code"]==0,"PROCESS_FAILED")
 require(run["winit_present_submitted_stages"]==list(range(5)),"PRESENTATION_INCOMPLETE")
 require(len(run["captures"])==5,"CAPTURE_COUNT_INCOMPLETE")

 sourcelog=(evidence/"source.log").read_text()
 viewerlog=(evidence/"viewer.log").read_text()
 gpu_sent=messages(sourcelog,r"QCHAIN_GPU_SOURCE_TRANSMITTED stage=(\d+) sha256=([0-9a-f]{64}) run_log_sha256=([0-9a-f]{64})")
 gpu_recv=messages(viewerlog,r"QCHAIN_GPU_IPC_RECEIVED stage=(\d+) rgba_sha256=([0-9a-f]{64})")
 presented=messages(viewerlog,
   r"QCHAIN_GPU_WGPU_PRESENT_SUBMITTED stage=(\d+) epoch=(\d+) scene_sha256=([0-9a-f]{64}) rgba_sha256=([0-9a-f]{64}) dimensions=(\d+)x(\d+)")
 require(len(gpu_sent)==len(gpu_recv)==5,"SEALED_GPU_IPC_RECEIPTS_MISSING")
 require(len(presented)>=5,"GPU_WGPU_PRESENT_SUBMISSIONS_MISSING")
 by_stage={v["stage"]:v for v in run["captures"]}
 require(set(by_stage)==set(range(5)),"DUPLICATE_OR_MISSING_CAPTURE")
 require(len({v["scene_sha256"] for v in m["stages"]})==5,"SEMANTIC_SCENE_COLLISION")
 stages=[]
 for i,item in enumerate(m["stages"]):
  proof=cpu["stages"][i]
  require(item["stage"]==item["epoch"]==proof["epoch"]==i,"EPOCH_REPLAY")
  require(item["scene_sha256"]==proof["scene_sha256"],"CPU_SCENE_IDENTITY_CHANGED")
  require(item["semantic_digest"]==proof["f2_semantic_digest"],"SEMANTIC_DIGEST_WRONG")
  rgba_file=f"state{i}-ceramic-frame0-dpr2.gpu-rgba.bin"
  require(item["gpu_file"]==rgba_file,"GPU_SOURCE_FILENAME_WRONG")
  expected=(raw/rgba_file).read_bytes()
  require(len(expected)==512*384*4,"GPU_FRAME_LENGTH")
  expect_sha=sha(expected)
  require(item["gpu_rgba_sha256"]==expect_sha,"GPU_FRAME_MANIFEST_MISMATCH")
  require(gpu_sent[i]==(str(i),expect_sha,m["compute_run_log_sha256"]),"SOURCE_RECEIPT_WRONG")
  require(gpu_recv[i]==(str(i),expect_sha),"VIEWER_RECEIPT_WRONG")

  require(any(t==(str(i),str(i),item["scene_sha256"],expect_sha,"512","384")
       for t in presented),"PRESENTED_SCENE_BINDING_WRONG")
  cap=by_stage[i]
  require(cap["captured"] and cap["qchain_window_rounding_disabled"],"WINDOW_OBSERVATION_MISSING")
  require(cap["geometry"].endswith("512x384"),"WINDOW_GEOMETRY_WRONG")
  png=evidence/f"stage-{i:02}.png"
  require(sha(png.read_bytes())==cap["capture_sha256"],"CAPTURE_BYTES_TAMPER")
  output=subprocess.run(["magick",str(png),"-depth","8","RGBA:-"],
    capture_output=True,check=True,timeout=7).stdout
  require(sha(output)==cap["raw_capture_rgba_sha256"],"CAPTURE_DECODE_DRIFT")
  require(cap["expected_rgba_sha256"]==expect_sha,"COMPOSITOR_WRONG_GPU_SOURCE")
  pix=compare_rgba(expected,output)
  require(pix["accepted_region_exact"],f"COMPOSITOR_OUTSIDE_MASK_MISMATCH_STAGE_{i}")
  stages.append({"stage":i,"scene_sha256":item["scene_sha256"],
    "gpu_rgba_sha256":expect_sha,"png_sha256":cap["capture_sha256"],**pix})
 return {"schema":"gnu6.qchain.gpu_source_wayland_e2e.v1",
   "verdict":"QCHAIN_GPU_SOURCE_IPC_WAYLAND_E2E_PASS_CORNER_MASKED",
   "gpu_source_real_vulkan_compute_log_sha256":m["compute_run_log_sha256"],
   "transport_version":m["transport_version"],
   "sealed_memfd_receipts":5,"separate_viewer_vulkan_present_submissions":len(presented),
   "masked_capture_pass":5,"unmasked_exact":all(v["entire_frame_exact"] for v in stages),
   "accepted_pixels_per_frame":195312,
   "total_mismatches_outside_authorized_mask":0,
   "gpu_readback_to_host":True,"zero_copy_gpu_to_wayland":False,
   "driver_allocation_trace":"NOT_RUN","physical_photons":"NOT_RUN",
   "cp03_hybrid60":"OPEN","stages":stages}

def main():
 if len(sys.argv)!=7:
  raise SystemExit("usage: qchain_gpu_compositor_gate.py WAYLAND MANIFEST CPU_RECEIPT GPU_RAW COMPUTE_LOG OUTPUT")
 e,m,c,r,l,out=map(Path,sys.argv[1:])
 require(not out.exists(),"REFUSE_OVERWRITE")
 result=evaluate(e,m,c,r,l)
 out.write_text(json.dumps(result,indent=2)+"\n")
 print(result["verdict"],"captured",len(result["stages"]),"accepted_pixels",result["accepted_pixels_per_frame"])
 print("outside_mask_mismatches",result["total_mismatches_outside_authorized_mask"])
if __name__=="__main__":main()
