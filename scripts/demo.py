"""Live demo: race XY, Plotly and matplotlib on the same points under one clock.

    .venv/bin/python scripts/demo.py                     # 250M points, 20s each
    .venv/bin/python scripts/demo.py --n 10000000        # any size
    .venv/bin/python scripts/demo.py --timeout 60        # a longer leash

Each library gets its own process and the same hard wall-clock budget. The point
arrays are generated ONCE and memory-mapped into every worker, so the clock
measures charting rather than identical data-generation overhead. Whatever
finishes is shown; whatever runs out of time is shown as that, which at 250M is
the entire point. Ends by serving a comparison page and opening it.

PRESENTER NOTE: pan the XY chart freely, but do not scroll-zoom deep on stage.
An exported file has no kernel, so zoom falls through to the ~8,200 point sample
baked into it and the plot empties after the first notch.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import shutil
import socketserver
import subprocess
import sys
import threading
import time
import webbrowser

import numpy as np

DEMO = "results/demo"
DATA = os.path.join(DEMO, "data")
LIBS = [("xy", "XY", "#2a78d6"),
        ("plotly", "Plotly", "#1baf7a"),
        ("matplotlib", "matplotlib", "#eb6834")]
INLINE_LIMIT = 50 * 1024 * 1024      # never iframe a file bigger than this


def generate(n: int) -> float:
    """Tile the real 1.3M-cell UMAP up to n points, once, to disk."""
    os.makedirs(DATA, exist_ok=True)
    t0 = time.perf_counter()
    emb = np.load("data/umap2.npy")
    tot = np.load("data/cell_meta.npz")["total_counts"]
    depth = np.log10(np.maximum(tot, 1.0)).astype(np.float32)
    src = emb.shape[0]
    rng = np.random.default_rng(0)
    xs = np.lib.format.open_memmap(os.path.join(DATA, "x.npy"), mode="w+",
                                   dtype=np.float32, shape=(n,))
    ys = np.lib.format.open_memmap(os.path.join(DATA, "y.npy"), mode="w+",
                                   dtype=np.float32, shape=(n,))
    cs = np.lib.format.open_memmap(os.path.join(DATA, "c.npy"), mode="w+",
                                   dtype=np.float32, shape=(n,))
    w = i = 0
    while w < n:
        take = min(src, n - w)
        sl = slice(w, w + take)
        xs[sl] = emb[:take, 0]
        ys[sl] = emb[:take, 1]
        cs[sl] = depth[:take]
        if i:
            xs[sl] += rng.normal(0, 0.06, take).astype(np.float32)
            ys[sl] += rng.normal(0, 0.06, take).astype(np.float32)
        w += take
        i += 1
    for a in (xs, ys, cs):
        a.flush()
    return time.perf_counter() - t0


def run_one(lib: str, timeout: float, limit: int = 0, suffix: str = "") -> dict:
    """One library, one process, one hard deadline."""
    cmd = [sys.executable, "scripts/demo_worker.py", "--lib", lib,
           "--data", DATA, "--out", DEMO]
    if limit:
        cmd += ["--limit", str(limit), "--suffix", suffix]
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Kill left a partial file behind; a half-written 4 GB HTML helps nobody,
        # and a truncated PNG will not decode.
        for stale in (f"{lib}{suffix}.html", f"{lib}{suffix}.png"):
            path = os.path.join(DEMO, stale)
            if os.path.exists(path):
                os.remove(path)
        return {"lib": lib, "status": "timeout", "elapsed": timeout}
    elapsed = time.perf_counter() - t0
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        return {"lib": lib, "status": "error", "elapsed": elapsed,
                "error": (tail[-1] if tail else "non-zero exit")[:200]}
    try:
        rec = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"lib": lib, "status": "error", "elapsed": elapsed,
                "error": "no result from worker"}
    rec.update(status="ok", elapsed=elapsed)
    return rec


def panel(lib: str, label: str, color: str, rec: dict, timeout: float) -> str:
    if rec.get("status") == "ok":
        badge = (f'<span class="ok">finished in {rec["total"]:.2f} s</span>')
        stats = (f'{rec["bytes"]/1e6:,.1f} MB &middot; built {rec["t_build"]:.2f} s '
                 f'&middot; wrote {rec["t_export"]:.2f} s &middot; '
                 f'peak {rec["peak_gb"]:.1f} GB')
        if rec["kind"] == "png":
            body = f'<img src="{rec["output"]}" alt="{label} output">'
        elif rec["bytes"] > INLINE_LIMIT:
            # Learned the hard way: a multi-GB figure in an iframe takes the
            # whole comparison page down with it.
            body = (f'<div class="miss"><p><strong>{rec["bytes"]/1e6:,.0f} MB</strong> '
                    f'— too large to embed without freezing this page.</p>'
                    f'<p><a href="{rec["output"]}" target="_blank">Open it in its '
                    f'own tab</a> if you want to watch it struggle.</p></div>')
        else:
            body = f'<iframe src="{rec["output"]}" loading="lazy"></iframe>'
    elif rec.get("status") == "timeout":
        badge = f'<span class="bad">still running at {timeout:.0f} s</span>'
        fb = rec.get("fallback")
        if fb and fb.get("status") == "ok":
            # It produced nothing at the headline size, so show what it DID
            # manage inside the same budget - a real run, at a fraction of the
            # data, labelled as exactly that.
            pct = 100.0 * fb["n"] / rec["n"]
            inner = (f'<img src="{fb["output"]}" alt="{label} at {fb["n"]:,} points">'
                     if fb["kind"] == "png" else
                     (f'<iframe src="{fb["output"]}" loading="lazy"></iframe>'
                      if fb["bytes"] <= INLINE_LIMIT else
                      f'<div class="miss"><p><strong>{fb["bytes"]/1e6:,.0f} MB</strong>'
                      f' — too large to embed.</p><p><a href="{fb["output"]}" '
                      f'target="_blank">Open in its own tab</a></p></div>'))
            body = (f'<div class="fallback"><p class="tag">given the same '
                    f'{timeout:.0f} s: {fb["n"]:,} points — {pct:.1f}% of the data'
                    f'</p>{inner}</div>')
            stats = (f'that {pct:.1f}% took {fb["total"]:.2f} s &middot; '
                     f'{fb["bytes"]/1e6:,.1f} MB &middot; peak {fb["peak_gb"]:.1f} GB')
        else:
            body = ('<div class="miss"><p class="big">no chart</p>'
                    f'<p>{label} had not finished after {timeout:.0f} seconds, '
                    f'so it was stopped.</p></div>')
            stats = "killed before it produced anything"
    else:
        badge = '<span class="bad">failed</span>'
        stats = rec.get("error", "")[:160]
        body = '<div class="miss"><p class="big">no chart</p></div>'
    return f"""
    <section class="panel">
      <h2 style="color:{color}">{label}</h2>
      <p class="badge">{badge}</p>
      <div class="frame">{body}</div>
      <p class="stats">{stats}</p>
    </section>"""


PAGE = """<!doctype html><meta charset="utf-8"><title>{n:,} points, three ways</title>
<style>
  :root {{ color-scheme: light; --bg:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b;
           --muted:#898781; --line:rgba(11,11,11,.12); }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#0d0d0d; --surface:#1a1a19; --ink:#fff; --muted:#898781;
             --line:rgba(255,255,255,.12); }} }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
          font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }}
  .wrap {{ max-width:1400px; margin:0 auto; padding:2.5rem 1.5rem; }}
  h1 {{ font-size:2rem; margin:0 0 .4rem; }}
  .lede {{ color:var(--muted); margin:0 0 2rem; max-width:70ch; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(380px,1fr));
           gap:1.25rem; }}
  .panel {{ background:var(--surface); border:1px solid var(--line);
            border-radius:12px; padding:1rem; }}
  .panel h2 {{ margin:0 0 .35rem; font-size:1.1rem; }}
  .badge {{ margin:0 0 .75rem; font-size:.85rem; }}
  .ok {{ color:#2a78d6; font-weight:600; }}
  .bad {{ color:#eb6834; font-weight:600; }}
  .frame {{ background:var(--bg); border-radius:8px; overflow:hidden;
            height:520px; display:flex; align-items:center;
            justify-content:center; }}
  iframe {{ width:100%; height:100%; border:0; }}
  img {{ max-width:100%; max-height:100%; object-fit:contain; }}
  .fallback {{ width:100%; height:100%; display:flex; flex-direction:column; }}
  .fallback .tag {{ margin:0 0 .5rem; font-size:.78rem; color:#eb6834;
                    text-align:center; font-weight:600; }}
  .fallback iframe, .fallback img {{ flex:1; min-height:0; }}
  .miss {{ text-align:center; color:var(--muted); padding:1.5rem; }}
  .miss .big {{ font-size:1.4rem; font-weight:600; color:#eb6834; margin:0 0 .4rem; }}
  .stats {{ color:var(--muted); font-size:.82rem; margin:.75rem 0 0;
            font-variant-numeric:tabular-nums; }}
  footer {{ color:var(--muted); font-size:.82rem; margin-top:2.5rem;
            border-top:1px solid var(--line); padding-top:1.25rem; max-width:80ch; }}
</style>
<div class="wrap">
  <h1>{n:,} points, three ways</h1>
  <p class="lede">{lede}</p>
  <div class="grid">{panels}
  </div>
  <footer>{footer}</footer>
</div>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250_000_000)
    ap.add_argument("--timeout", type=float, default=20.0)
    ap.add_argument("--port", type=int, default=8899)
    ap.add_argument("--no-open", action="store_true")
    ap.add_argument("--fallback-n", type=int, default=5_000_000,
                    help="on timeout, retry that library at this size so the page "
                         "can show how far it got (0 disables)")
    ap.add_argument("--keep-data", action="store_true",
                    help="keep the generated .npy columns for a re-run")
    args = ap.parse_args()
    n, timeout = args.n, args.timeout

    os.makedirs(DEMO, exist_ok=True)
    for lib, _, _ in LIBS:
        for stem in (lib, f"{lib}_fallback"):
            for ext in ("html", "png"):
                p = os.path.join(DEMO, f"{stem}.{ext}")
                if os.path.exists(p):
                    os.remove(p)

    print(f"\n  {n:,} points — each library gets {timeout:.0f} seconds\n", flush=True)
    need = not (args.keep_data and os.path.exists(os.path.join(DATA, "x.npy"))
                and np.load(os.path.join(DATA, "x.npy"), mmap_mode="r").shape[0] == n)
    if need:
        print(f"  {'generating the points (once, shared)':<40}", end="", flush=True)
        dt = generate(n)
        print(f"{dt:7.2f} s", flush=True)
    else:
        print("  reusing the generated points", flush=True)
    print()

    results = {}
    for lib, label, _ in LIBS:
        print(f"  {label:<40}", end="", flush=True)
        rec = run_one(lib, timeout)
        rec["n"] = n
        results[lib] = rec
        if rec["status"] == "ok":
            print(f"{rec['total']:7.2f} s   {rec['bytes']/1e6:>9,.1f} MB", flush=True)
        elif rec["status"] == "timeout":
            print(f"{'—':>7}     still running at {timeout:.0f}s, killed", flush=True)
            if args.fallback_n and args.fallback_n < n:
                print(f"  {'  ...retrying at ' + format(args.fallback_n, ',') + ' points':<40}",
                      end="", flush=True)
                fb = run_one(lib, timeout, limit=args.fallback_n, suffix="_fallback")
                rec["fallback"] = fb
                print(f"{fb['total']:7.2f} s" if fb["status"] == "ok"
                      else f"{'—':>7}     also out of time", flush=True)
        else:
            print(f"{'—':>7}     failed: {rec.get('error','')[:60]}", flush=True)

    finished = [l for l, _, _ in LIBS if results[l]["status"] == "ok"]
    lede = (f"The same {n:,} points, the same machine, the same colour ramp. Each "
            f"library was given its own process and {timeout:.0f} seconds to turn "
            f"those arrays into a finished chart file. "
            + (f"{len(finished)} of 3 made it."
               if len(finished) < 3 else "All three made it."))
    fell_back = [l for l, _, _ in LIBS
                 if results[l].get("fallback", {}).get("status") == "ok"]
    footer = (
        "The points are the real 1,306,127-cell mouse brain UMAP (10x Genomics, E18) "
        "tiled with Gaussian jitter — the structure is real, the individual points "
        "are manufactured. Arrays were generated once and memory-mapped into each "
        "worker, so the clock covers charting only, not data generation. A timeout "
        "is not a crash: the library was still working when the deadline passed, and "
        "a half-written file cannot be rendered, so there is no partial chart to show."
        + (" Where a library ran out of time, it was given the same budget again at "
           f"{args.fallback_n:,} points so the panel can show something real it "
           "actually finished. That smaller run is not its maximum — it is one "
           "sample point, labelled with the fraction of the data it covers."
           if fell_back else "")
    )
    panels = "".join(panel(l, lab, col, results[l], timeout) for l, lab, col in LIBS)
    page = PAGE.format(n=n, lede=lede, panels=panels, footer=footer)
    with open(os.path.join(DEMO, "compare.html"), "w") as fh:
        fh.write(page)

    if not args.keep_data:
        shutil.rmtree(DATA, ignore_errors=True)

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DEMO)
    handler.log_message = lambda *a, **k: None
    socketserver.TCPServer.allow_reuse_address = True
    httpd = socketserver.TCPServer(("127.0.0.1", args.port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{args.port}/compare.html"
    print(f"\n  {url}")
    if not args.no_open:
        webbrowser.open(url)
    print("  serving — Ctrl-C when you're done\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        httpd.shutdown()
        print("  stopped\n")


if __name__ == "__main__":
    main()
