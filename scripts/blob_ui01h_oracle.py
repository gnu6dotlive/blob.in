#!/usr/bin/env python3
"""01H independent client-GPU pixel oracle: strict convex fill, closed rounded
outline, Bézier regressions and native Weston provenance. No synthetic pixels."""
from pathlib import Path
from PIL import Image
import argparse,gzip,hashlib,json,shutil,tempfile,sys
def sha(data):return hashlib.sha256(data).hexdigest()
def bernstein(v,t):
    a=1.-t
    weights=((a*a,2.*a*t,t*t) if len(v)==3
        else (a*a*a,3.*a*a*t,3.*a*t*t,t*t*t))
    return (sum(p[0]*w for p,w in zip(v,weights)),
            sum(p[1]*w for p,w in zip(v,weights)))
def check(root:Path,destination:Path|None=None):
    root=root.resolve()
    sealed_path=root/"native-qualification.json"
    sealed=json.loads(sealed_path.read_text()) if sealed_path.exists() else None
    if sealed:
        for name,digest in sealed["archive_sha256"].items():
            assert sha((root/name).read_bytes())==digest,f"archive modified: {name}"
    rows=[json.loads(x) for x in (root/"production-events.jsonl").read_text().splitlines() if x.strip()]
    get=lambda event:[x for x in rows if x.get("event")==event]
    composed=get("ui01h_scene_submit")
    assert len(composed)>2
    assert all(x["input_layers"]==4 and x["composed_layers"]==4
       and x["rectangles"]==14 and x["triangles"]==12
       and x["strokes"]==28 and x["total_commands"]==54
       and x["adapter_draw_commands"]==54
       and x["persistent_allocations"]==2
       and x["compositor_present_feedback"] is False for x in composed)
    a,b,c=(get(f"ui01{k}_native_submit") for k in ("a","b","c"))
    assert min(len(a),len(b),len(c))>1
    assert {a[0]["surface"],b[0]["surface"],c[0]["surface"]}=={0x10a,0x10b,0x10c}
    assert all(x["commands"]==3 for x in a+b+c)
    requests,frames=get("request"),get("presented")
    assert [x["revision"] for x in requests]==[3,4]
    assert [x["revision"] for x in frames]==[3,4]
    assert all(x["backend"]=="cpu" for x in requests)
    assert all(x["backend_actual"]=="cpu" and
       x["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for x in frames)
    events=get("ui01h_gpu_pixels")
    assert len(events)==1 and events[0]["state"]=="concave-hole"
    assert events[0]["format"]=="Rgba8Unorm" and events[0]["bytes"]==1280*800*4
    assert events[0]["width"]==1280 and events[0]["height"]==800
    weston=(root/"weston.stderr").read_text()
    for mark in ("BLOB_UI01H_PRIVATE_SEAT_READY","BLOB_UI01H_COMPOSITOR_BUTTON_DOWN",
                 "BLOB_UI01H_COMPOSITOR_BUTTON_UP","BLOB_UI01H_COMPOSITOR_TOGGLE_UP",
                 "BLOB_UI01H_COMPOSITOR_FINISHED"):
        assert mark in weston,mark
    assert "panicked" not in (root/"showcase.stderr").read_text()
    assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    rawfile=root/"concave-hole.raw"
    rgba=rawfile.read_bytes() if rawfile.exists() else gzip.decompress(
        (root/"concave-hole.rgba.gz").read_bytes())
    assert len(rgba)==1280*800*4
    im=Image.frombytes("RGBA",(1280,800),rgba)
    blue=(40,130,230,255);pink=(200,65,165,255);green=(20,230,150,255)
    expected={
        (690,120):blue,(780,130):blue,(700,200):blue,
        (730,140):blue,(760,180):(0,0,0,255),
        (745,155):(0,0,0,255),(825,170):(0,0,0,255),
        (860,120):pink,(860,170):pink,(970,180):pink,(920,220):pink,
        (880,180):pink,(960,220):pink,
        (920,165):(0,0,0,255),(900,180):(0,0,0,255),
        (400,50):(0,0,0,255),
        (952,344):(22,39,51,255),(975,670):(49,95,121,255)
    }
    for point,pixel in expected.items():
        assert im.getpixel(point)==pixel, f"concave/hole pixel mismatch {point}"
    curves=[
        ((480.,140.),(515.,220.),(550.,140.)),
        ((575.,145.),(590.,225.),(640.,225.),(655.,145.)),
    ]
    for curve in curves:
        for i in range(33):
            pt=tuple(round(v) for v in bernstein(curve,i/32))
            assert im.getpixel(pt)==green,f"prior 01F stroke changed at {pt}"
    for i in range(5):
        pt=(129+24*(i%11),114+24*(i//11))
        assert im.getpixel(pt)==(224,70,130,255),f"prior 01D rect missing {pt}"
    origsha=sha(rgba)
    if sealed:
        assert sealed["original_gpu_rgba_sha256"]==origsha,"RGBA SHA mismatched"
        with Image.open(root/"concave-hole.png") as png:
            assert png.convert("RGBA").tobytes()==rgba,"PNG != native pixels"
    result={
      "verdict":"SCOPED_PASS_NATIVE_CONCAVE_AND_RECTANGULAR_HOLE",
      "qualified_shapes":"simple L-shape concavity + rectangular frame with one inset rectangular hole",
      "triangles":12,"rectangles":14,"strokes":28,
      "total_native_gpu_commands":54,"composition_layers":4,
      "sdf_cpu_revisions":[3,4],"sdf_frames":2,
      "independent_geometry_pixel_witnesses":len(expected),
      "prior_01f_curve_sample_pixels":66,"prior_rectangle_centers":5,
      "original_gpu_rgba_sha256":origsha,
      "renderer":"real blobin_renderd CPU + showcase wgpu",
      "gpu_client_readback_before_present":True,
      "antialias_triangle_edges_qualified":False,
      "arbitrary_holes_qualified":False,
      "arbitrary_winding_qualified":False,
      "compositor_present_feedback":False,
      "gpu_sdf_qualified":False,"cp03_hybrid60":"NOT_PASS"
    }
    if destination:
        destination.mkdir(parents=True,exist_ok=True)
        im.save(destination/"concave-hole.png","PNG",compress_level=9)
        (destination/"concave-hole.rgba.gz").write_bytes(gzip.compress(rgba,compresslevel=9,mtime=0))
        for name in ("production-events.jsonl","weston.stderr","weston.log",
                     "renderd.stdout","renderd.stderr","showcase.stderr"):
            shutil.copy2(root/name,destination/name)
        result["archive_sha256"]={f.name:sha(f.read_bytes()) for f in destination.iterdir()
            if f.is_file() and f.name!="native-qualification.json"}
        (destination/"native-qualification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--destination",type=Path)
    p.add_argument("--negative",choices=("none","trace","png"),default="none")
    args=p.parse_args()
    try:
        if args.negative!="none":
            with tempfile.TemporaryDirectory(prefix="01h-adversarial-") as td:
                copy=Path(td)/"tampered"
                shutil.copytree(args.source,copy)
                if args.negative=="trace":
                    path=copy/"production-events.jsonl"
                    events=[json.loads(x) for x in path.read_text().splitlines()]
                    for row in events:
                        if row.get("event")=="ui01h_scene_submit":row["triangles"]=77
                    path.write_text("\n".join(json.dumps(x) for x in events)+"\n")
                else:
                    path=copy/"concave-hole.png"
                    contents=bytearray(path.read_bytes());contents[-19]^=16
                    path.write_bytes(contents)
                try:check(copy)
                except (OSError,ValueError,AssertionError,KeyError):
                    print("BLOB_UI01H_NEGATIVE_REJECTED",args.negative)
                    return 0
                print("BLOB_UI01H_NEGATIVE_INCORRECTLY_ACCEPTED")
                return 1
        print(json.dumps(check(args.source,args.destination),indent=2,sort_keys=True))
        return 0
    except (OSError,ValueError,AssertionError,KeyError) as err:
        print("BLOB_UI01H_HOLD",repr(err),file=sys.stderr)
        return 1
if __name__=="__main__":raise SystemExit(main())
