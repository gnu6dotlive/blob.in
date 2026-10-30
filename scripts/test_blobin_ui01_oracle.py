#!/usr/bin/env python3
"""Reject false UI claims and modified compositor pixels without editing raw evidence."""
import json,shutil,tempfile
from pathlib import Path
from PIL import Image
from blobin_ui01_oracle import verify
ROOT=Path("/mnt/workbench/evidence/runs/blobin-ui01-20261012-01/runs/native-qualified")

def reject(name,change):
    with tempfile.TemporaryDirectory(prefix="blobin-ui01-negative-") as d:
        dst=Path(d)
        for file in ("smoke-verdict.json","viewer.stdout","viewer.stderr","ui-trace.jsonl"):
            shutil.copy2(ROOT/file,dst/file)
        for file in sorted(ROOT.glob("sample-*.png")):
            shutil.copy2(file,dst/file.name)
        change(dst)
        try:verify(dst)
        except (AssertionError,ValueError,OSError) as exc:
            print("UI01_MUTATION_REJECTED",name,str(exc)[:65],flush=True)
            return
        raise AssertionError("FALSE_UI_PROOF_ACCEPTED_"+name)
def edit_json(root,mutate):
    file=root/"smoke-verdict.json"
    doc=json.loads(file.read_text())
    mutate(doc)
    file.write_text(json.dumps(doc)+"\n")
def change_frame(root):
    p=root/"viewer.stdout"
    p.write_text(p.read_text().replace("frames=180 revisions=6","frames=179 revisions=6"))
def wrong_revision(root):
    p=root/"ui-trace.jsonl"
    rows=[json.loads(x) for x in p.read_text().splitlines()]
    for row in rows:
        if row["kind"]=="scripted_action":
            row["revision"]=99;break
    p.write_text("\n".join(json.dumps(x) for x in rows)+"\n")
def changed_pixel(root):
    p=root/"sample-03.png"
    with Image.open(p) as image:
        rgba=image.convert("RGBA")
        rgba.putpixel((630,500),(255,0,255,255))
        rgba.save(p)
def main():
    assert verify(ROOT)["native_submitted_frames"]==180
    reject("missing_native_frame",change_frame)
    reject("wrong_scene_revision",wrong_revision)
    reject("altered_compositor_pixel",changed_pixel)
    reject("missing_compositor_capture",
           lambda r:(r/"sample-02.png").unlink())
    reject("forged_sixty_fps_pass",
           lambda r:edit_json(r,lambda x:x.update({"steady_60fps_qualified":True})))
    reject("forged_mouse_test",
           lambda r:edit_json(r,lambda x:x.update({"real_pointer_mouse_interactions_automated":True})))
    reject("non_vulkan_backend",
           lambda r:(r/"viewer.stdout").write_text(
             (r/"viewer.stdout").read_text().replace("backend=Vulkan","backend=OpenGL")))
    print("UI01_INDEPENDENT_ADVERSARIAL_7_OF_7_PASS",flush=True)
if __name__=="__main__":main()
