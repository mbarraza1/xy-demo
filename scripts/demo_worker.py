"""Render one library's chart from memory-mapped columns. Spawned by demo.py.

Runs in its own process so the parent can enforce a hard wall-clock timeout and
kill it cleanly - a library that hangs cannot be interrupted in-process. Emits a
single JSON line on stdout when it finishes.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import sys
import time
import warnings

import numpy as np

warnings.filterwarnings("ignore", category=RuntimeWarning, module="xy.*")

BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
             "#256abf", "#184f95", "#0d366b"]
W, H = 1000, 720          # fixed export size for Plotly and matplotlib
FRAME_H = 520            # must match .frame height in demo.py's comparison page


def peak_gb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / 1e9 if sys.platform == "darwin" else raw / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True, choices=["xy", "plotly", "matplotlib"])
    ap.add_argument("--data", required=True, help="directory holding x/y/c .npy")
    ap.add_argument("--out", required=True, help="output directory")
    args = ap.parse_args()

    # mmap: the arrays are shared with the other workers and never copied here,
    # so the clock below measures charting rather than data loading.
    x = np.load(os.path.join(args.data, "x.npy"), mmap_mode="r")
    y = np.load(os.path.join(args.data, "y.npy"), mmap_mode="r")
    c = np.load(os.path.join(args.data, "c.npy"), mmap_mode="r")
    n = int(x.shape[0])
    title = f"{n:,} points"
    rec: dict = {"lib": args.lib, "n": n}

    t0 = time.perf_counter()
    if args.lib == "xy":
        import xy
        chart = xy.scatter_chart(
            xy.scatter(x, y, color=c, colormap=BLUE_RAMP, size=2.0, opacity=0.55,
                       density=None),
            xy.x_axis(label="UMAP 1"), xy.y_axis(label="UMAP 2"),
            xy.colorbar(title="log10 UMI"),
            xy.theme(background="#fcfcfb", plot_background="#fcfcfb",
                     grid_color="#e1e0d9", axis_color="#c3c2b7",
                     text_color="#0b0b0b"),
            title=title,
            # Width follows the panel it is embedded in; height is fixed to the
            # comparison page's frame, because a percentage height inside an
            # iframe has no context to resolve against and collapses.
            width="100%", height=FRAME_H,
        )
        rec["t_build"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        out = os.path.join(args.out, "xy.html")
        chart.to_html(out)
        rec.update(t_export=time.perf_counter() - t1, output=os.path.basename(out),
                   kind="html")

    elif args.lib == "plotly":
        import plotly.graph_objects as go
        scale = [[i / (len(BLUE_RAMP) - 1), h] for i, h in enumerate(BLUE_RAMP)]
        fig = go.Figure(go.Scattergl(
            x=np.asarray(x), y=np.asarray(y), mode="markers",
            marker=dict(color=np.asarray(c), colorscale=scale, size=2.0,
                        opacity=0.55, colorbar=dict(title="log10 UMI"))))
        fig.update_layout(title=title, xaxis_title="UMAP 1", yaxis_title="UMAP 2",
                          width=W, height=H, plot_bgcolor="#fcfcfb",
                          paper_bgcolor="#fcfcfb")
        rec["t_build"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        out = os.path.join(args.out, "plotly.html")
        fig.write_html(out, include_plotlyjs=True, full_html=True)
        rec.update(t_export=time.perf_counter() - t1, output=os.path.basename(out),
                   kind="html")

    else:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import LinearSegmentedColormap
        cmap = LinearSegmentedColormap.from_list("blues", BLUE_RAMP)
        fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
        sc = ax.scatter(x, y, c=c, cmap=cmap, s=2.0, alpha=0.55, linewidths=0)
        ax.set_title(title)
        ax.set_xlabel("UMAP 1")
        ax.set_ylabel("UMAP 2")
        fig.colorbar(sc, ax=ax, label="log10 UMI")
        fig.tight_layout()
        rec["t_build"] = time.perf_counter() - t0
        t1 = time.perf_counter()
        out = os.path.join(args.out, "matplotlib.png")
        fig.savefig(out, dpi=100, facecolor="#fcfcfb")
        rec.update(t_export=time.perf_counter() - t1, output=os.path.basename(out),
                   kind="png")

    rec["bytes"] = os.path.getsize(out)
    rec["total"] = rec["t_build"] + rec["t_export"]
    rec["peak_gb"] = peak_gb()
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
