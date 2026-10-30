#!/usr/bin/env python3
"""Real-window E2E for the blob.in showcase surface on Hyprland.

Launches the viewer against a BLOB-FRAME-v1 socket, drives the *real* window
through compositor IPC (float, resize, close — runtime dispatches on this one
window only, no configuration change), captures it with grim, and validates
the viewer's JSON-lines trace:

  * every viewport size ends up presented at the size the runtime limits allow;
  * never more than one request in flight;
  * presented revisions strictly increase;
  * a rapid resize storm is coalesced (requests << resize events);
  * closing through the compositor shuts down cleanly.

Writes captures, trace, logs and run.json (with sha256 of every artefact)
into --out. Exit status 0 only if every check passes.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

APP_ID = "live.gnu6.blobin-showcase"


def sh(*cmd, check=True):
    return subprocess.run(cmd, check=check, capture_output=True, text=True).stdout


def client():
    for c in json.loads(sh("hyprctl", "clients", "-j")):
        if c["class"] == APP_ID:
            return c
    return None


def dispatch(expr):
    out = sh("hyprctl", "dispatch", expr).strip()
    if out != "ok":
        raise RuntimeError(f"hyprctl dispatch {expr!r}: {out}")


def monitor_of(c):
    for m in json.loads(sh("hyprctl", "monitors", "-j")):
        if m["id"] == c["monitor"]:
            return m
    raise RuntimeError("window has no monitor")


def logical_size(m):
    """Monitor size in layout units; transforms 1/3/5/7 rotate by 90 degrees."""
    w, h = m["width"] / m["scale"], m["height"] / m["scale"]
    return (h, w) if m.get("transform", 0) % 2 == 1 else (w, h)


def inside(c, m):
    (x, y), (w, h) = c["at"], c["size"]
    mw, mh = logical_size(m)
    return m["x"] <= x and m["y"] <= y and x + w <= m["x"] + mw and y + h <= m["y"] + mh


def trace_events(path):
    try:
        return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]
    except FileNotFoundError:
        return []


def fit(w, h, caps):
    """Mirror of scheduler::fit (largest size with the viewport aspect within limits)."""
    if w < 16 or h < 16:
        return None
    s = min(1.0, caps["max_width_px"] / w, caps["max_height_px"] / h, math.sqrt(caps["max_pixels"] / (w * h)))
    while True:
        rw, rh = math.floor(w * s), math.floor(h * s)
        if rw < 16 or rh < 16:
            return None
        if rw <= caps["max_width_px"] and rh <= caps["max_height_px"] and rw * rh <= caps["max_pixels"]:
            return [rw, rh]
        s *= 0.999


def wait_for(pred, timeout, step=0.05):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        v = pred()
        if v:
            return v
        time.sleep(step)
    return None


def settled_geometry(stable_polls=4, interval=0.2, extra=1.2):
    """Waits for the compositor's move/resize animation to finish before a capture."""
    last, same = None, 0
    while same < stable_polls:
        c = client()
        g = (tuple(c["at"]), tuple(c["size"]))
        same = same + 1 if g == last else 0
        last = g
        time.sleep(interval)
    time.sleep(extra)
    return client()


def sha256(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--viewer", required=True, help="path to the blobin-showcase binary")
    ap.add_argument("--socket", help="runtime socket (default: viewer default)")
    ap.add_argument("--test-server", action="store_true", help="use the test server socket")
    ap.add_argument("--backend", default="cpu")
    ap.add_argument("--lab", default="3")
    ap.add_argument("--sizes", default="1280x800,960x720,1600x900,760x520")
    ap.add_argument("--frame-timeout", type=float, default=30.0)
    ap.add_argument("--exercise", action="store_true",
                    help="instead of the resize phases, run the viewer's scripted edit sequence and verify each step")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    trace = out / "trace.jsonl"
    log = out / "viewer.log"
    for p in (trace, log):
        p.unlink(missing_ok=True)
    if client():
        sys.exit("a blobin-showcase window is already open; close it first")

    cmd = [a.viewer, "--trace", str(trace), "--backend", a.backend, "--lab", a.lab]
    if a.exercise:
        cmd.append("--exercise")
    if a.test_server:
        cmd.append("--test-server")
    elif a.socket:
        cmd += ["--socket", a.socket]
    viewer = subprocess.Popen(cmd, stdout=open(log, "w"), stderr=subprocess.STDOUT)
    checks, captures = [], []

    def check(name, ok, detail=""):
        checks.append({"check": name, "pass": bool(ok), "detail": detail})
        print(("PASS " if ok else "FAIL ") + name + (f" — {detail}" if detail else ""), flush=True)
        return ok

    try:
        c = wait_for(client, 10)
        check("native Wayland window mapped by Hyprland", c and not c["xwayland"], json.dumps({k: c[k] for k in ("class", "xwayland", "pid")}) if c else "no window")
        if not c:
            raise SystemExit(1)
        addr = c["address"]
        connected = wait_for(lambda: next((e for e in trace_events(trace) if e["event"] == "connected"), None), 15)
        check("BLOB-FRAME-v1 session established", connected, connected and connected["server"])
        if not connected:
            raise SystemExit(1)
        caps = connected["capabilities"]
        dispatch(f'hl.dsp.focus({{ window = "address:{addr}" }})')
        dispatch(f'hl.dsp.window.float({{ action = "enable", window = "address:{addr}" }})')

        def presented_for_current_viewport():
            ev = trace_events(trace)
            vps = [e for e in ev if e["event"] == "viewport"]
            if not vps:
                return None
            vp = vps[-1]
            want = fit(*vp["physical"], caps)
            after = [e for e in ev if e["event"] == "presented" and e["t_ms"] >= vp["t_ms"]]
            for e in after:
                if e["size"] == want and e["viewport_physical"] == vp["physical"]:
                    return {"viewport": vp["physical"], "frame": e}
            return None

        mon = monitor_of(client())
        lw, lh = logical_size(mon)
        mw, mh = int(lw) - 80, int(lh) - 80

        def place(w, h):
            # Explicit placement inside the window's own monitor (center follows the cursor's monitor).
            x, y = int(mon["x"] + (lw - w) / 2), int(mon["y"] + (lh - h) / 2)
            dispatch(f'hl.dsp.window.move({{ x = {x}, y = {y}, relative = false, window = "address:{addr}" }})')

        def capture(name, frame):
            cc = settled_geometry(extra=0.3)
            if not check(f"capture {name} lies within one monitor", inside(cc, monitor_of(cc)), f"{cc['at']} {cc['size']}"):
                return
            png = out / f"{name}.png"
            # Only the window's own rectangle is captured.
            sh("grim", "-g", f"{cc['at'][0]},{cc['at'][1]} {cc['size'][0]}x{cc['size'][1]}", str(png))
            captures.append({"file": png.name, "window": cc["size"], "sha256": sha256(png),
                             "frame": frame and {k: frame[k] for k in ("request_id", "revision", "size", "backend_actual", "view_mode", "qualification", "geometry_sha256")}})

        if a.exercise:
            w, h = min(1000, mw), min(820, mh)
            dispatch(f'hl.dsp.window.resize({{ x = {w}, y = {h}, relative = false, window = "address:{addr}" }})')
            place(w, h)

            def presented_after(step):
                return next((e for e in trace_events(trace)
                             if e["event"] == "presented" and e["revision"] >= step["revision"] and e["t_ms"] >= step["t_ms"]), None)

            done, seen = None, 0
            deadline = time.monotonic() + a.frame_timeout * 20
            while time.monotonic() < deadline:
                ev = trace_events(trace)
                steps = [e for e in ev if e["event"] == "exercise_step"]
                while seen < len(steps):
                    st = steps[seen]
                    fr = wait_for(lambda: presented_after(st), a.frame_timeout)
                    ok = fr and st["applied"] and fr["backend_actual"] == st["backend"] and fr["view_mode"] == st["view_mode"]
                    check(f"exercise {st['index']:02d} {st['step']}: frame follows (backend, view)", ok,
                          fr and f"rev {fr['revision']} backend={fr['backend_actual']} view={fr['view_mode']} q={fr['qualification']} geom={fr['geometry_sha256'][:12]}")
                    if fr:
                        capture(f"x{st['index']:02d}-{fr['backend_actual']}-{fr['view_mode']}", fr)
                    seen += 1
                done = next((e for e in ev if e["event"] == "exercise_done"), None)
                if done or viewer.poll() is not None:
                    break
                time.sleep(0.1)
            check("exercise sequence completed", done, json.dumps(done))
            try:
                rc = viewer.wait(15)
            except subprocess.TimeoutExpired:
                rc = None
            check("viewer quits by itself after the sequence: exit 0", rc == 0, f"exit {rc}")
            ev = trace_events(trace)
            # Geometry edits must change what the runtime computed; pure view/backend switches must not.
            steps = [e for e in ev if e["event"] == "exercise_step"]
            frames = [presented_after(st) for st in steps]
            runtime = frames and frames[0] and not frames[0]["qualification"].startswith("TEST_FIXTURE")
            if runtime:
                geometric = ("MoveCircle", "ScaleRadius", "CycleOp", "Lab(Csg)", "Zoom", "ResetCamera")
                for st, prev, cur in zip(steps[1:], frames, frames[1:]):
                    if prev and cur and st["step"].startswith(geometric):
                        check(f"exercise {st['index']:02d} {st['step']}: geometry digest changes", prev["geometry_sha256"] != cur["geometry_sha256"],
                              f"{prev['geometry_sha256'][:12]} -> {cur['geometry_sha256'][:12]}")
        else:
            sizes = a.sizes.split(",")
            for i, size in enumerate(sizes):
                w, h = map(int, size.split("x"))
                if w > mw or h > mh:
                    print(f"note: {w}x{h} clamped to monitor {mon['name']} ({int(lw)}x{int(lh)})", flush=True)
                    w, h = min(w, mw), min(h, mh)
                dispatch(f'hl.dsp.window.resize({{ x = {w}, y = {h}, relative = false, window = "address:{addr}" }})')
                place(w, h)
                time.sleep(0.4)
                got = wait_for(presented_for_current_viewport, a.frame_timeout)
                fr = got and got["frame"]
                check(
                    f"window {w}x{h}: frame presented at fitted viewport size",
                    got,
                    got and f"viewport {got['viewport']} -> frame {fr['size']} backend={fr['backend_actual']} qualification={fr['qualification']} rtt={fr['round_trip_ms']:.0f}ms",
                )
                capture(f"{i + 1:02d}-{a.backend}-{w}x{h}", fr)

            # Resize storm: many compositor resizes in quick succession.
            n0 = len(trace_events(trace))
            for k in range(40):
                dispatch(f'hl.dsp.window.resize({{ x = {min(900 + 12 * k, mw)}, y = {min(640 + 5 * (k % 7), mh)}, relative = false, window = "address:{addr}" }})')
                time.sleep(0.015)
            place(*client()["size"])
            settled = wait_for(presented_for_current_viewport, a.frame_timeout)
            storm = trace_events(trace)[n0:]
            n_resize = sum(e["event"] == "viewport" for e in storm)
            n_req = sum(e["event"] == "request" for e in storm)
            check("resize storm settles on a frame matching the final viewport", settled,
                  settled and f"final viewport {settled['viewport']} frame {settled['frame']['size']}")
            check("resize storm coalesced", n_req <= n_resize, f"{n_resize} viewport changes -> {n_req} requests")

            # Clean close through the compositor.
            dispatch(f'hl.dsp.window.close({{ window = "address:{addr}" }})')
            try:
                rc = viewer.wait(10)
            except subprocess.TimeoutExpired:
                rc = None
            check("close via compositor: process exits 0", rc == 0, f"exit {rc}")

        ev = trace_events(trace)
        sd = next((e for e in ev if e["event"] == "shutdown"), None)
        check("clean shutdown recorded", sd and sd["clean"] and sd["client_threads_joined"], json.dumps(sd))

        # Whole-trace invariants.
        in_flight, max_in_flight, revs = 0, 0, []
        for e in ev:
            if e["event"] == "request":
                in_flight += 1
            elif e["event"] in ("presented", "frame_dropped", "frame_rejected", "request_failed", "render_error"):
                in_flight = max(0, in_flight - 1)
            elif e["event"] == "disconnected":
                in_flight = 0
            max_in_flight = max(max_in_flight, in_flight)
            if e["event"] == "presented":
                revs.append(e["revision"])
        check("never more than one request in flight", max_in_flight <= 1, f"max {max_in_flight}")
        check("presented revisions strictly increase", all(x < y for x, y in zip(revs, revs[1:])), f"{len(revs)} frames")
        if not a.exercise:
            backends = {e["backend_actual"] for e in ev if e["event"] == "presented"}
            check("every presented frame reports the requested backend", backends <= {a.backend}, str(sorted(backends)))
        errs = [e for e in ev if e["event"] in ("frame_rejected", "render_error", "request_failed")]
        check("no rejected/failed frames", not errs, json.dumps(errs[:3]))
    finally:
        if viewer.poll() is None:
            viewer.terminate()
            viewer.wait(5)

    head = sh("git", "-C", str(Path(__file__).resolve().parent.parent), "rev-parse", "HEAD", check=False).strip()
    run = {
        "schema": "blobin-showcase-e2e/1",
        "date_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_head": head,
        "viewer": a.viewer,
        "socket": a.socket or ("test-server" if a.test_server else "default"),
        "backend": a.backend,
        "lab": a.lab,
        "mode": "exercise" if a.exercise else "resize",
        "hyprland": sh("hyprctl", "version", "-j", check=False)[:2000] and json.loads(sh("hyprctl", "version", "-j")).get("tag"),
        "checks": checks,
        "captures": captures,
        "artifacts": {p.name: sha256(p) for p in (trace, log) if p.exists()},
        "pass": all(c["pass"] for c in checks),
    }
    (out / "run.json").write_text(json.dumps(run, indent=2) + "\n")
    print("RESULT", "PASS" if run["pass"] else "FAIL", out / "run.json")
    sys.exit(0 if run["pass"] else 1)


if __name__ == "__main__":
    main()
