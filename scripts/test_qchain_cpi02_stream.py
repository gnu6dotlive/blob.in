#!/usr/bin/env python3
"""Independent negative evidence mutations, canonical captures remain read-only."""
import json,shutil,tempfile,unittest
from pathlib import Path
from PIL import Image
import qchain_cpi02_independent_oracle as check

R=Path("/mnt/workbench/evidence/runs/qchain-cpi02-20261010-01/weston/run-01")
BASE=Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
CPU=Path("/mnt/workbench/evidence/runs/qchain-cpu-20261010/qchain-reconciliation.json")
def cloned(d):
    result=Path(d)/"run"
    result.mkdir()
    for item in R.iterdir():
        if item.name=="engine-ledger":
            sub=result/item.name;sub.mkdir()
            for f in item.iterdir():(sub/f.name).symlink_to(f)
        elif item.is_file():
            (result/item.name).symlink_to(item)
    return result
def mutated(file,contents):
    file.unlink();file.write_bytes(contents)
class CPI02NegativeTests(unittest.TestCase):
    def test_positive_complete_run(self):
        self.assertEqual(check.verify(R,BASE,CPU)["rendered_frames"],120)
    def test_reordered_source_timeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=cloned(tmp)
            p=run/"engine-ledger/timeline.json"
            v=json.loads(p.read_text());v["frames"][50]["seq"]=49
            mutated(p,(json.dumps(v)+"\n").encode())
            with self.assertRaisesRegex(ValueError,"SEQUENCE_IDENTITY_MISMATCH_50"):
                check.verify(run,BASE,CPU)
    def test_wrong_semantic_scene_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=cloned(tmp);p=run/"viewer.stdout"
            text=p.read_text()
            import re
            old=re.findall(r"scene_sha256=([0-9a-f]{64})",text)
            self.assertGreater(len(old),5)
            text=text.replace("scene_sha256="+old[3],
                 "scene_sha256="+old[0],1)
            mutated(p,text.encode())
            with self.assertRaisesRegex(ValueError,"GPU_FRAME_HASH_DRIFT_3"):
                check.verify(run,BASE,CPU)

    def test_corrupted_compositor_centre_pixel(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=cloned(tmp);png=run/"sample-03.png"
            im=Image.open(png).convert("RGBA")
            color=im.getpixel((256,192))
            im.putpixel((256,192),((color[0]+51)%256,color[1],color[2],color[3]))
            png.unlink();im.save(png)
            with self.assertRaisesRegex(ValueError,"COMPOSITOR_PIXEL_MISMATCH_3"):
                check.verify(run,BASE,CPU)
    def test_unsupported_capture_orientation(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=cloned(tmp);p=run/"weston.log"
            text=p.read_text().replace("screen capture uses y-flip: yes",
                                     "screen capture uses y-flip: no")
            mutated(p,text.encode())
            with self.assertRaisesRegex(ValueError,"SCREEN_COORDINATES_UNDECLARED"):
                check.verify(run,BASE,CPU)
if __name__=="__main__":
    unittest.main(verbosity=2)
