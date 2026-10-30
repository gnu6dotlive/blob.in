#!/usr/bin/env python3
"""Independent 01C captured native reset oracle; no synthetic frames."""
from pathlib import Path
import argparse,hashlib,json,gzip,shutil,tempfile,sys
from PIL import Image
def sha(x):return hashlib.sha256(x).hexdigest()
def check(root:Path,dest:Path|None=None):
    r=root.resolve()
    sealed=json.loads((r/"native-qualification.json").read_text()) if (r/"native-qualification.json").exists() else None
    if sealed:
        for name,digest in sealed["archive_sha256"].items():
            assert sha((r/name).read_bytes())==digest, f"tampered {name}"
    events=[json.loads(x) for x in (r/"production-events.jsonl").read_text().splitlines() if x.strip()]
    def get(k):return [x for x in events if x.get("event")==k]
    submits=get("ui01c_native_submit");frames=get("presented");req=get("request")
    pixels=get("ui01c_gpu_pixels");pointer=get("ac05_winit_pointer")
    assert len(submits)>3 and all(x["commands"]==3 and x["surface"]==0x10C for x in submits)
    assert [submits[0]["camera_default"],submits[-1]["camera_default"]]==[False,True]
    assert [x["revision"] for x in req]==[3,4]
    assert [x["revision"] for x in frames]==[3,4]
    assert all(x["backend_actual"]=="cpu" and x["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for x in frames)
    assert frames[0]["geometry_sha256"]!=frames[1]["geometry_sha256"]
    assert [x["state"] for x in pixels]==["reset-before","reset-after"]
    assert [x["scene_revision"] for x in pixels]==[3,4]
    assert len([x for x in pointer if x.get("kind")=="button" and x.get("state")=="Released"])==2
    assert len(get("ui01a_native_submit"))>1 and len(get("ui01b_native_submit"))>1
    assert all(x["camera_default"] for x in submits[-3:])
    assert all(x["bounds"][2:]==[94.0,26.0] for x in submits)
    assert [x["nodes"] for x in submits]==[3]*len(submits)
    assert all(x["commands_batch"]==9 for x in submits)
    log=(r/"weston.stderr").read_text()
    for token in ("BLOB_UI01C_PRIVATE_SEAT_READY","BLOB_UI01C_COMPOSITOR_BUTTON_DOWN",
                  "BLOB_UI01C_COMPOSITOR_BUTTON_UP","BLOB_UI01C_COMPOSITOR_TOGGLE_UP"):
        assert token in log, token
    assert "panicked" not in (r/"showcase.stderr").read_text()
    assert (r/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    image={};dig={}
    for stage in ("reset-before","reset-after"):
        raw=r/f"{stage}.raw"
        data=raw.read_bytes() if raw.exists() else gzip.decompress((r/f"{stage}.rgba.gz").read_bytes())
        assert len(data)==1280*800*4
        image[stage]=Image.frombytes("RGBA",(1280,800),data)
        dig[stage]=sha(data)
        if sealed:
            with Image.open(r/f"{stage}.png") as png:
                assert png.convert("RGBA").tobytes()==data
    before,after=image["reset-before"],image["reset-after"]
    assert dig["reset-before"]!=dig["reset-after"]
    # Actual native 01C third button, around x1139.7 y631.
    assert before.getpixel((1146,644))!=after.getpixel((1146,644))
    # Old 01A/01B graphics remain pixel-identical in their own regions.
    assert before.getpixel((952,344))==after.getpixel((952,344))
    assert before.getpixel((975,670))==after.getpixel((975,670))
    rect=(1139,631,1234,657)
    diff=sum(a!=b for a,b in zip(before.crop(rect).tobytes(),after.crop(rect).tobytes()))
    assert diff>200
    result={"verdict":"SCOPED_PASS_01C_NATIVE_CAMERA_RESET_AND_GPU_UI_PIXELS",
       "source":"actual blobin-renderd CPU / real showcase / Weston private input",
       "ui_third_component":True,"g02_surface":0x10C,
       "g03_bounds":submits[0]["bounds"],
       "batched_nodes":3,"batched_draw_commands":9,
       "semantic_reset_count":1,"pointer_release_count":2,
       "sdf_requests":2,"sdf_frames":2,"revisions":[3,4],
       "same_geometry_digest":False,"shader_gpu_sdf_qualified":False,
       "client_gpu_readback":True,"compositor_present_feedback":False,
       "original_frame_sha256":dig,"reset_button_changed_channel_bytes":diff}
    if dest:
        dest.mkdir(parents=True,exist_ok=True)
        for stage in ("reset-before","reset-after"):
            raw=image[stage].tobytes()
            (dest/f"{stage}.rgba.gz").write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
            image[stage].save(dest/f"{stage}.png","PNG",compress_level=9)
        for f in ("production-events.jsonl","weston.stderr","weston.log","renderd.stdout","renderd.stderr","showcase.stderr"):
            shutil.copy2(r/f,dest/f)
        result["archive_sha256"]={f.name:sha(f.read_bytes()) for f in dest.iterdir() if f.is_file()}
        (dest/"native-qualification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--destination",type=Path)
    p.add_argument("--negative",choices=["none","trace","png"],default="none")
    args=p.parse_args()
    try:
        if args.negative!="none":
            with tempfile.TemporaryDirectory(prefix="blob-ui01c-adversarial-") as temp:
                root=Path(temp)/"mutated";shutil.copytree(args.source,root)
                if args.negative=="trace":
                    f=root/"production-events.jsonl"
                    rows=[json.loads(x) for x in f.read_text().splitlines()]
                    for row in rows:
                        if row.get("event")=="request":row["revision"]=999
                    f.write_text("\n".join(json.dumps(x) for x in rows)+"\n")
                else:
                    f=root/"reset-after.png"
                    raw=bytearray(f.read_bytes());raw[-17]^=8;f.write_bytes(raw)
                try:check(root)
                except (OSError,AssertionError,ValueError,KeyError):
                    print("01C_NEGATIVE_REJECTED",args.negative)
                    return 0
                print("01C_NEGATIVE_ACCEPTED")
                return 1
        print(json.dumps(check(args.source,args.destination),indent=2))
        return 0
    except (OSError,AssertionError,ValueError,KeyError) as e:
        print("BLOB_UI01C_HOLD",repr(e),file=sys.stderr)
        return 1
if __name__=="__main__":sys.exit(main())
