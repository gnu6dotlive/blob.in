#!/usr/bin/env python3
"""Independent 01F GPU pixel oracle: actual client readback + Bernstein reference.
The renderer does not synthesize any pixel in this verifier.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,shutil,tempfile,sys
from PIL import Image

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def bernstein(control:tuple[tuple[float,float],...],t:float)->tuple[float,float]:
    a=1.-t
    if len(control)==3:
        weights=(a*a,2.*a*t,t*t)
    else:
        weights=(a*a*a,3.*a*a*t,3.*a*t*t,t*t*t)
    return (
      sum(c[0]*w for c,w in zip(control,weights)),
      sum(c[1]*w for c,w in zip(control,weights)),
    )
def check(folder:Path,destination:Path|None=None)->dict:
    folder=folder.resolve()
    seal=folder/"native-qualification.json"
    recorded=json.loads(seal.read_text()) if seal.is_file() else None
    if recorded:
        for name,d in recorded["archive_sha256"].items():
            assert sha((folder/name).read_bytes())==d, f"tampered archive member {name}"
    rows=[json.loads(line) for line in (folder/"production-events.jsonl").read_text().splitlines() if line.strip()]
    events=lambda kind:[r for r in rows if r.get("event")==kind]
    scene=events("ui01f_scene_submit")
    assert len(scene)>=3 and all(
      r["input_layers"]==4 and r["composed_layers"]==4
      and r["filled_rectangles"]==36 and r["bezier_flattened_segments"]==28
      and r["total_commands"]==64 and r["adapter_draw_commands"]==64
      and r["tolerance_logical_px"]==0.75 and r["persistent_allocations"]==2
      and r["compositor_present_feedback"] is False for r in scene
    ), "incorrect 01F production GPU scene attribution"
    a,b,c=[events(f"ui01{x}_native_submit") for x in ("a","b","c")]
    assert min(len(a),len(b),len(c))>1
    assert {a[0]["surface"],b[0]["surface"],c[0]["surface"]}=={0x10a,0x10b,0x10c}
    assert all(r["commands"]==3 for r in a+b+c)
    requests,presented=events("request"),events("presented")
    assert [r["revision"] for r in requests]==[3,4], "unexpected SDF recomputation"
    assert [r["revision"] for r in presented]==[3,4], "missing real renderer frames"
    assert all(r["backend"]=="cpu" for r in requests)
    assert all(r["backend_actual"]=="cpu" and
       r["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for r in presented)
    pixels=events("ui01f_gpu_pixels")
    assert len(pixels)==1 and pixels[0]["state"]=="bezier-curves"
    assert pixels[0]["format"]=="Rgba8Unorm" and pixels[0]["bytes"]==1280*800*4
    assert (pixels[0]["width"],pixels[0]["height"])==(1280,800)
    weston=(folder/"weston.stderr").read_text()
    for mark in ("BLOB_UI01F_PRIVATE_SEAT_READY",
                 "BLOB_UI01F_COMPOSITOR_BUTTON_DOWN",
                 "BLOB_UI01F_COMPOSITOR_BUTTON_UP",
                 "BLOB_UI01F_COMPOSITOR_TOGGLE_UP",
                 "BLOB_UI01F_COMPOSITOR_FINISHED"):
        assert mark in weston, mark
    assert "panicked" not in (folder/"showcase.stderr").read_text()
    assert (folder/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    original=folder/"bezier-curves.raw"
    rgba=original.read_bytes() if original.is_file() else gzip.decompress(
       (folder/"bezier-curves.rgba.gz").read_bytes())
    assert len(rgba)==1280*800*4
    image=Image.frombytes("RGBA",(1280,800),rgba)
    expected_curve=(20,230,150,255)
    samples={}
    controls={
        "quadratic":((480.,140.),(515.,220.),(550.,140.)),
        "cubic":((575.,145.),(590.,225.),(640.,225.),(655.,145.)),
    }
    for name,curve in controls.items():
        points=[]
        for i in range(33):
            x,y=bernstein(curve,i/32)
            pos=(round(x),round(y))
            actual=image.getpixel(pos)
            assert actual==expected_curve, f"{name} Bernstein t={i}/32 {pos} {actual}"
            points.append(pos)
        samples[name]=points
    for pos in ((515,195),(615,220),(510,185)):
        assert image.getpixel(pos)==(0,0,0,255),f"false fill at {pos}"
    # 27 red rectangles under separate G02 test layer, alongside nine real
    # UI widget commands: 36 rectangle commands total.
    for i in range(27):
        pos=(129+24*(i%11),114+24*(i//11))
        assert image.getpixel(pos)==(224,70,130,255),f"missing rectangle {pos}"
    controls_witness={(400,50):(0,0,0,255),
                      (952,344):(22,39,51,255),
                      (975,670):(49,95,121,255)}
    for pos,pixel in controls_witness.items():
        assert image.getpixel(pos)==pixel,f"prior native widget changed {pos}"
    frame_sha=sha(rgba)
    if recorded:
        assert recorded["original_gpu_rgba_sha256"]==frame_sha,"source pixel SHA mismatch"
        with Image.open(folder/"bezier-curves.png") as png:
            assert png.convert("RGBA").tobytes()==rgba,"archived PNG differs from GPU source"
    result={
      "verdict":"SCOPED_PASS_NATIVE_QUADRATIC_CUBIC_BEZIER_GPU_CLIENT_PIXELS",
      "work":"first-party deterministic De Casteljau adaptive flatness tessellation",
      "curve_count":2,"quadratic_count":1,"cubic_count":1,
      "curve_tolerance_logical_px":0.75,
      "flattened_stroke_segments":28,
      "gpu_fill_commands":36,"gpu_stroke_commands":28,"total_gpu_commands":64,
      "composition_layers":4,
      "curve_bernstein_samples_verified":66,
      "decorative_rectangle_centers_verified":27,
      "independent_curve_sample_positions":samples,
      "original_gpu_rgba_sha256":frame_sha,
      "real_renderer":"blobin_renderd CPU","sdf_revisions":[3,4],
      "input":"private Weston artificial pointer -> real egui",
      "host_window":"real blobin-showcase Wayland",
      "client_swapchain_pixels_before_present":True,
      "compositor_present_feedback":False,"gpu_sdf_qualified":False,
      "physical_hid":False,"cp03_hybrid60":"NOT_PASS",
      "full_bezier_fill_joins_text_runtime_qualified":False,
    }
    if destination:
        destination.mkdir(parents=True,exist_ok=True)
        image.save(destination/"bezier-curves.png","PNG",compress_level=9)
        (destination/"bezier-curves.rgba.gz").write_bytes(gzip.compress(rgba,compresslevel=9,mtime=0))
        for name in ("production-events.jsonl","weston.stderr","weston.log",
                     "renderd.stdout","renderd.stderr","showcase.stderr"):
            shutil.copy2(folder/name,destination/name)
        result["archive_sha256"]={p.name:sha(p.read_bytes()) for p in destination.iterdir()
             if p.is_file() and p.name!="native-qualification.json"}
        (destination/"native-qualification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--destination",type=Path)
    parser.add_argument("--negative",choices=("none","trace","png"),default="none")
    args=parser.parse_args()
    try:
        if args.negative!="none":
            with tempfile.TemporaryDirectory(prefix="blob-ui01f-adversarial-") as tmp:
                copy=Path(tmp)/"tampered"
                shutil.copytree(args.source,copy)
                if args.negative=="trace":
                    trace=copy/"production-events.jsonl"
                    rows=[json.loads(x) for x in trace.read_text().splitlines()]
                    for event in rows:
                        if event["event"]=="ui01f_scene_submit":
                            event["bezier_flattened_segments"]=65
                    trace.write_text("\n".join(json.dumps(x) for x in rows)+"\n")
                else:
                    png=copy/"bezier-curves.png"
                    data=bytearray(png.read_bytes());data[-19]^=16;png.write_bytes(data)
                try:check(copy)
                except (OSError,AssertionError,ValueError,KeyError):
                    print("BLOB_UI01F_NEGATIVE_ORACLE_REJECTED",args.negative)
                    return 0
                print("BLOB_UI01F_NEGATIVE_ORACLE_ACCEPTED_BAD_EVIDENCE",args.negative)
                return 1
        print(json.dumps(check(args.source,args.destination),indent=2,sort_keys=True))
        return 0
    except (OSError,AssertionError,ValueError,KeyError) as err:
        print("BLOB_UI01F_ORACLE_HOLD",repr(err),file=sys.stderr)
        return 1
if __name__=="__main__":raise SystemExit(main())
