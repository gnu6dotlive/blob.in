#!/usr/bin/env python3
"""BLOB-UI-RUNTIME-01B independent native action+renderer pixel oracle.
Consumes actual client GPU readbacks, not synthetic images.
"""
from pathlib import Path
from PIL import Image
import argparse,hashlib,gzip,json,shutil,tempfile,sys
def sha(x):return hashlib.sha256(x).hexdigest()
def bytes_(p):return Path(p).read_bytes()
def check(root:Path,dest:Path|None=None)->dict:
    root=root.resolve()
    receipt_file=root/"native-qualification.json"
    sealed=json.loads(receipt_file.read_text()) if receipt_file.exists() else None
    if sealed:
        for name,digest in sealed["artifacts_sha256"].items():
            assert sha(bytes_(root/name))==digest, f"tampered artifact {name}"
    rows=[json.loads(s) for s in (root/"production-events.jsonl").read_text().splitlines() if s.strip()]
    events=lambda name:[r for r in rows if r.get("event")==name]
    action=events("ui01b_native_submit")
    toggles=events("ui01a_native_submit")
    gpu=events("ui01b_gpu_pixels")
    old_gpu=events("ui01a_gpu_pixels")
    requests=events("request")
    responses=events("presented")
    pointer=events("ac05_winit_pointer")
    assert len(action)>2 and len(toggles)>2 and len(gpu)==2 and len(old_gpu)==1, "missing native draw/copy"
    assert [r["revision"] for r in requests]==[3,4], "not one initial + one action-triggered SDF request"
    assert [r["revision"] for r in responses]==[3,4], "missing actual SDF response"
    assert all(r["backend"]=="cpu" for r in requests)
    assert all(r["backend_actual"]=="cpu" and r["qualification"]=="CPU_LOCAL_PREVIEW_NOT_GPU_QUALIFIED" for r in responses)
    assert responses[0]["geometry_sha256"]==responses[1]["geometry_sha256"],"visualization must preserve geometric identity"
    assert [r["view_mode"] for r in requests]==["coverage","distance"],"actual view mode did not switch"
    assert [r["view_mode"] for r in responses]==["coverage","distance"],"actual rendered view mode did not switch"
    assert [r["selection"] for r in gpu]==["idle","selected"]
    assert [r["sdf_scene_revision"] for r in gpu]==[3,4]
    assert [r["bytes"] for r in gpu]==[1280*800*4,1280*800*4]
    assert all(r["format"]=="Rgba8Unorm" and r["width"]==1280 and r["height"]==800 for r in gpu)
    bounds=[946.0,331.0,76.0,26.0]
    assert all(r["bounds"]==bounds and r["clip"]==bounds for r in action)
    assert [action[0]["selected"],action[-1]["selected"]]==[False,True]
    assert [action[0]["ui_revision"],action[-1]["ui_revision"]]==[1,2]
    assert all(r["batched_commands"]==6 and r["batched_nodes"]==2
        and r["resident_resource_allocations"]==2 for r in action)
    assert action[-1]["uniform_uploads_total"]<=10, "unexpected churn in uniform writes"
    assert any(not r["uniform_write"] for r in action), "uniform upload repeated every redraw"
    assert len({r["node"] for r in action})==1
    assert len({r["node"] for r in toggles})==1
    # The first widget and second widget need distinct namespace/identity.
    assert toggles[0]["node"]==action[0]["node"]==1, "same local slot is OK only across distinct surfaces"
    assert [toggles[0]["overlay_state"],toggles[-1]["overlay_state"]]==[True,False], "01A toggle did not activate once"
    assert toggles[0]["surface"]==0x010A and action[0]["surface"]==0x010B, "G02 surfaces must be distinct"
    assert old_gpu[0]["toggle"]=="off" and old_gpu[0]["sdf_scene_revision"]==4
    assert toggles[0]["ui_revision"]==1 and toggles[-1]["ui_revision"]==2
    assert any(r.get("kind")=="move" and abs(r["x"]-985)<.01 and abs(r["y"]-344)<.01 for r in pointer)
    assert sum(r.get("kind")=="button" and r.get("state")=="Released" for r in pointer)==2
    compositor=(root/"weston.stderr").read_text()
    assert all(s in compositor for s in (
       "BLOB_UI01B_PRIVATE_SEAT_READY",
       "BLOB_UI01B_COMPOSITOR_MOVE_TO_DISTANCE",
       "BLOB_UI01B_COMPOSITOR_BUTTON_DOWN",
       "BLOB_UI01B_COMPOSITOR_BUTTON_UP",
       "BLOB_UI01B_COMPOSITOR_MOVE_TO_TOGGLE",
       "BLOB_UI01B_COMPOSITOR_TOGGLE_DOWN",
       "BLOB_UI01B_COMPOSITOR_TOGGLE_UP",
       "BLOB_UI01B_COMPOSITOR_FINISHED",
    )), "missing independent compositor seat provenance"
    server=(root/"renderd.stdout").read_text()
    assert "BLOB_FRAME_LISTENING" in server and "PREVIEW_ONLY" in server
    assert (root/"renderd.stderr").read_text().count("BLOB_FRAME_TIMING backend=cpu")==2
    assert "panicked" not in (root/"showcase.stderr").read_text()
    pixels={}
    images={}
    for stage in ("idle","selected","toggle-off"):
        filename=("action-"+stage if stage!="toggle-off" else "toggle-off")
        raw=root/f"{filename}.raw"
        if raw.exists(): content=raw.read_bytes()
        else:content=gzip.decompress((root/f"{filename}.rgba.gz").read_bytes())
        assert len(content)==1280*800*4
        pixels[stage]=sha(content)
        images[stage]=Image.frombytes("RGBA",(1280,800),content)
        if sealed:
            with Image.open(root/f"{filename}.png") as png:
                assert png.convert("RGBA").tobytes()==content,"PNG not derived from raw GPU copy"
    idle,selected=images["idle"],images["selected"]
    samples={str(pos):[list(idle.getpixel(pos)),list(selected.getpixel(pos))]
       for pos in ((952,344),(985,344),(500,70),(205,400),(975,670))}
    assert idle.getpixel((952,344))==(22,39,51,255)
    assert selected.getpixel((952,344))==(49,95,121,255)
    assert idle.getpixel((985,344))!=selected.getpixel((985,344))
    assert idle.getpixel((975,670))==selected.getpixel((975,670)), "other native control changed from Distance click"
    assert selected.getpixel((965,670))==(49,95,121,255) and images["toggle-off"].getpixel((965,670))==(255,255,255,255)
    assert selected.getpixel((986,670))==(255,255,255,255) and images["toggle-off"].getpixel((986,670))==(22,39,51,255)
    assert selected.getpixel((952,344))==images["toggle-off"].getpixel((952,344)), "Distance must remain selected after toggle"

    ctrl_rect=(946,331,1022,357)
    delta=sum(a!=b for a,b in zip(idle.crop(ctrl_rect).tobytes(),selected.crop(ctrl_rect).tobytes()))
    assert delta>2000
    assert pixels["idle"]!=pixels["selected"]
    if sealed:
        assert pixels==sealed["original_rgba_sha256"],"archived client GPU pixels changed"
    report={
        "verdict":"SCOPED_PASS_01B_REAL_UI_ACTION_AND_RENDERER_CPU_GPU_CLIENT_PIXELS",
        "input":"private Weston 15 artificial pointer -> production egui action",
        "graphics":"2 G02/G03 control lists -> one persistent wgpu buffer/group/pass in real Wayland swapchain",
        "source":"actual BLOB-FRAME-v1 renderd CPU, NOT testcard server",
        "compositor_presentation_feedback":False,
        "physical_hid":False,"cp03_hybrid60":"NOT_PASS",
        "input_releases":2,
        "old_toggle_ui_revisions":[1,2],
        "old_toggle_changed_without_new_sdf_request":True,"ui_revision_before_after":[1,2],
        "sdf_requests":2,"sdf_frames":2,"sdf_revisions":[3,4],
        "control_bounds":bounds,"controlled_channel_byte_changes":delta,
        "original_rgba_sha256":pixels,"pixel_samples":samples,
        "persistent_gpu_buffer_and_binding_group_count":2,
        "gpu_uniform_uploads_during_run":action[-1]["uniform_uploads_total"],
        "native_batches_containing_both_widgets":len(action),
        "legacy_toggle_state_unchanged_until_its_own_click":True,
    }
    if dest:
        dest.mkdir(parents=True,exist_ok=True)
        for stage in ("idle","selected","toggle-off"):
            name=("action-"+stage if stage!="toggle-off" else "toggle-off")
            content=images[stage].tobytes()
            (dest/f"{name}.rgba.gz").write_bytes(gzip.compress(content,compresslevel=9,mtime=0))
            images[stage].save(dest/f"{name}.png","PNG",compress_level=9)
        for f in ("production-events.jsonl","weston.stderr","weston.log",
                  "renderd.stdout","renderd.stderr","showcase.stderr"):
            shutil.copy2(root/f,dest/f)
        report["artifacts_sha256"]={f.name:sha(f.read_bytes()) for f in dest.iterdir()
                    if f.is_file() and f.name!="native-qualification.json"}
        (dest/"native-qualification.json").write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--destination",type=Path)
    p.add_argument("--negative",choices=["none","sdf","png"],default="none")
    a=p.parse_args()
    if a.negative!="none":
        with tempfile.TemporaryDirectory(prefix="blob-ui01b-negative-") as td:
            root=Path(td)/"mutated"
            shutil.copytree(a.source,root)
            if a.negative=="sdf":
                trace=root/"production-events.jsonl"
                rows=[json.loads(s) for s in trace.read_text().splitlines()]
                for row in rows:
                    if row.get("event")=="request":row["revision"]=99
                trace.write_text("\n".join(json.dumps(r) for r in rows)+"\n")
            else:
                p=root/"action-selected.png"
                data=bytearray(p.read_bytes())
                data[-20]^=0x10
                p.write_bytes(data)
            try:check(root)
            except (OSError,ValueError,AssertionError,KeyError):
                print("BLOB_UI01B_NEGATIVE_REJECTED",a.negative)
                return 0
            print("BLOB_UI01B_NEGATIVE_ACCEPTED_INVALID",a.negative)
            return 1
    try:
        report=check(a.source,a.destination)
        print(json.dumps(report,indent=2,sort_keys=True))
        return 0
    except (OSError,ValueError,AssertionError,KeyError) as e:
        print("BLOB_UI01B_ORACLE_HOLD",repr(e),file=sys.stderr)
        return 1
if __name__=="__main__":sys.exit(main())
