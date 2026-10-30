#!/usr/bin/env python3
"""01E independent oracle for private Weston native 64-command scene composition.
Reads REAL wgpu swapchain GPU bytes before present; does not fabricate images.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,shutil,tempfile,sys
from PIL import Image

def digest(blob):return hashlib.sha256(blob).hexdigest()
def qualify(root:Path,destination:Path|None=None)->dict:
    root=root.resolve()
    seal=root/"native-qualification.json"
    recorded=json.loads(seal.read_text()) if seal.exists() else None
    if recorded:
        for name,value in recorded["archive_sha256"].items():
            assert digest((root/name).read_bytes())==value, f"changed archived source: {name}"
    rows=[json.loads(line) for line in (root/"production-events.jsonl").read_text().splitlines() if line.strip()]
    events=lambda label:[r for r in rows if r.get("event")==label]
    compiled=events("ui01e_scene_submit")
    assert len(compiled)>=3, "no real native draw sequence"
    assert all(r["input_layers"]==4 and r["composed_layers"]==4
           and r["total_commands"]==64 and r["adapter_draw_commands"]==64
           and r["filled_rectangles"]==60 and r["vector_segments"]==4
           and r["persistent_allocations"]==2
           for r in compiled), "native renderer did not draw 64 commands"
    a,b,c=events("ui01a_native_submit"),events("ui01b_native_submit"),events("ui01c_native_submit")
    assert all(len(x)>1 for x in (a,b,c)), "first-party production widgets not painted"
    assert {a[0]["surface"],b[0]["surface"],c[0]["surface"]}=={0x10a,0x10b,0x10c}
    assert all(r["commands"]==3 for r in a+b+c)
    req,frames=events("request"),events("presented")
    assert [r["revision"] for r in req]==[3,4],f"wrong SDF requests {req}"
    assert [r["revision"] for r in frames]==[3,4],"not actual native SDF frames"
    assert all(r["backend"]=="cpu" for r in req)
    assert all(r["backend_actual"]=="cpu" for r in frames)
    assert all(r["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for r in frames)
    assert len(events("ui01e_gpu_pixels"))==1
    captured=events("ui01e_gpu_pixels")[0]
    assert captured["state"]=="vector-strokes" and captured["bytes"]==1280*800*4
    assert captured["format"]=="Rgba8Unorm" and captured["width"]==1280 and captured["height"]==800
    log=(root/"weston.stderr").read_text()
    assert all(token in log for token in (
         "BLOB_UI01E_PRIVATE_SEAT_READY",
         "BLOB_UI01E_COMPOSITOR_BUTTON_DOWN","BLOB_UI01E_COMPOSITOR_BUTTON_UP",
         "BLOB_UI01E_COMPOSITOR_TOGGLE_UP",
         "BLOB_UI01E_COMPOSITOR_FINISHED",
    )), "missing compositor provenance"
    assert "panicked" not in (root/"showcase.stderr").read_text()
    assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    source=root/"vector-strokes.raw"
    raw=source.read_bytes() if source.exists() else gzip.decompress(
        (root/"vector-strokes.rgba.gz").read_bytes())
    assert len(raw)==1280*800*4
    im=Image.frombytes("RGBA",(1280,800),raw)
    count=0
    centers=[]
    for i in range(51):
        center=(129+24*(i%11),114+24*(i//11))
        pixel=im.getpixel(center)
        assert pixel==(224,70,130,255),f"GPU stress pixel mismatch at {center}: {pixel}"
        centers.append(center)
        count+=1
    for point in ((510,140),(550,170),(585,200),(620,170)):
        assert im.getpixel(point)==(20,230,150,255), f"real vector line missing at {point}"
    for point in ((510,154),(520,160)):
        assert im.getpixel(point)!=(20,230,150,255), f"false filled rectangle at {point}"
    # Independent extra-region witness: widget and background not repainted by
    # fixture data, and the private swapchain is not a synthetic drawing.
    expected={
        (400,50):(0,0,0,255),
        (952,344):(22,39,51,255),
        (975,670):(49,95,121,255),
    }
    for point,value in expected.items():
        assert im.getpixel(point)==value,f"existing UI changed at {point}"
    rawhash=digest(raw)
    if recorded:
        assert rawhash==recorded["original_gpu_rgba_sha256"],"raw GPU witness mutated"
        with Image.open(root/"vector-strokes.png") as png:
            assert png.convert("RGBA").tobytes()==raw,"PNG != original source pixels"
    result={
        "verdict":"SCOPED_PASS_REAL_WGPU_64_COMMAND_VECTOR_SCENE",
        "scene":"3 live controls + 51 private rectangles + 4 real vector stroke segments",
        "input_layers":4,"composed_layers":4,"gpu_draw_commands":64,
        "gpu_uniform_buffer_and_bind_group_resident":2,
        "verified_stress_shape_pixels":count,
        "verified_stroke_center_pixels":4,
        "vector_segments":4,
        "gpu_source_extent":[1280,800],
        "original_gpu_rgba_sha256":rawhash,
        "real_renderer":"blobin_renderd CPU",
        "sdf_revisions":[3,4],"sdf_frame_count":2,
        "compositor_present_feedback":False,"gpu_sdf_qualified":False,
        "physical_hid":False,"cp03_hybrid60":"NOT_PASS",
        "stress_fixture_confined_to_private_wayland":True,
        "stress_not_an_fps_benchmark":True,
    }
    if destination:
        destination.mkdir(parents=True,exist_ok=True)
        im.save(destination/"vector-strokes.png","PNG",compress_level=9)
        (destination/"vector-strokes.rgba.gz").write_bytes(gzip.compress(raw,compresslevel=9,mtime=0))
        for sourcefile in ("production-events.jsonl","weston.stderr","weston.log",
                           "renderd.stdout","renderd.stderr","showcase.stderr"):
            shutil.copy2(root/sourcefile,destination/sourcefile)
        result["archive_sha256"]={
            file.name:digest(file.read_bytes()) for file in destination.iterdir() if file.is_file()
             and file.name!="native-qualification.json"
        }
        (destination/"native-qualification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--destination",type=Path)
    parser.add_argument("--negative",choices=["none","trace","png"],default="none")
    args=parser.parse_args()
    try:
        if args.negative!="none":
            with tempfile.TemporaryDirectory(prefix="blob-ui01e-corrupt-") as temp:
                path=Path(temp)/"altered"
                shutil.copytree(args.source,path)
                if args.negative=="trace":
                    trace=path/"production-events.jsonl"
                    entries=[json.loads(line) for line in trace.read_text().splitlines()]
                    for r in entries:
                        if r.get("event")=="ui01e_scene_submit":r["total_commands"]=65
                    trace.write_text("\n".join(json.dumps(r) for r in entries)+"\n")
                else:
                    source=path/"vector-strokes.png"
                    raw=bytearray(source.read_bytes());raw[-19]^=16;source.write_bytes(raw)
                try:qualify(path)
                except (AssertionError,ValueError,OSError,KeyError):
                    print("BLOB_UI01E_REJECTED_NEGATIVE",args.negative)
                    return 0
                print("BLOB_UI01E_ACCEPTED_BAD_EVIDENCE")
                return 1
        print(json.dumps(qualify(args.source,args.destination),indent=2,sort_keys=True))
        return 0
    except (AssertionError,ValueError,OSError,KeyError) as err:
        print("BLOB_UI01E_HOLD",repr(err),file=sys.stderr)
        return 1
if __name__=="__main__":raise SystemExit(main())
