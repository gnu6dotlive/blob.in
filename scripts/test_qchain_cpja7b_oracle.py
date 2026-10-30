#!/usr/bin/env python3
"""Negative qualification controls for independent CP-JA7B visual oracle."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from qchain_cpja7b_independent_oracle import audit

EVIDENCE = Path("/mnt/workbench/evidence/runs/qchain-cpja7b-20261010-01")
BASELINE = Path("/mnt/workbench/evidence/runs/qchain-gpu-execution-01/20261010-cpf-persistent-01/raw")
RUN = EVIDENCE / "runs/typed-visible-drop-20261011b"


def copy_fixture(where):
    where.mkdir()
    for name in ("run-verdict.json", "viewer.stdout", "viewer.stderr", "weston.stdout", "weston-timeline-proto.log"):
        shutil.copy2(RUN/name, where/name)
    for path in sorted(RUN.glob("sample-*.png")):
        shutil.copy2(path, where/path.name)


def alter_capture(where, idx, alter):
    path=where/f"sample-{idx:02}.png"
    with Image.open(path) as image:
        rgba=np.asarray(ImageOps.flip(image.convert("RGBA"))).copy()
    alter(rgba)
    ImageOps.flip(Image.fromarray(rgba,"RGBA")).save(path)
    receipt=json.loads((where/"run-verdict.json").read_text())
    entry=receipt["samples"][idx]
    entry["screenshot_sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
    left=rgba[190:574,92:604,:]
    right=rgba[190:574,810:1322,:]
    entry["primary_region_rgba_sha256"]=hashlib.sha256(left.tobytes()).hexdigest()
    entry["secondary_region_rgba_sha256"]=hashlib.sha256(right.tobytes()).hexdigest()
    (where/"run-verdict.json").write_text(json.dumps(receipt,indent=2)+"\n")


def pixel_over3(rgba):
    rgba[210,125,0] = (int(rgba[210,125,0])+60)%256


def resurrect_secondary(rgba):
    raw=(BASELINE/"state4-metal-frame0-dpr2.gpu-rgba.bin").read_bytes()
    expected=np.frombuffer(raw,np.uint8).reshape(384,512,4).copy()
    expected[:,:16,:]=[0,0,0,255]
    rgba[190:574,810:1322,:]=expected


def alias_surfaces(rgba):
    rgba[190:574,810:1322,:]=rgba[190:574,92:604,:].copy()


def missing_final_frame(where):
    path=where/"viewer.stdout"
    lines=path.read_text().splitlines()
    lines=[l for l in lines if "CPI02_WGPU_PRESENT_SUBMITTED seq=119 " not in l]
    path.write_text("\n".join(lines)+"\n")


def missing_unmap(where):
    p=where/"weston.stdout"
    p.write_text("\n".join(x for x in p.read_text().splitlines()
                           if "CPJA7B_TILE_VIEWS count=1" not in x)+"\n")


def missing_typed_ack(where):
    p=where/"viewer.stderr"
    lines=p.read_text().splitlines()
    lines=[x for x in lines if "CPJA6_TYPED_ACK generation=2 present_id=60 " not in x]
    p.write_text("\n".join(lines)+"\n")


def missing_feedback(where):
    p=where/"weston-timeline-proto.log"
    lines=p.read_text().splitlines()
    for i,x in enumerate(lines):
        if "ev wp_presentation_feedback@" in x and ".presented(" in x:
            del lines[i]
            break
    p.write_text("\n".join(lines)+"\n")


def main():
    # Valid original is checked before any mutation.
    audit(RUN,BASELINE)
    cases=[
        ("rgb_delta_gt_3",lambda w: alter_capture(w,2,pixel_over3),"PRIMARY_PIXEL_ERROR_2"),
        ("closed_secondary_resurrected",lambda w: alter_capture(w,4,resurrect_secondary),"SECONDARY_NOT_VISUALLY_RELEASED_4"),
        ("two_surface_alias",lambda w: alter_capture(w,1,alias_surfaces),"SECONDARY_PIXEL_ERROR_1"),
        ("final_stream_frame_removed",missing_final_frame,"STREAM_GAP_OR_DUPLICATE"),
        ("weston_unmap_event_removed",missing_unmap,"ONE_MAPPED_VIEW_TRANSITION_INCONSISTENT"),
        ("typed_ack_deleted",missing_typed_ack,"SECONDARY_TYPED_VK_ACK_MISSING"),
        ("compositor_feedback_deleted",missing_feedback,"SERVER_CLIENT_FEEDBACK_DIVERGENCE"),
    ]
    with tempfile.TemporaryDirectory(prefix="cpja7b-oracle-adversary-") as temp:
        for case,change,expected in cases:
            root=Path(temp)/case
            copy_fixture(root)
            change(root)
            try:
                audit(root, BASELINE)
            except AssertionError as error:
                if str(error)!=expected:
                    raise AssertionError(f"{case}: unexpected failure {error}")
                print("NEGATIVE_REJECTED",case,expected)
            else:
                raise AssertionError(f"ORACLE_FALSE_ACCEPT_{case}")
    print(f"CPJA7B_ORACLE_NEGATIVE_{len(cases)}_OF_{len(cases)}_PASS")


if __name__=="__main__":
    main()
