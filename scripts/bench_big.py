"""One big-scale (library, n) case. Same contract as bench_one.py, but the point
set is generated in-process because n can exceed the cell count by orders of
magnitude. Failure is a legitimate result here and is reported, not hidden.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time

import numpy as np

WIDTH, HEIGHT = 900, 700
POINT_SIZE, OPACITY = 2.0, 0.55
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
             "#256abf", "#184f95", "#0d366b"]


def peak_rss_gb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / 1e9 if sys.platform == "darwin" else raw / 1e6


def make_points(n: int, source: str):
    """Real transcript-detection events, or a structure-preserving synthetic cloud."""
    if source == "real":
        x = np.load("data/big_x.npy", mmap_mode="r")
        y = np.load("data/big_y.npy", mmap_mode="r")
        c = np.load("data/big_c.npy", mmap_mode="r")
        n = min(n, x.shape[0])
        return (np.ascontiguousarray(x[:n]), np.ascontiguousarray(y[:n]),
                np.ascontiguousarray(c[:n]))
    # Synthetic: the real 1.3M embedding replicated with jitter. The STRUCTURE is
    # real, the individual points are manufactured. Everything stays float32 and
    # is filled in place - a float64 temporary at 500M would cost 4 GB per column.
    emb = np.load("data/umap2.npy")
    src = emb.shape[0]
    cols = np.load("data/cell_meta.npz")["total_counts"]
    src_c = np.log10(np.maximum(cols, 1.0)).astype(np.float32)
    rng = np.random.default_rng(0)
    xs = np.empty(n, dtype=np.float32)
    ys = np.empty(n, dtype=np.float32)
    cs = np.empty(n, dtype=np.float32)
    written = 0
    while written < n:
        take = min(src, n - written)
        sl = slice(written, written + take)
        xs[sl] = emb[:take, 0]
        ys[sl] = emb[:take, 1]
        cs[sl] = src_c[:take]
        if written:  # leave the first copy exactly on the real embedding
            xs[sl] += rng.normal(0, 0.06, take).astype(np.float32)
            ys[sl] += rng.normal(0, 0.06, take).astype(np.float32)
        written += take
    return xs, ys, cs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True, choices=["xy", "matplotlib", "plotly"])
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--source", default="synthetic", choices=["synthetic", "real"])
    ap.add_argument("--outdir", default="results/big")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rec = {"lib": args.lib, "n": args.n, "source": args.source, "status": "ok"}

    t0 = time.perf_counter()
    x, y, c = make_points(args.n, args.source)
    rec["n"] = int(x.shape[0])
    rec["t_data_s"] = time.perf_counter() - t0
    rec["rss_after_data_gb"] = peak_rss_gb()

    stem = f"{args.lib}_{rec['n']}_{args.source}"
    try:
        if args.lib == "xy":
            import xy
            t0 = time.perf_counter()
            fig = xy.scatter_chart(
                xy.scatter(x, y, color=c, colormap=BLUE_RAMP, size=POINT_SIZE,
                           opacity=OPACITY, density=None),
                xy.x_axis(label="UMAP 1"), xy.y_axis(label="UMAP 2"),
                xy.theme(background="#fcfcfb", plot_background="#fcfcfb",
                         grid_color="#e1e0d9", axis_color="#c3c2b7",
                         text_color="#0b0b0b"),
                width=WIDTH, height=HEIGHT,
            )
            rec["t_build"] = time.perf_counter() - t0
            p = os.path.join(args.outdir, f"{stem}.html")
            t0 = time.perf_counter(); fig.to_html(p)
            rec["t_export_html"] = time.perf_counter() - t0
            rec["bytes_html"] = os.path.getsize(p)
            p2 = os.path.join(args.outdir, f"{stem}.png")
            t0 = time.perf_counter()
            fig.write_image(p2, width=WIDTH, height=HEIGHT, scale=1)
            rec["t_export_png"] = time.perf_counter() - t0
            rec["bytes_png"] = os.path.getsize(p2)
            rec["canonical_bytes"] = fig.memory_report().get("canonical_bytes")
            if not args.keep:
                os.remove(p); os.remove(p2)

        elif args.lib == "matplotlib":
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib.colors import LinearSegmentedColormap
            cmap = LinearSegmentedColormap.from_list("blues", BLUE_RAMP)
            t0 = time.perf_counter()
            fig, ax = plt.subplots(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100)
            ax.scatter(x, y, c=c, cmap=cmap, s=POINT_SIZE, alpha=OPACITY,
                       linewidths=0)
            rec["t_build"] = time.perf_counter() - t0
            p = os.path.join(args.outdir, f"{stem}.png")
            t0 = time.perf_counter(); fig.savefig(p, dpi=100)
            rec["t_export_png"] = time.perf_counter() - t0
            rec["bytes_png"] = os.path.getsize(p)
            if not args.keep:
                os.remove(p)

        else:
            import plotly.graph_objects as go
            scale = [[i / (len(BLUE_RAMP) - 1), h] for i, h in enumerate(BLUE_RAMP)]
            t0 = time.perf_counter()
            fig = go.Figure(go.Scattergl(
                x=x, y=y, mode="markers",
                marker=dict(color=c, colorscale=scale, size=POINT_SIZE,
                            opacity=OPACITY)))
            fig.update_layout(width=WIDTH, height=HEIGHT)
            rec["t_build"] = time.perf_counter() - t0
            p = os.path.join(args.outdir, f"{stem}.html")
            t0 = time.perf_counter()
            fig.write_html(p, include_plotlyjs=True, full_html=True)
            rec["t_export_html"] = time.perf_counter() - t0
            rec["bytes_html"] = os.path.getsize(p)
            if not args.keep:
                os.remove(p)

    except MemoryError as exc:
        rec["status"] = "oom"
        rec["error"] = f"MemoryError: {exc}"[:300]
    except Exception as exc:
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:300]

    rec["peak_rss_gb"] = peak_rss_gb()
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
