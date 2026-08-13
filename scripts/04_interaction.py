"""Measure real browser behaviour for the exported interactive HTML files.

Static export size only tells you what has to travel. What a scientist actually
feels is: how long until the plot appears, and does dragging it stay smooth.
This drives a real Chromium against each file over localhost HTTP and records:

  t_load_ms          navigationStart -> load event (parse + deserialize payload)
  t_canvas_ms        navigationStart -> a sized canvas exists
  t_quiet_ms         navigationStart -> main thread sustains 5 frames < 50ms
  pan/zoom fps       frames actually presented during a scripted interaction
  p95_frame_ms       95th-percentile frame time during that interaction
  js_heap_mb         used JS heap once settled

Both XY and Plotly render with WebGL, so whichever GL backend Chromium picks
applies equally to both; the detected renderer is recorded alongside the numbers.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import socketserver
import threading

ARTIFACT_DIR = "results/artifacts"
OUT = "results/interaction.json"
PORT = 8777

# Injected before any interaction: counts presented frames and their durations.
FRAME_RECORDER = """
window.__frames = [];
window.__recording = false;
(function tick(prev){
  requestAnimationFrame(function(now){
    if (window.__recording && prev !== undefined) window.__frames.push(now - prev);
    tick(now);
  });
})();
"""

QUIET_PROBE = """
() => new Promise(resolve => {
  const start = performance.now();
  let good = 0, last = performance.now();
  const deadline = start + 60000;
  function step(now){
    const dt = now - last; last = now;
    if (dt < 50) { good++; } else { good = 0; }
    if (good >= 5) return resolve(performance.now());
    if (now > deadline) return resolve(-1);
    requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
})
"""


def serve(directory: str, port: int):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def summarize(frames: list[float]) -> dict:
    frames = [f for f in frames if f > 0]
    if not frames:
        return {"fps": None, "p95_frame_ms": None, "n_frames": 0}
    ordered = sorted(frames)
    p95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
    return {
        "fps": round(1000.0 * len(frames) / sum(frames), 1),
        "p95_frame_ms": round(p95, 1),
        "median_frame_ms": round(ordered[len(ordered) // 2], 1),
        "n_frames": len(frames),
    }


def measure(page, url: str, label: str, nav_timeout_ms: int) -> dict:
    rec: dict = {"file": label, "status": "ok"}
    page.add_init_script(FRAME_RECORDER)
    try:
        page.goto(url, wait_until="load", timeout=nav_timeout_ms)
    except Exception as exc:
        rec.update(status="load_timeout", error=f"{type(exc).__name__}: {str(exc)[:200]}")
        return rec

    rec["t_load_ms"] = page.evaluate(
        "() => performance.timing.loadEventEnd - performance.timing.navigationStart")

    try:
        page.wait_for_selector("canvas", timeout=nav_timeout_ms)
        rec["t_canvas_ms"] = page.evaluate("() => performance.now()")
    except Exception:
        rec["t_canvas_ms"] = None

    quiet = page.evaluate(QUIET_PROBE)
    rec["t_quiet_ms"] = round(quiet, 1) if quiet and quiet > 0 else None

    rec["gl_renderer"] = page.evaluate("""
      () => { try {
        const c = document.createElement('canvas');
        const gl = c.getContext('webgl2') || c.getContext('webgl');
        if (!gl) return 'none';
        const ext = gl.getExtension('WEBGL_debug_renderer_info');
        return ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : 'masked';
      } catch (e) { return 'error'; } }
    """)

    box = page.evaluate("""
      () => { const cs = [...document.querySelectorAll('canvas')]
                .map(c => c.getBoundingClientRect())
                .filter(r => r.width > 100 && r.height > 100);
              if (!cs.length) return null;
              const r = cs.sort((a,b) => b.width*b.height - a.width*a.height)[0];
              return {x: r.x, y: r.y, w: r.width, h: r.height}; }
    """)
    if not box:
        rec["status"] = "no_canvas"
        return rec

    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2

    # ---------------- pan ----------------
    page.evaluate("() => { window.__frames = []; window.__recording = true; }")
    page.mouse.move(cx, cy)
    page.mouse.down()
    for i in range(30):
        page.mouse.move(cx - (i + 1) * 6, cy - (i + 1) * 2)
    page.mouse.up()
    page.wait_for_timeout(300)
    page.evaluate("() => { window.__recording = false; }")
    rec["pan"] = summarize(page.evaluate("() => window.__frames"))

    # ---------------- zoom ----------------
    page.evaluate("() => { window.__frames = []; window.__recording = true; }")
    page.mouse.move(cx, cy)
    for _ in range(15):
        page.mouse.wheel(0, -120)
        page.wait_for_timeout(40)
    page.wait_for_timeout(400)
    page.evaluate("() => { window.__recording = false; }")
    rec["zoom"] = summarize(page.evaluate("() => window.__frames"))

    heap = page.evaluate("() => performance.memory ? performance.memory.usedJSHeapSize : null")
    rec["js_heap_mb"] = round(heap / 1e6, 1) if heap else None
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*", default=None)
    ap.add_argument("--nav-timeout", type=int, default=180_000)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--dir", default=ARTIFACT_DIR)
    args = ap.parse_args()
    out_path = args.out

    from playwright.sync_api import sync_playwright

    art_dir = args.dir
    files = args.files or sorted(
        f for f in os.listdir(art_dir) if f.endswith(".html"))
    if not files:
        raise SystemExit(f"no .html artifacts in {art_dir}")

    httpd = serve(art_dir, PORT)
    results = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--enable-gpu", "--use-angle=metal",
                      "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"],
            )
            for fname in files:
                print(f"[{fname}] measuring...", flush=True)
                ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                page = ctx.new_page()
                try:
                    rec = measure(page, f"http://127.0.0.1:{PORT}/{fname}", fname,
                                  args.nav_timeout)
                except Exception as exc:
                    rec = {"file": fname, "status": "error",
                           "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
                results.append(rec)
                print("   " + json.dumps({k: v for k, v in rec.items()
                                          if k not in ("file",)})[:300], flush=True)
                ctx.close()
                with open(out_path, "w") as fh:
                    json.dump(results, fh, indent=2)
            browser.close()
    finally:
        httpd.shutdown()

    with open(out_path, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
