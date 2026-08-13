"""Live demo: build an N-point chart with XY, time every stage, open it.

    .venv/bin/python scripts/demo.py                # 250M points
    .venv/bin/python scripts/demo.py --n 50000000   # any size
    .venv/bin/python scripts/demo.py --compare      # also run Plotly at 10M

Prints each stage as it completes so the timings are visible while you talk,
then opens the finished chart in your browser.

PRESENTER NOTE - read before you demo:
  Pan freely. Do NOT scroll-zoom deep on stage. An exported XY file carries a
  density surface plus an ~8,200 point sample; on zoom the client asks a kernel
  for a finer view, and a file has no kernel, so the plot empties out after the
  first wheel notch. Measured: 43% ink -> 3.7%. Zooming is a live-backend
  feature, and at 250M that costs seconds per zoom. The story this demo tells is
  "a correct interactive overview of a quarter-billion points, in a 2 MB file,
  in under two seconds" - which is true, and which nothing else here can do.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
import webbrowser

import numpy as np

# XY warns that it is switching to a density surface above 2M points. That is
# expected here and the message would interleave into the timing lines mid-demo.
warnings.filterwarnings("ignore", category=RuntimeWarning, module="xy.*")

BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
             "#256abf", "#184f95", "#0d366b"]
OUT = "results/demo_chart.html"
W, H = 1100, 780


class Stage:
    """Print a stage and its elapsed time as it finishes."""

    def __init__(self, label: str, width: int = 42):
        self.label, self.width = label, width

    def __enter__(self):
        print(f"  {self.label:<{self.width}}", end="", flush=True)
        self.t = time.perf_counter()
        return self

    def __exit__(self, *a):
        self.dt = time.perf_counter() - self.t
        print(f"{self.dt:8.2f} s")


def build_points(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Tile the real 1.3M-cell UMAP up to n points with Gaussian jitter."""
    emb = np.load("data/umap2.npy")
    tot = np.load("data/cell_meta.npz")["total_counts"]
    depth = np.log10(np.maximum(tot, 1.0)).astype(np.float32)
    src = emb.shape[0]
    rng = np.random.default_rng(0)
    xs = np.empty(n, dtype=np.float32)
    ys = np.empty(n, dtype=np.float32)
    cs = np.empty(n, dtype=np.float32)
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
    return xs, ys, cs


def recorded_comparison(n: int) -> list[tuple[str, str, str]]:
    """Previously measured Plotly / matplotlib numbers, if the sweep has run."""
    try:
        with open("results/bigsweep.json") as fh:
            sweep = json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    rows = []
    for lib, label in (("plotly", "Plotly"), ("matplotlib", "matplotlib")):
        rec = next((r for r in sweep if r["lib"] == lib and r["n"] == n), None)
        if not rec:
            continue
        if rec.get("status") != "ok":
            rows.append((label, "did not complete", rec.get("status", "")))
            continue
        if rec.get("bytes_html"):
            rows.append((label,
                         f"{rec['t_export_html']:.1f} s to write",
                         f"{rec['bytes_html']/1e6:,.0f} MB file"))
        elif rec.get("t_export_png"):
            t = rec["t_export_png"]
            rows.append((label,
                         f"{t/60:.1f} min to render" if t > 60 else f"{t:.1f} s to render",
                         "static PNG"))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=250_000_000)
    ap.add_argument("--compare", action="store_true",
                    help="also build the same chart with Plotly at 10M, live")
    ap.add_argument("--no-open", action="store_true")
    args = ap.parse_args()
    n = args.n

    print(f"\n  Plotting {n:,} points with XY")
    print("  " + "-" * 50)

    with Stage("generate points") as s_gen:
        x, y, c = build_points(n)

    import xy   # imported here so its cost is visible as its own stage

    with Stage("build the chart") as s_build:
        chart = xy.scatter_chart(
            xy.scatter(x, y, color=c, colormap=BLUE_RAMP, size=2.0, opacity=0.55,
                       density=None),
            xy.x_axis(label="UMAP 1"),
            xy.y_axis(label="UMAP 2"),
            xy.colorbar(title="log10 UMI"),
            xy.theme(background="#fcfcfb", plot_background="#fcfcfb",
                     grid_color="#e1e0d9", axis_color="#c3c2b7",
                     text_color="#0b0b0b"),
            title=f"{n:,} points",
            width=W, height=H,
        )

    os.makedirs("results", exist_ok=True)
    with Stage("write a self-contained HTML file") as s_exp:
        chart.to_html(OUT)

    size = os.path.getsize(OUT)
    print("  " + "-" * 50)
    print(f"  {'XY total (build + write)':<42}{s_build.dt + s_exp.dt:8.2f} s")
    print(f"\n  {size/1e6:,.1f} MB, self-contained, for {n:,} points.")
    print(f"  The same file is 1.9 MB at 10 million points - above ~2 million XY "
          f"sends\n  a screen-bounded density surface, so the payload stops "
          f"tracking the data.")

    if args.compare:
        print("\n  Same chart, Plotly, at 10,000,000 points (25x less data):")
        import plotly.graph_objects as go
        xs, ys, cs = x[:10_000_000], y[:10_000_000], c[:10_000_000]
        scale = [[i / (len(BLUE_RAMP) - 1), h] for i, h in enumerate(BLUE_RAMP)]
        with Stage("  build the chart"):
            fig = go.Figure(go.Scattergl(
                x=xs, y=ys, mode="markers",
                marker=dict(color=cs, colorscale=scale, size=2.0, opacity=0.55)))
            fig.update_layout(width=W, height=H)
        p = "results/demo_plotly.html"
        with Stage("  write a self-contained HTML file"):
            fig.write_html(p, include_plotlyjs=True, full_html=True)
        print(f"\n  {os.path.getsize(p)/1e6:,.0f} MB file for 10,000,000 points")

    rows = recorded_comparison(n)
    if rows:
        print(f"\n  Previously measured at {n:,} points on this machine:")
        for label, a, b in rows:
            print(f"    {label:<12} {a:<22} {b}")

    print()
    if not args.no_open:
        print(f"  opening {OUT}\n")
        webbrowser.open("file://" + os.path.abspath(OUT))
    else:
        print(f"  wrote {OUT}\n")


if __name__ == "__main__":
    main()
