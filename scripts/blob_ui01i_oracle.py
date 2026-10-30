#!/usr/bin/env python3
"""Independent 01I client framebuffer oracle; real wgpu pixels + trace provenance."""
from pathlib import Path
from PIL import Image
import argparse,gzip,hashlib,json,shutil,tempfile,sys
def sha(b):return hashlib.sha256(b).hexdigest()
def qualify(root:Path,destination:Path|None=None):
    root=root.resolve()
    sealed=root/"native-qualification.json"
    receipt=json.loads(sealed.read_text()) if sealed.exists() else None
    if receipt:
        for name,expected in receipt["archive_sha256"].items():
            assert sha((root/name).read_bytes())==expected,f"tampered {name}"
    rows=[json.loads(x) for x in (root/"production-events.jsonl").read_text().splitlines() if x.strip()]
    ev=lambda name:[x for x in rows if x.get("event")==name]
    batch=ev("ui01i_scene_submit")
    assert len(batch)>2
    assert all(x["composed_layers"]==4 and x["triangles"]==42 and
       x["commands"]==51 and x["gpu_commands"]==51 and
       x["antialias_external_edges_only"] and
       x["compositor_present_feedback"] is False for x in batch)
    assert all(len(ev(f"ui01{x}_native_submit"))>1 for x in ("a","b","c"))
    assert [x["revision"] for x in ev("request")]==[3,4]
    assert [x["revision"] for x in ev("presented")]==[3,4]
    assert all(x["backend_actual"]=="cpu" for x in ev("presented"))
    pix=ev("ui01i_gpu_pixels")
    assert len(pix)==1 and pix[0]["state"]=="two-holes-aa"
    assert pix[0]["bytes"]==1280*800*4 and pix[0]["format"]=="Rgba8Unorm"
    log=(root/"weston.stderr").read_text()
    for token in ("BLOB_UI01I_PRIVATE_SEAT_READY",
                  "BLOB_UI01I_COMPOSITOR_BUTTON_DOWN",
                  "BLOB_UI01I_COMPOSITOR_BUTTON_UP",
                  "BLOB_UI01I_COMPOSITOR_TOGGLE_UP",
                  "BLOB_UI01I_COMPOSITOR_FINISHED"):
        assert token in log,token
    assert "panicked" not in (root/"showcase.stderr").read_text()
    assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    raw=root/"two-holes-aa.raw"
    bytes_=raw.read_bytes() if raw.exists() else gzip.decompress((root/"two-holes-aa.rgba.gz").read_bytes())
    assert len(bytes_)==1280*800*4
    im=Image.frombytes("RGBA",(1280,800),bytes_)
    fill=(180,80,210,255)
    expected={
      (710,120):fill,(770,130):fill,(860,160):fill,(920,165):fill,(950,240):fill,
      (805,190):fill,(765,210):fill,(880,115):fill,(744,160):fill,
      (765,165):(0,0,0,255),(860,190):(0,0,0,255),
      (746,160):(0,0,0,255),(784,160):(0,0,0,255),
      (841,180):(0,0,0,255),
      (699,140):(0,0,0,255),(400,50):(0,0,0,255),
      (952,344):(22,39,51,255),(975,670):(49,95,121,255),
      # Boundary AA including both outer edge and hole edges:
      (700,140):(152,67,177,255),
      (745,160):(28,13,33,255),
      (785,160):(152,67,177,255),
      (840,180):(28,13,33,255),
      (890,180):(152,67,177,255)
    }
    for pos,want in expected.items():
        got=im.getpixel(pos)
        assert got==want,f"01I real GPU pixel {pos} got {got} wanted {want}"
    # No cracks at internal triangulation: sample centerline of the strips.
    no_seam=[(720,120),(760,125),(810,128),(940,125),(730,235),
             (810,235),(920,235),(800,178)]
    for pos in no_seam:
        assert im.getpixel(pos)==fill,f"internal tessellation seam at {pos}"
    current_sha=sha(bytes_)
    if receipt:
        assert current_sha==receipt["gpu_client_rgba_sha256"]
        with Image.open(root/"two-holes-aa.png") as png:
            assert png.convert("RGBA").tobytes()==bytes_
    result={
      "verdict":"SCOPED_PASS_TWO_RECTANGULAR_HOLES_EVEN_ODD_EDGE_AA",
      "fill_rule":"explicit bounded EvenOdd, one rectangular outer contour and 2 disjoint inner rectangles",
      "hole_count":2,"triangles":42,"native_commands":51,"gpu_composition_layers":4,
      "full_color_and_transparent_pixels":len(expected)-5,
      "antialias_fractional_edge_pixels":5,"internal_seam_pixels":len(no_seam),
      "gpu_client_rgba_sha256":current_sha,
      "sdf_revisions":[3,4],"original_frames":2,
      "gpu_sdf_qualified":False,"compositor_present_feedback":False,
      "svg_arbitrary_winding_qualified":False,"nonrectangular_holes_qualified":False,
      "physical_input_qualified":False,"cp03_hybrid60":"NOT_PASS"
    }
    if destination:
        destination.mkdir(parents=True,exist_ok=True)
        im.save(destination/"two-holes-aa.png","PNG",compress_level=9)
        (destination/"two-holes-aa.rgba.gz").write_bytes(gzip.compress(bytes_,compresslevel=9,mtime=0))
        for name in ("production-events.jsonl","weston.stderr","weston.log",
                     "renderd.stdout","renderd.stderr","showcase.stderr"):
            shutil.copy2(root/name,destination/name)
        result["archive_sha256"]={p.name:sha(p.read_bytes()) for p in destination.iterdir()
            if p.is_file() and p.name!="native-qualification.json"}
        (destination/"native-qualification.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    return result
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--destination",type=Path)
    p.add_argument("--negative",choices=("none","trace","png"),default="none")
    a=p.parse_args()
    try:
        if a.negative!="none":
            with tempfile.TemporaryDirectory(prefix="blob-ui01i-") as temp:
                copy=Path(temp)/"bad";shutil.copytree(a.source,copy)
                if a.negative=="trace":
                    file=copy/"production-events.jsonl"
                    rows=[json.loads(line) for line in file.read_text().splitlines()]
                    for row in rows:
                        if row.get("event")=="ui01i_scene_submit":row["triangles"]=65
                    file.write_text("\n".join(json.dumps(row) for row in rows)+"\n")
                else:
                    file=copy/"two-holes-aa.png"
                    bytes_=bytearray(file.read_bytes());bytes_[-19]^=16;file.write_bytes(bytes_)
                try:qualify(copy)
                except (OSError,AssertionError,ValueError,KeyError):
                    print("BLOB_UI01I_NEGATIVE_REJECTED",a.negative)
                    return 0
                print("BLOB_UI01I_BAD_EVIDENCE_ACCEPTED")
                return 1
        print(json.dumps(qualify(a.source,a.destination),indent=2))
        return 0
    except (OSError,AssertionError,ValueError,KeyError) as e:
        print("BLOB_UI01I_HOLD",repr(e),file=sys.stderr)
        return 1
if __name__=="__main__":sys.exit(main())
