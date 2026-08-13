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


def partial_matplotlib(args) -> None:
    """Draw the whole dataset in chunks and keep whatever made it onto the canvas.

    matplotlib normally rasterises in one shot inside savefig(), so a run that is
    killed leaves nothing. Drawing chunk by chunk with draw_artist() composites
    each batch straight onto the Agg buffer, so the buffer at any moment is a
    true partial render of the same points - not a different, smaller plot.

    Axis limits are fixed up front from the full extent, because autoscaling
    would shift the frame under every chunk. That scan is done before the clock
    starts; only drawing is timed.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    from PIL import Image

    x = np.load(os.path.join(args.data, "x.npy"), mmap_mode="r")
    y = np.load(os.path.join(args.data, "y.npy"), mmap_mode="r")
    c = np.load(os.path.join(args.data, "c.npy"), mmap_mode="r")
    n = int(x.shape[0])
    cmap = LinearSegmentedColormap.from_list("blues", BLUE_RAMP)

    CHUNK = 2_000_000
    head = slice(0, min(n, 20_000_000))          # extent from a bounded head read
    xlo, xhi = float(x[head].min()), float(x[head].max())
    ylo, yhi = float(y[head].min()), float(y[head].max())
    clo, chi = float(c[head].min()), float(c[head].max())
    padx, pady = 0.03 * (xhi - xlo), 0.03 * (yhi - ylo)

    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=100)
    ax.set_xlim(xlo - padx, xhi + padx)
    ax.set_ylim(ylo - pady, yhi + pady)
    ax.set_xlabel("UMAP 1")
    ax.set_ylabel("UMAP 2")
    ax.set_title(f"{n:,} points")
    fig.tight_layout()
    fig.canvas.draw()                             # background, axes, labels

    drawn = 0
    t0 = time.perf_counter()
    deadline = t0 + args.partial_budget
    for start in range(0, n, CHUNK):
        if time.perf_counter() >= deadline:
            break
        sl = slice(start, min(start + CHUNK, n))
        coll = ax.scatter(x[sl], y[sl], c=c[sl], cmap=cmap, s=2.0, alpha=0.55,
                          linewidths=0, vmin=clo, vmax=chi)
        ax.draw_artist(coll)                      # composite onto the live buffer
        coll.remove()                             # keep redraw cost per-chunk flat
        drawn = sl.stop
    elapsed = time.perf_counter() - t0

    out = os.path.join(args.out, f"matplotlib{args.suffix}.png")
    Image.fromarray(np.asarray(fig.canvas.buffer_rgba())).convert("RGB").save(out)
    print(json.dumps({
        "lib": "matplotlib", "n": n, "status": "partial", "drawn": drawn,
        "elapsed": elapsed, "output": os.path.basename(out), "kind": "png",
        "bytes": os.path.getsize(out), "peak_gb": peak_gb(),
    }))


def peak_gb() -> float:
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / 1e9 if sys.platform == "darwin" else raw / 1e6


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True, choices=["xy", "plotly", "matplotlib"])
    ap.add_argument("--data", required=True, help="directory holding x/y/c .npy")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--suffix", default="",
                    help="appended to the output filename")
    ap.add_argument("--partial-budget", type=float, default=0.0,
                    help="matplotlib only: draw the FULL dataset incrementally and "
                         "snapshot the canvas after this many seconds")
    args = ap.parse_args()

    if args.partial_budget and args.lib == "matplotlib":
        partial_matplotlib(args)
        return

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
        out = os.path.join(args.out, f"xy{args.suffix}.html")
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
        out = os.path.join(args.out, f"plotly{args.suffix}.html")
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
        out = os.path.join(args.out, f"matplotlib{args.suffix}.png")
        fig.savefig(out, dpi=100, facecolor="#fcfcfb")
        rec.update(t_export=time.perf_counter() - t1, output=os.path.basename(out),
                   kind="png")

    rec["bytes"] = os.path.getsize(out)
    rec["total"] = rec["t_build"] + rec["t_export"]
    rec["peak_gb"] = peak_gb()
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
