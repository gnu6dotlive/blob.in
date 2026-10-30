#!/usr/bin/env python3
"""AC05 independent offline qualification of a pre-existing private Weston/renderd run.
This does not launch processes, create network namespaces, or inject user input.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,shutil
from PIL import Image

def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):return sha_bytes(Path(p).read_bytes())
def main():
 parser=argparse.ArgumentParser()
 parser.add_argument("--source",type=Path,required=True)
 parser.add_argument("--destination",type=Path,required=True)
 a=parser.parse_args()
 src=a.source.resolve();dst=a.destination.resolve()
 dst.mkdir(parents=True,exist_ok=True)
 receipt={"gate":"BLOB-AC-05 captured-run independent oracle","scope":"real blobin_renderd CPU previews, actual BLOB-FRAME source pixels, private Weston test seat",
          "live_replay":"NOT_EXECUTED_IN_THIS_ORACLE","compositor_present_feedback":False,
          "physical_hid":False,"cp03_hybrid60":"NOT_PASS","verdict":"HOLD"}
 try:
  events=[json.loads(row) for row in (src/"production-events.jsonl").read_text().splitlines() if row.strip()]
  select=lambda name:[e for e in events if e.get("event")==name]
  connected=select("connected")
  requests=select("request"); frames=select("presented")
  gestures=select("ac05_gesture_state");pointer=select("ac05_winit_pointer")
  assert len(connected)==1 and connected[0]["server"]=="blobin-cuda05f-render-bridge","not actual renderd"
  assert [(e["request_id"],e["revision"],e["backend"],e["primitives"]) for e in requests]==[(1,3,"cpu",3),(2,4,"cpu",3)],"unexpected requests"
  assert [(e["request_id"],e["revision"],e["backend_actual"],e["frame_sequence"]) for e in frames]==[(1,3,"cpu",1),(2,4,"cpu",2)],"unexpected renderer frames"
  assert all(e["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for e in frames),"false GPU qualification"
  geometry=[e["geometry_sha256"] for e in frames]
  assert len(set(geometry))==2 and all(len(v)==64 and v!="0"*64 for v in geometry)
  assert len(pointer)>=5 and {e.get("state") for e in pointer if e.get("kind")=="button"}=={"Pressed","Released"}
  assert all(any(e.get("kind")=="move" and abs(e.get("x",0)-x)<0.01 and abs(e.get("y",0)-400)<0.01 for e in pointer) for x in [258,318,398])
  assert any(e["active"] and e["scheduler_revision"]==3 and e["preview_position"] and e["preview_position"]!=e["selected_position"] for e in gestures)
  assert all(e["scheduler_revision"]==3 for e in gestures if e["active"]), "intermediate render invalidation"
  assert gestures[-1]["commits"]==1 and gestures[-1]["scheduler_revision"]==4 and not gestures[-1]["active"]
  assert max(e["commits"] for e in gestures)==1 and max(e["cancels"] for e in gestures)==0
  steps=(src/"weston.stderr").read_text()
  for item in ["BLOB_AC05_PRIVATE_SEAT_READY","BLOB_AC05_COMPOSITOR_STEP down A",
              "BLOB_AC05_COMPOSITOR_STEP preview dx60","BLOB_AC05_COMPOSITOR_STEP preview dx140",
              "BLOB_AC05_COMPOSITOR_STEP up A"]:
   assert item in steps, "missing independent compositor evidence "+item
  server=(src/"renderd.stdout").read_text()
  assert "BLOB_FRAME_LISTENING" in server and "qualification=PREVIEW_ONLY" in server
  timings=(src/"renderd.stderr").read_text()
  assert timings.count("BLOB_FRAME_TIMING backend=cpu") == 2,"missing real CPU evaluations"
  samples={}
  compressed={}
  images=[]
  for rev in [3,4]:
   raw=src/f"runtime-revision-{rev}.rgba"
   content=raw.read_bytes()
   assert len(content)==932*800*4,"unexpected original SDF pixel extent"
   img=Image.frombytes("RGBA",(932,800),content)
   target=dst/f"real-renderd-revision-{rev}.png"
   img.save(target,"PNG",compress_level=9)
   packed=dst/f"real-renderd-revision-{rev}.rgba.gz"
   packed.write_bytes(gzip.compress(content,compresslevel=9,mtime=0))
   assert gzip.decompress(packed.read_bytes())==content
   compressed[str(rev)]={"raw_sha256":sha_bytes(content),"gzip_sha256":sha_file(packed),
                          "png_sha256":sha_file(target),"raw_bytes":len(content),"format":"RGBA8"}
   samples[str(rev)]={str(p):img.getpixel(p) for p in [(205,400),(345,400),(20,20)]}
   images.append(img)
  assert samples["3"]["(205, 400)"]==(255,255,255,255)
  assert samples["4"]["(205, 400)"]==(0,0,0,255)
  assert samples["3"]["(345, 400)"]==(0,0,0,255)
  assert samples["4"]["(345, 400)"]==(255,255,255,255)
  assert all(samples[str(rev)]["(20, 20)"]==(0,0,0,255) for rev in (3,4))
  assert compressed["3"]["raw_sha256"]!=compressed["4"]["raw_sha256"]
  files=["production-events.jsonl","weston.stderr","weston.log",
         "renderd.stdout","renderd.stderr","showcase.stderr"]
  copied={}
  for name in files:
   new=dst/name
   shutil.copy2(src/name,new)
   copied[name]=sha_file(new)
  receipt.update(verdict="SCOPED_PASS_EXISTING_PRIVATE_WESTON_REAL_CPU_SDF_PIXELS",
    native_pointer_events=len(pointer),input_steps=5,
    semantic_commits=1,render_requests=2,source_frames=2,
    before_revision=3,after_revision=4,
    renderd_geometry_sha256=geometry,original_pixel_buffers=compressed,
    sample_pixels=samples,copied_logs_sha256=copied)
 except Exception as exc:
  receipt["reason"]=repr(exc)
 (dst/"capture-qualification.json").write_text(json.dumps(receipt,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
 print(json.dumps(receipt,indent=2,ensure_ascii=False),flush=True)
 return 0 if receipt["verdict"].startswith("SCOPED_PASS") else 1
if __name__=="__main__":
 raise SystemExit(main())
