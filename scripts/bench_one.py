"""Run ONE (library, n) benchmark case in a fresh process and emit JSON on stdout.

Isolation matters: peak RSS and import cost are per-process, and a warm figure
cache in one library would otherwise flatter the next. The parent
(03_benchmark.py) spawns one of these per cell of the sweep.

All three libraries get identical inputs: the same UMAP coordinates, the same
continuous colour values, the same sequential blue ramp, the same canvas size,
the same marker size. The only variable is the rendering engine.
"""

from __future__ import annotations

import argparse
import inspect
import json
import os
import resource
import sys
import time

import numpy as np

WIDTH, HEIGHT = 900, 700
POINT_SIZE = 2.0
OPACITY = 0.55

# Sequential blue ramp, light -> dark (validated design-system ramp).
BLUE_RAMP = [
    "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
    "#256abf", "#184f95", "#0d366b",
]

TITLE = "Mouse brain UMAP - 1.3M cells (E18)"
X_LABEL = "UMAP 1"
Y_LABEL = "UMAP 2"
COLOR_LABEL = "log10 UMI count"


def peak_rss_mb() -> float:
    """macOS reports ru_maxrss in bytes; Linux in kilobytes."""
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw / 1e6 if sys.platform == "darwin" else raw / 1e3


def body_loc(fn) -> int:
    """Non-blank, non-comment lines of a chart-construction function's body."""
    lines = inspect.getsource(fn).splitlines()[1:]  # drop the def line
    out = 0
    for ln in lines:
        s = ln.strip()
        if s and not s.startswith("#"):
            out += 1
    return out


# --------------------------------------------------------------------------
# The three chart implementations. Each takes the same arrays and returns a
# figure object; LOC is measured on these bodies.
# --------------------------------------------------------------------------

def build_matplotlib(x, y, c):
    import matplotlib
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blues", BLUE_RAMP)
    fig, ax = matplotlib.pyplot.subplots(figsize=(WIDTH / 100, HEIGHT / 100), dpi=100)
    sc = ax.scatter(x, y, c=c, cmap=cmap, s=POINT_SIZE, alpha=OPACITY, linewidths=0)
    ax.set_title(TITLE)
    ax.set_xlabel(X_LABEL)
    ax.set_ylabel(Y_LABEL)
    fig.colorbar(sc, ax=ax, label=COLOR_LABEL)
    fig.tight_layout()
    return fig


def build_plotly(x, y, c):
    import plotly.graph_objects as go
    scale = [[i / (len(BLUE_RAMP) - 1), h] for i, h in enumerate(BLUE_RAMP)]
    fig = go.Figure(go.Scattergl(
        x=x, y=y, mode="markers",
        marker=dict(color=c, colorscale=scale, size=POINT_SIZE, opacity=OPACITY,
                    colorbar=dict(title=COLOR_LABEL)),
        hoverinfo="x+y",
    ))
    fig.update_layout(title=TITLE, xaxis_title=X_LABEL, yaxis_title=Y_LABEL,
                      width=WIDTH, height=HEIGHT, plot_bgcolor="#fcfcfb",
                      paper_bgcolor="#fcfcfb")
    return fig


def build_xy(x, y, c):
    import xy
    return xy.scatter_chart(
        xy.scatter(x, y, color=c, colormap=BLUE_RAMP, size=POINT_SIZE,
                   opacity=OPACITY, density=None),
        xy.x_axis(label=X_LABEL),
        xy.y_axis(label=Y_LABEL),
        xy.colorbar(title=COLOR_LABEL),
        xy.theme(background="#fcfcfb", plot_background="#fcfcfb",
                 grid_color="#e1e0d9", axis_color="#c3c2b7", text_color="#0b0b0b"),
        title=TITLE, width=WIDTH, height=HEIGHT,
    )


BUILDERS = {"matplotlib": build_matplotlib, "plotly": build_plotly, "xy": build_xy}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lib", required=True, choices=list(BUILDERS))
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--outdir", default="results/artifacts")
    ap.add_argument("--save-artifacts", action="store_true",
                    help="keep the rendered files (used for the largest run)")
    args = ap.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    rec: dict = {"lib": args.lib, "n": args.n, "status": "ok"}

    # ---- shared data load, deliberately outside every timer ----
    emb = np.load("data/umap2.npy", mmap_mode="r")
    meta = np.load("data/cell_meta.npz")
    total = meta["total_counts"]
    n = min(args.n, emb.shape[0])
    rng = np.random.default_rng(0)
    idx = np.sort(rng.choice(emb.shape[0], size=n, replace=False)) if n < emb.shape[0] \
        else np.arange(emb.shape[0])
    x = np.ascontiguousarray(emb[idx, 0], dtype=np.float32)
    y = np.ascontiguousarray(emb[idx, 1], dtype=np.float32)
    c = np.log10(np.maximum(total[idx], 1.0)).astype(np.float32)
    rss_baseline = peak_rss_mb()

    # ---- import cost, measured separately from build ----
    t0 = time.perf_counter()
    if args.lib == "matplotlib":
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot  # noqa: F401
    elif args.lib == "plotly":
        import plotly.graph_objects  # noqa: F401
    else:
        import xy  # noqa: F401
    rec["t_import"] = time.perf_counter() - t0

    builder = BUILDERS[args.lib]
    rec["loc"] = body_loc(builder)

    stem = f"{args.lib}_{n}"
    try:
        t0 = time.perf_counter()
        fig = builder(x, y, c)
        rec["t_build"] = time.perf_counter() - t0

        # ---- interactive HTML (plotly, xy) ----
        if args.lib in ("plotly", "xy"):
            path = os.path.join(args.outdir, f"{stem}.html")
            t0 = time.perf_counter()
            if args.lib == "plotly":
                fig.write_html(path, include_plotlyjs=True, full_html=True)
            else:
                fig.to_html(path)
            rec["t_export_html"] = time.perf_counter() - t0
            rec["bytes_html"] = os.path.getsize(path)
            if not args.save_artifacts:
                os.remove(path)

        # ---- static PNG (matplotlib, xy) ----
        if args.lib in ("matplotlib", "xy"):
            path = os.path.join(args.outdir, f"{stem}.png")
            t0 = time.perf_counter()
            if args.lib == "matplotlib":
                fig.savefig(path, dpi=100, facecolor="#fcfcfb")
            else:
                # scale=1 so the raster matches matplotlib's 900x700 at dpi=100;
                # XY defaults to a 2x device-pixel-ratio, which would quadruple
                # the pixel count and make the byte comparison meaningless.
                fig.write_image(path, width=WIDTH, height=HEIGHT, scale=1)
            rec["t_export_png"] = time.perf_counter() - t0
            rec["bytes_png"] = os.path.getsize(path)
            if not args.save_artifacts:
                os.remove(path)

        if args.lib == "xy":
            try:
                mr = fig.memory_report()
                rec["xy_canonical_bytes"] = mr.get("canonical_bytes")
            except Exception:
                pass

    except Exception as exc:  # a real result: the library could not do it
        rec["status"] = "error"
        rec["error"] = f"{type(exc).__name__}: {exc}"[:400]

    rec["peak_rss_mb"] = peak_rss_mb()
    rec["rss_baseline_mb"] = rss_baseline
    rec["peak_over_baseline_mb"] = rec["peak_rss_mb"] - rss_baseline
    print(json.dumps(rec))


if __name__ == "__main__":
    main()
