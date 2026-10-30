#!/usr/bin/env python3
"""Independent BLOB-UI-RUNTIME-01A compositor + client-GPU pixel oracle.
Only captures the dedicated private Weston fixture, never the user's desktop.
"""
from pathlib import Path
import argparse,gzip,hashlib,json,shutil,sys,tempfile
from PIL import Image
def sha(data):return hashlib.sha256(data).hexdigest()
def checksum(path):return sha(Path(path).read_bytes())
def check(source:Path,dest:Path|None=None)->dict:
    root=Path(source)
    archived=root/"native-qualification.json"
    if archived.is_file():
        sealed=json.loads(archived.read_text())
        for name,expected in sealed["archives_sha256"].items():
            assert sha((root/name).read_bytes())==expected, f"archived artifact changed: {name}"
    rows=[json.loads(x) for x in (root/"production-events.jsonl").read_text().splitlines() if x.strip()]
    get=lambda name:[r for r in rows if r.get("event")==name]
    compositor=(root/"weston.stderr").read_text()
    for expected in ("BLOB_UI01A_PRIVATE_SEAT_READY","BLOB_UI01A_COMPOSITOR_MOVE_TO_TOGGLE",
                     "BLOB_UI01A_COMPOSITOR_BUTTON_DOWN","BLOB_UI01A_COMPOSITOR_BUTTON_UP",
                     "BLOB_UI01A_COMPOSITOR_FINISHED"):
        if expected not in compositor:
            raise ValueError(f"missing compositor-origin event {expected}")
    native=get("ui01a_native_submit")
    captures=get("ui01a_gpu_pixels")
    requests=get("request")
    presented=get("presented")
    pointer=get("ac05_winit_pointer")
    assert [x["revision"] for x in requests]==[3],f"UI toggle rerendered SDF {requests}"
    assert [x["revision"] for x in presented]==[3],f"unexpected SDF receipts {presented}"
    assert len(native)>=2 and native[0]["overlay_state"] is True
    assert any(r["overlay_state"] is False and r["ui_revision"]==2 for r in native)
    assert all(r["node"]==native[0]["node"] and r["commands"]==3 for r in native)
    assert all(r["layout_epoch"]==native[0]["layout_epoch"] for r in native)
    assert all(r["bounds"]==[946.0,623.0,52.0,26.0] and r["clip"]==r["bounds"] for r in native)
    assert [r["toggle"] for r in captures]==["on","off"]
    assert [r["sdf_scene_revision"] for r in captures]==[3,3]
    assert [(r["width"],r["height"],r["bytes"],r["format"]) for r in captures] == [
        (1280,800,4096000,"Rgba8Unorm"),(1280,800,4096000,"Rgba8Unorm")
    ]
    assert any(r.get("kind")=="button" and r.get("state")=="Pressed" for r in pointer)
    assert sum(r.get("kind")=="button" and r.get("state")=="Released" for r in pointer)==1
    assert len([r for r in native if r["overlay_state"] is False])>=1
    assert not get("ui01a_capture_error")
    assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==1
    a={}
    hashes={}
    for name in ("on","off"):
        if (root/f"toggle-{name}.raw").exists():
            raw=(root/f"toggle-{name}.raw").read_bytes()
        else:
            raw=gzip.decompress((root/f"toggle-{name}.rgba.gz").read_bytes())
        assert len(raw)==1280*800*4
        a[name]=Image.frombytes("RGBA",(1280,800),raw)
        hashes[name]=sha(raw)
    samples={str(xy):[list(a["on"].getpixel(xy)),list(a["off"].getpixel(xy))]
             for xy in [(958,636),(986,636),(500,60),(205,400),(946,623)]}
    assert a["on"].getpixel((958,636))!=(255,255,255,255)
    assert a["off"].getpixel((958,636))==(255,255,255,255)
    assert a["on"].getpixel((986,636))==(255,255,255,255)
    assert a["off"].getpixel((986,636))!=(255,255,255,255)
    assert a["on"].getpixel((500,60))==a["off"].getpixel((500,60))
    assert a["on"].getpixel((205,400))==a["off"].getpixel((205,400))
    assert a["on"].getpixel((946,623))==a["off"].getpixel((946,623))
    assert hashes["on"]!=hashes["off"]
    if archived.is_file():
        assert hashes==sealed["on_off_original_rgba_sha256"],"archived original pixel content mutated"
        for name in ("on","off"):
            with Image.open(root/f"toggle-{name}.png") as png:
                assert png.convert("RGBA").tobytes()==a[name].tobytes(), "PNG/GZIP mismatch"
    control_bytes_on=a["on"].crop((946,623,998,649)).tobytes()
    control_bytes_off=a["off"].crop((946,623,998,649)).tobytes()
    changed=sum(x!=y for x,y in zip(control_bytes_on,control_bytes_off))
    assert changed>1000,f"toggle widget pixels did not change: {changed}"
    receipt={
        "verdict":"SCOPED_PASS_REAL_EDITOR_NATIVE_TOGGLE_CLIENT_GPU_PIXELS",
        "scope":"production blobin-showcase + private Weston input + G02/G03 display list + same-swapchain wgpu",
        "gtk_qt_electron_qml_imported":False,
        "egui_input_owner":True,"egui_text_owner":True,
        "blobin_native_toggle_drawing_owner":True,
        "compositor_presentation_feedback":False,"physical_hid":False,
        "sdf_backend":"real blobin_renderd CPU",
        "sdf_request_count":len(requests),"sdf_frame_count":len(presented),
        "sdf_scene_revision":3,
        "control_bounds":[946,623,52,26],
        "g02_ui_revisions":[native[0]["ui_revision"],next(r["ui_revision"] for r in native if not r["overlay_state"])],
        "g03_layout_epoch":native[0]["layout_epoch"],
        "compositor_button_releases":1,
        "on_off_original_rgba_sha256":hashes,
        "pixel_samples":samples,"control_changed_channel_bytes":changed,
        "capture_method":"actual first-party native wgpu compositor-target swapchain COPY_SRC before queue.present",
    }
    if dest is not None:
        dest=Path(dest)
        dest.mkdir(parents=True,exist_ok=True)
        for name in ("on","off"):
            out=dest/f"toggle-{name}.png"
            a[name].save(out,"PNG",compress_level=9)
            content=a[name].tobytes()
            (dest/f"toggle-{name}.rgba.gz").write_bytes(gzip.compress(content,compresslevel=9,mtime=0))
        for name in ("production-events.jsonl","weston.stderr","weston.log","renderd.stderr",
                     "renderd.stdout","showcase.stderr"):
            shutil.copy2(root/name,dest/name)
        receipt["archives_sha256"]={f.name:checksum(f) for f in dest.iterdir() if f.is_file() and f.name != "native-qualification.json"}
        (dest/"native-qualification.json").write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n")
    return receipt
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--destination",type=Path)
    p.add_argument("--negative-test",action="store_true")
    p.add_argument("--negative-png",action="store_true")
    a=p.parse_args()
    if a.negative_png:
        with tempfile.TemporaryDirectory(prefix="blob-ui01a-adversarial-png-") as td:
            out=Path(td)
            shutil.copytree(a.source,out/"mutated")
            png=out/"mutated/toggle-on.png"
            data=bytearray(png.read_bytes())
            data[-14]^=1
            png.write_bytes(data)
            try:
                check(out/"mutated")
                print("NEGATIVE_ORACLE_ACCEPTED_TAMPERED_PNG")
                return 1
            except (AssertionError,ValueError,OSError):
                print("BLOB_UI01A_NEGATIVE_ORACLE_REJECTED_TAMPERED_PNG")
                return 0
    if a.negative_test:
        with tempfile.TemporaryDirectory(prefix="blob-ui01a-adversarial-") as td:
            out=Path(td)
            shutil.copytree(a.source,out/"mutated")
            trace=out/"mutated/production-events.jsonl"
            rows=[json.loads(row) for row in trace.read_text().splitlines()]
            for r in rows:
                if r.get("event")=="request":r["revision"]=4
            trace.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            try:
                check(out/"mutated")
                print("NEGATIVE_ORACLE_ACCEPTED_TAMPERED_TRACE")
                return 1
            except (AssertionError,ValueError):
                print("BLOB_UI01A_NEGATIVE_ORACLE_REJECTED_TAMPERED_REVISION")
                return 0
    try:
        receipt=check(a.source,a.destination)
        print(json.dumps(receipt,indent=2,sort_keys=True))
        return 0
    except (AssertionError,ValueError,KeyError,OSError) as e:
        print("BLOB_UI01A_ORACLE_HOLD",repr(e),file=sys.stderr)
        return 1
if __name__=="__main__":
    raise SystemExit(main())
