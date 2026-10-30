#!/usr/bin/env python3
"""Adversarial tests of CP-JA2 strict shutdown gate on immutable protocol logs."""
import tempfile,unittest
from pathlib import Path
import qchain_cpja2_feedback_gate as gate
NORMAL=Path('/mnt/workbench/evidence/runs/qchain-cpja2-20261010-01/experiments/redraw-only')
SENTINEL=Path('/mnt/workbench/evidence/runs/qchain-cpja-20261010-01/runs/sentinel-01')

def copy_logs(root,source):
    root.mkdir()
    for name in ('viewer.stdout','viewer.stderr','weston-timeline-proto.log'):
        (root/name).symlink_to(source/name)
    return root

def alter(path,fn):
    data=path.read_text()
    path.unlink()
    modified=fn(data)
    assert data!=modified
    path.write_text(modified)

class FeedbackGateTests(unittest.TestCase):
    def test_no_extra_present_does_not_claim_success(self):
        result=gate.evaluate(NORMAL)
        self.assertFalse(result['may_report_clean_shutdown'])
        self.assertEqual((result['received_on_client'],result['presented_on_server']),(119,120))
    def test_sentinel_does_not_cleanly_terminate(self):
        result=gate.evaluate(SENTINEL)
        self.assertEqual(result['genuine_frames_acknowledged'],120)
        self.assertEqual(result['outstanding_wayland_feedback'],1)
        self.assertFalse(result['may_report_clean_shutdown'])
    def test_server_missing_presentation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=copy_logs(Path(temp)/'run',NORMAL)
            def remove_last(s):
                lines=s.splitlines(keepends=True)
                matches=[i for i,x in enumerate(lines) if '.presented(' in x]
                lines.pop(matches[-1]);return ''.join(lines)
            alter(root/'weston-timeline-proto.log',remove_last)
            with self.assertRaisesRegex(ValueError,'UNMATCHED_COMPOSITOR_PRESENTATIONS'):
                gate.evaluate(root)
    def test_client_feedback_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=copy_logs(Path(temp)/'run',NORMAL)
            alter(root/'viewer.stderr',lambda s:s.replace('.presented(','.discarded(',1))
            with self.assertRaisesRegex(ValueError,'PRESENTATION_DISCARDED'):
                gate.evaluate(root)
    def test_forged_client_presented_not_accepted(self):
        with tempfile.TemporaryDirectory() as temp:
            root=copy_logs(Path(temp)/'run',NORMAL)
            emitted=(root/'weston-timeline-proto.log').read_text()
            lines=[x for x in emitted.splitlines() if 'ev wp_presentation_feedback@' in x and '.presented(' in x]
            self.assertEqual(len(lines),120)
            final=lines[-1].split('.presented(')[1]
            target=root/'viewer.stderr'
            original=target.read_text()
            target.unlink()  # Never append through the source-evidence symlink.
            target.write_text(original+'[forged] wp_presentation_feedback#72.presented('+final+'\n')
            result=gate.evaluate(root)
            self.assertTrue(result['diagnostic_trace_looks_complete'])
            self.assertFalse(result['may_report_clean_shutdown'])
            # A log-only gate cannot authenticate log authorship: not production authority.
if __name__=='__main__':unittest.main(verbosity=2)
