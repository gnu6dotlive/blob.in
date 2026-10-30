#!/usr/bin/env python3
"""CP-J non-destructive adversarial protocol and clock oracle tests."""
import tempfile,unittest
from pathlib import Path
import qchain_cpj_presentation_oracle as oracle
RUN=Path("/mnt/workbench/evidence/runs/qchain-cpj-20261010-01/runs/protocol-04")
def copy_run(tmp):
    root=Path(tmp)/"run";root.mkdir()
    for f in RUN.iterdir():
        if f.is_file():(root/f.name).symlink_to(f)
        elif f.name=="engine-ledger":
            e=root/f.name;e.mkdir()
            for sub in f.iterdir(): (e/sub.name).symlink_to(sub)
    return root
def change(root,name,alter):
    file=root/name
    content=file.read_text()
    after=alter(content)
    assert content!=after
    file.unlink();file.write_text(after)
class PresentationNegatives(unittest.TestCase):
    def test_actual_server_120_client_119(self):
        a=oracle.verify(RUN)
        self.assertEqual(a["wp_feedback_presented_by_compositor"],120)
        self.assertEqual(a["wp_feedback_received_by_viewer"],119)
        self.assertEqual(a["client_unconfirmed_seq"],[119])
    def test_server_missing_final_presentation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=copy_run(d)
            def remove_last(text):
                lines=text.splitlines(keepends=True)
                i=max(i for i,x in enumerate(lines) if
                     "ev wp_presentation_feedback@" in x and ".presented(" in x)
                lines.pop(i);return "".join(lines)
            change(p,"weston-timeline-proto.log",remove_last)
            with self.assertRaisesRegex(ValueError,"COMPOSITOR_SOURCE_LOG_DISAGREEMENT"):
                oracle.verify(p)

    def test_wrong_clock_id_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=copy_run(d)
            change(p,"viewer.stderr",lambda x:x.replace(".clock_id(4)",".clock_id(1)",1))
            with self.assertRaisesRegex(ValueError,"CLIENT_PRESENTATION_CLOCK_MISMATCH"):
                oracle.verify(p)
    def test_duplicate_or_ordered_clock_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=copy_run(d)
            change(p,"viewer.stdout",lambda x:x.replace(
                  "CPJ_RAW_PRESENT seq=1 monotonic_raw_ns=",
                  "CPJ_RAW_PRESENT seq=0 monotonic_raw_ns=",1))
            with self.assertRaisesRegex(ValueError,"RAW_APP_CLOCK_INCOMPLETE"):
                oracle.verify(p)
    def test_client_acks_forged_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=copy_run(d)
            change(p,"viewer.stderr",lambda x:x.replace(".presented(",".discarded(",1))
            with self.assertRaisesRegex(ValueError,"COMPOSITOR_SOURCE_LOG_DISAGREEMENT"):
                oracle.verify(p)
if __name__=="__main__":unittest.main(verbosity=2)
