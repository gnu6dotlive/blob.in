#!/usr/bin/env python3
"""01G independent client-GPU pixel oracle: strict convex fill, closed rounded
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
    composed=get("ui01g_scene_submit")
    assert len(composed)>2
    assert all(x["input_layers"]==4 and x["composed_layers"]==4
       and x["filled_rectangles"]==26 and x["triangle_fills"]==3
       and x["vector_strokes"]==35 and x["total_commands"]==64
       and x["adapter_draw_commands"]==64
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
    events=get("ui01g_gpu_pixels")
    assert len(events)==1 and events[0]["state"]=="convex-closed-paths"
    assert events[0]["format"]=="Rgba8Unorm" and events[0]["bytes"]==1280*800*4
    assert events[0]["width"]==1280 and events[0]["height"]==800
    weston=(root/"weston.stderr").read_text()
    for mark in ("BLOB_UI01G_PRIVATE_SEAT_READY","BLOB_UI01G_COMPOSITOR_BUTTON_DOWN",
                 "BLOB_UI01G_COMPOSITOR_BUTTON_UP","BLOB_UI01G_COMPOSITOR_TOGGLE_UP",
                 "BLOB_UI01G_COMPOSITOR_FINISHED"):
        assert mark in weston,mark
    assert "panicked" not in (root/"showcase.stderr").read_text()
    assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    rawfile=root/"convex-closed-paths.raw"
    rgba=rawfile.read_bytes() if rawfile.exists() else gzip.decompress(
        (root/"convex-closed-paths.rgba.gz").read_bytes())
    assert len(rgba)==1280*800*4
    im=Image.frombytes("RGBA",(1280,800),rgba)
    # Strictly independent point-in-convex-region expectations: no triangle
    # tessellation reads in the oracle. Sample the *interior shared diagonal*
    # to reject visible seams between fan triangles.
    blue=(30,110,230,255);magenta=(200,60,180,255)
    orange=(250,180,40,255);green=(20,230,150,255)
    square_interior=[(735,145),(715,130),(745,167),(730,150)]
    diagonal=[(p,p-590) for p in range(710,761,10)]
    triangle_interior=[(850,150),(840,163),(855,175)]
    square_outline=[(735,110),(700,110),(701,111),(697,145)]
    triangle_outline=[(830,155),(830,185),(830,115),(900,175),(875,157)]
    for points,expected in ((square_interior+diagonal,blue),
                             (triangle_interior,magenta),
                             (square_outline+triangle_outline,orange)):
        for pt in points:
            assert im.getpixel(pt)==expected,f"convex fill/edge failure at {pt}"
    for p in ((780,145),(800,145),(820,145),(400,50)):
        assert im.getpixel(p)==(0,0,0,255),f"leaked fill at {p}"
    # Preserve the exact prior 01F curve, whose shader draws 28 segments.
    curves=[
        ((480.,140.),(515.,220.),(550.,140.)),
        ((575.,145.),(590.,225.),(640.,225.),(655.,145.)),
    ]
    for curve in curves:
        for i in range(33):
            pt=tuple(round(v) for v in bernstein(curve,i/32))
            assert im.getpixel(pt)==green,f"prior 01F stroke changed at {pt}"
    for i in range(17):
        pt=(129+24*(i%11),114+24*(i//11))
        assert im.getpixel(pt)==(224,70,130,255),f"original 01D fill missing {pt}"
    for pt,expected in { (952,344):(22,39,51,255),
                         (975,670):(49,95,121,255)}.items():
        assert im.getpixel(pt)==expected,f"production widget changed at {pt}"
    origsha=sha(rgba)
    if sealed:
        assert sealed["original_gpu_rgba_sha256"]==origsha,"RGBA SHA mismatched"
        with Image.open(root/"convex-closed-paths.png") as png:
            assert png.convert("RGBA").tobytes()==rgba,"PNG != native pixels"
    result={
      "verdict":"SCOPED_PASS_NATIVE_CONVEX_CLOSED_PATH_FILLED_TRIANGLES",
      "shapes":"two strictly convex simple polygons (square + triangle)",
      "closed_round_stroke_segments":7,
      "quadratic_cubic_stroke_segments":28,
      "filled_triangles":3,"rectangles":26,"strokes":35,
      "total_native_gpu_commands":64,"composition_layers":4,
      "sdf_cpu_revisions":[3,4],"sdf_frames":2,
      "independent_polygon_interior_pixels":len(square_interior)+len(triangle_interior),
      "independent_shared_diagonal_no_seam_pixels":len(diagonal),
      "independent_closed_outline_pixels":len(square_outline)+len(triangle_outline),
      "prior_01f_curve_sample_pixels":66,
      "prior_rectangle_centers":17,
      "original_gpu_rgba_sha256":origsha,
      "gpu_witness_width":1280,"gpu_witness_height":800,
      "polygon_types_qualified":"strict convex only; no holes, no concavity",
      "internal_triangle_aa_qualified":False,
      "joins":"opaque overlapping round-caps, no bevel/miter",
      "compositor_present_feedback":False,
      "renderer":"real blobin_renderd CPU + real showcase wgpu",
      "gpu_sdf_qualified":False,"cp03_hybrid60":"NOT_PASS",
    }
    if destination:
        destination.mkdir(parents=True,exist_ok=True)
        im.save(destination/"convex-closed-paths.png","PNG",compress_level=9)
        (destination/"convex-closed-paths.rgba.gz").write_bytes(gzip.compress(rgba,compresslevel=9,mtime=0))
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
            with tempfile.TemporaryDirectory(prefix="01g-adversarial-") as td:
                copy=Path(td)/"tampered"
                shutil.copytree(args.source,copy)
                if args.negative=="trace":
                    path=copy/"production-events.jsonl"
                    events=[json.loads(x) for x in path.read_text().splitlines()]
                    for row in events:
                        if row.get("event")=="ui01g_scene_submit":row["triangle_fills"]=77
                    path.write_text("\n".join(json.dumps(x) for x in events)+"\n")
                else:
                    path=copy/"convex-closed-paths.png"
                    contents=bytearray(path.read_bytes());contents[-19]^=16
                    path.write_bytes(contents)
                try:check(copy)
                except (OSError,ValueError,AssertionError,KeyError):
                    print("BLOB_UI01G_NEGATIVE_REJECTED",args.negative)
                    return 0
                print("BLOB_UI01G_NEGATIVE_INCORRECTLY_ACCEPTED")
                return 1
        print(json.dumps(check(args.source,args.destination),indent=2,sort_keys=True))
        return 0
    except (OSError,ValueError,AssertionError,KeyError) as err:
        print("BLOB_UI01G_HOLD",repr(err),file=sys.stderr)
        return 1
if __name__=="__main__":raise SystemExit(main())
