"""Find where each library's interactive export stops working in a real browser.

Producing a file is not the same as rendering it. Plotly writes a valid HTML
document at 100M points that a browser will happily "load" and then never draw,
with no error and no crash. This walks both libraries up the size ladder and
records, for each artifact, whether a canvas ever appears.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import socketserver
import subprocess
import sys
import threading
import time

SIZES = [10_000_000, 25_000_000, 50_000_000, 100_000_000]
BIG_DIR = "results/big"
OUT = "results/biginteraction.json"
PORT = 8783
RENDER_WAIT_S = 90


def serve(directory: str, port: int):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=directory)
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def ensure(lib: str, n: int) -> str | None:
    path = os.path.join(BIG_DIR, f"{lib}_{n}_synthetic.html")
    if os.path.exists(path):
        return os.path.basename(path)
    print(f"  generating {lib} @ {n:,} ...", flush=True)
    proc = subprocess.run(
        [sys.executable, "scripts/bench_big.py", "--lib", lib, "--n", str(n), "--keep"],
        capture_output=True, text=True, timeout=3600)
    if proc.returncode != 0 or not os.path.exists(path):
        print(f"    could not generate: {proc.stderr.strip()[-160:]}", flush=True)
        return None
    return os.path.basename(path)


def measure(page, url: str, size_bytes: int) -> dict:
    rec: dict = {"bytes_html": size_bytes}
    crashed: list = []
    page.on("crash", lambda _: crashed.append(True))
    t0 = time.time()
    try:
        page.goto(url, wait_until="load", timeout=300_000)
    except Exception as exc:
        rec.update(status="load_failed", seconds=round(time.time() - t0, 1),
                   error=f"{type(exc).__name__}: {str(exc)[:160]}")
        return rec
    rec["t_load_ms"] = round((time.time() - t0) * 1000)

    deadline = time.time() + RENDER_WAIT_S
    rendered = False
    while time.time() < deadline:
        try:
            if page.evaluate("() => document.querySelectorAll('canvas').length") > 0:
                rendered = True
                break
        except Exception:
            break
        time.sleep(1.0)
    rec["t_render_ms"] = round((time.time() - t0) * 1000) if rendered else None
    rec["rendered"] = rendered
    rec["status"] = "ok" if rendered else ("crashed" if crashed else "never_rendered")
    try:
        heap = page.evaluate(
            "() => performance.memory ? performance.memory.usedJSHeapSize : null")
        rec["js_heap_mb"] = round(heap / 1e6, 1) if heap else None
    except Exception:
        rec["js_heap_mb"] = None
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, nargs="*", default=SIZES)
    args = ap.parse_args()

    from playwright.sync_api import sync_playwright

    targets = []
    for n in args.sizes:
        for lib in ("xy", "plotly"):
            name = ensure(lib, n)
            if name:
                targets.append((lib, n, name))
    # The 500M XY export is produced by the sweep itself.
    big_xy = f"xy_500000000_synthetic.html"
    if os.path.exists(os.path.join(BIG_DIR, big_xy)):
        targets.append(("xy", 500_000_000, big_xy))

    httpd = serve(BIG_DIR, PORT)
    results = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--enable-gpu", "--use-angle=metal",
                      "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            for lib, n, name in targets:
                size = os.path.getsize(os.path.join(BIG_DIR, name))
                print(f"[{lib} @ {n:,}]  {size/1e6:.0f} MB", flush=True)
                ctx = browser.new_context(viewport={"width": 1280, "height": 900})
                page = ctx.new_page()
                try:
                    rec = measure(page, f"http://127.0.0.1:{PORT}/{name}", size)
                except Exception as exc:
                    rec = {"status": "error", "bytes_html": size,
                           "error": f"{type(exc).__name__}: {str(exc)[:200]}"}
                rec.update(lib=lib, n=n, file=name)
                results.append(rec)
                print(f"   -> {rec['status']}  load={rec.get('t_load_ms')}ms  "
                      f"render={rec.get('t_render_ms')}ms  heap={rec.get('js_heap_mb')}MB",
                      flush=True)
                try:
                    ctx.close()
                except Exception:
                    pass
                with open(OUT, "w") as fh:
                    json.dump(results, fh, indent=2)
            browser.close()
    finally:
        httpd.shutdown()

    with open(OUT, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
