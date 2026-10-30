#!/usr/bin/env python3
"""Revalidate saved BLOB-AC-05 receipts without launching a compositor or touching user input."""
import argparse,gzip,hashlib,json
from pathlib import Path
from PIL import Image

def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 ap=argparse.ArgumentParser()
 ap.add_argument("--evidence",type=Path,required=True)
 args=ap.parse_args()
 root=args.evidence.resolve()
 receipt=json.loads((root/"capture-qualification.json").read_text())
 assert receipt["verdict"]=="SCOPED_PASS_EXISTING_PRIVATE_WESTON_REAL_CPU_SDF_PIXELS"
 rows=[json.loads(l) for l in (root/"production-events.jsonl").read_text().splitlines() if l.strip()]
 events=lambda kind:[r for r in rows if r.get("event")==kind]
 assert [e["revision"] for e in events("request")]==[3,4]
 assert [e["revision"] for e in events("presented")]==[3,4]
 assert [e["request_id"] for e in events("presented")]==[1,2]
 assert [e["backend_actual"] for e in events("presented")]==["cpu","cpu"]
 assert all(e["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for e in events("presented"))
 assert [e["geometry_sha256"] for e in events("presented")]==receipt["renderd_geometry_sha256"]
 states=events("ac05_gesture_state")
 assert any(s["active"] and s["commits"]==0 and s["scheduler_revision"]==3 and
            s["preview_position"]!=s["selected_position"] for s in states)
 assert states[-1]["scheduler_revision"]==4 and states[-1]["commits"]==1 and not states[-1]["active"]
 for rev in ("3","4"):
  row=receipt["original_pixel_buffers"][rev]
  raw=gzip.decompress((root/f"real-renderd-revision-{rev}.rgba.gz").read_bytes())
  assert sha(raw)==row["raw_sha256"] and len(raw)==row["raw_bytes"]==932*800*4
  with Image.open(root/f"real-renderd-revision-{rev}.png") as im:
   assert im.convert("RGBA").tobytes()==raw
  assert sha((root/f"real-renderd-revision-{rev}.png").read_bytes())==row["png_sha256"]
  assert sha((root/f"real-renderd-revision-{rev}.rgba.gz").read_bytes())==row["gzip_sha256"]
 for filename,h in receipt["copied_logs_sha256"].items():
  assert sha((root/filename).read_bytes())==h
 for item in ["BLOB_AC05_PRIVATE_SEAT_READY","BLOB_AC05_COMPOSITOR_STEP up A"]:
  assert item in (root/"weston.stderr").read_text()
 assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
 print("BLOB_AC05_REVALIDATED_CAPTURE_PASS_2_REAL_SDF_FRAMES_ONE_COMMIT_NO_LIVE_REPLAY")
 return 0
if __name__=="__main__":
 raise SystemExit(main())
