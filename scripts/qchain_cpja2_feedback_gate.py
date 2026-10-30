#!/usr/bin/env python3
"""Strict CP-JA2 feedback gate: distinguish all real GPU frame ACKs from terminal sentinel.

Only grants shutdown when all real frames are acknowledged AND no dangling
presentation feedback remains. Never infers ACKs from wgpu submit or Weston alone.
"""
import argparse,json,re
from pathlib import Path

def require(ok,why):
    if not ok:raise ValueError(why)

def evaluate(run):
    client=(run/'viewer.stderr').read_text()
    server=(run/'weston-timeline-proto.log').read_text()
    app=(run/'viewer.stdout').read_text()
    submits=[int(x) for x in re.findall(r'CPI02_WGPU_PRESENT_SUBMITTED seq=(\d+)',app)]
    require(submits==list(range(120)),'SOURCE_SEQUENCE_MISSING')
    request=re.findall(r' -> wp_presentation#\d+\.feedback\(',client)
    received=re.findall(r'wp_presentation_feedback#\d+\.presented\(([^)]*)\)',client)
    emitted=re.findall(r'ev wp_presentation_feedback@\d+\.presented\(([^)]*)\)',server)
    discarded=re.findall(r'wp_presentation_feedback#\d+\.discarded\(',client)
    sentinel='CPJA_SENTINEL_PRESENT' in app
    require(not discarded,'PRESENTATION_DISCARDED')
    require(len(request)==len(emitted),'UNMATCHED_COMPOSITOR_PRESENTATIONS')
    require(received==emitted[:len(received)],'CLIENT_SERVER_FEEDBACK_DISAGREEMENT')
    require(len(received)<=len(emitted),'CLIENT_ACK_COUNT_EXCEEDS_SERVER')
    outstanding=len(emitted)-len(received)
    real_ack=min(len(received),120)
    clean=(not sentinel and len(request)==120 and
           len(received)==120 and outstanding==0)
    return {'schema':'gnu6.qchain.cpja2_feedback_gate.v1',
      'verdict':'CPJA2_TYPED_FINAL_FEEDBACK_SHUTDOWN_HOLD',
      'real_gpu_frames_submitted':120,'presented_on_server':len(emitted),
      'received_on_client':len(received),'genuine_frames_acknowledged':real_ack,
      'sentinel_extra_present':sentinel,
      'outstanding_wayland_feedback':outstanding,
      'diagnostic_trace_looks_complete':clean,
      'typed_app_feedback_received':False,
      'may_report_clean_shutdown':False,
      'claims_60fps':False,'production_ready':False}

def main():
    a=argparse.ArgumentParser()
    a.add_argument('--run',required=True,type=Path)
    a.add_argument('--out',required=True,type=Path)
    args=a.parse_args()
    require(not args.out.exists(),'REFUSE_OVERWRITE')
    report=evaluate(args.run)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(report['verdict'], 'client',report['received_on_client'],
          'server',report['presented_on_server'],
          'dangling',report['outstanding_wayland_feedback'])
    if not report['may_report_clean_shutdown']:
        raise SystemExit(2)
if __name__=='__main__':main()
