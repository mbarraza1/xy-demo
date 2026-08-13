"""Zoom fidelity: a raster is frozen at export resolution; XY re-renders the window.

Both panels show the same small neighbourhood. The matplotlib panel is what you
get by cropping and upscaling the exported 900x700 PNG - the only thing a static
figure can offer once it is written. The XY panel is the same window re-rendered
from the canonical columns still held in Python, which is what zooming in the
live chart actually does.

At 500M points the XY panel is itself a density surface rather than individual
markers, because the window still holds millions of points. The comparison is
therefore not "blurry vs crisp points" - it is "frozen at 98x85 source pixels"
against "re-evaluated at whatever resolution you asked for".
"""

from __future__ import annotations

import argparse

import numpy as np

X_LO, X_HI = 6.0, 9.5
Y_LO, Y_HI = -5.5, -2.0
W, H = 700, 700

BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
             "#256abf", "#184f95", "#0d366b"]


def load_points(source: str, n: int):
    emb = np.load("data/umap2.npy")
    tot = np.load("data/cell_meta.npz")["total_counts"]
    c = np.log10(np.maximum(tot, 1.0)).astype(np.float32)
    if source == "real":
        return emb[:, 0].copy(), emb[:, 1].copy(), c
    import sys
    sys.path.insert(0, "scripts")
    from bench_big import make_points
    return make_points(n, "synthetic")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="synthetic", choices=["real", "synthetic"])
    ap.add_argument("--n", type=int, default=500_000_000)
    ap.add_argument("--raster", default="app/assets/matplotlib_big.png",
                    help="the exported PNG to crop from")
    args = ap.parse_args()

    import xy
    from PIL import Image

    # ---- what the exported raster can give you: crop + upscale ----
    full = Image.open(args.raster)
    x, y, c = load_points(args.source, args.n)

    # Ask matplotlib itself where the axes box and data limits landed, rather than
    # hard-coding pixels: the benchmark figure has no title, labels, or colorbar,
    # so its margins differ from any other figure in this project.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    probe_fig, probe_ax = plt.subplots(figsize=(900 / 100, 700 / 100), dpi=100)
    probe_ax.set_xlim(float(x.min()), float(x.max()))
    probe_ax.set_ylim(float(y.min()), float(y.max()))
    probe_ax.margins(0.05)
    probe_ax.autoscale_view()
    probe_fig.canvas.draw()
    bbox = probe_ax.get_window_extent()
    dx_lo, dx_hi = probe_ax.get_xlim()
    dy_lo, dy_hi = probe_ax.get_ylim()
    fig_h = probe_fig.get_size_inches()[1] * probe_fig.dpi
    ax_l, ax_r = bbox.x0, bbox.x1
    ax_t, ax_b = fig_h - bbox.y1, fig_h - bbox.y0   # PIL counts y from the top
    plt.close(probe_fig)
    print(f"axes box: x[{ax_l:.0f},{ax_r:.0f}] y[{ax_t:.0f},{ax_b:.0f}]  "
          f"data x[{dx_lo:.2f},{dx_hi:.2f}] y[{dy_lo:.2f},{dy_hi:.2f}]")

    def px(px_x, px_y):
        fx = (px_x - dx_lo) / (dx_hi - dx_lo)
        fy = (px_y - dy_lo) / (dy_hi - dy_lo)
        return ax_l + fx * (ax_r - ax_l), ax_b - fy * (ax_b - ax_t)

    x0, y1 = px(X_LO, Y_LO)
    x1, y0 = px(X_HI, Y_HI)
    crop = full.crop((int(x0), int(y0), int(x1), int(y1)))
    src_w, src_h = crop.width, crop.height
    crop = crop.resize((W, H), Image.NEAREST)
    crop.save("results/artifacts/fidelity_matplotlib_zoom.png")
    print(f"raster crop: {src_w}x{src_h} source pixels upscaled to {W}x{H}")

    # ---- what XY gives you: the same window, re-rendered from source rows ----
    in_window = int((((x >= X_LO) & (x <= X_HI) & (y >= Y_LO) & (y <= Y_HI)).sum()))
    print(f"points in window: {in_window:,} of {x.shape[0]:,}")

    chart = xy.scatter_chart(
        xy.scatter(x, y, color=c, colormap=BLUE_RAMP, size=3.0, opacity=0.7,
                   density=None),
        xy.x_axis(label="UMAP 1", domain=(X_LO, X_HI)),
        xy.y_axis(label="UMAP 2", domain=(Y_LO, Y_HI)),
        xy.theme(background="#fcfcfb", plot_background="#fcfcfb",
                 grid_color="#e1e0d9", axis_color="#c3c2b7", text_color="#0b0b0b"),
        width=W, height=H,
    )
    chart.write_image("results/artifacts/fidelity_xy_zoom.png",
                      width=W, height=H, scale=1)
    print("wrote results/artifacts/fidelity_xy_zoom.png")

    with open("results/fidelity_meta.json", "w") as fh:
        import json
        json.dump({"source": args.source, "n": int(x.shape[0]),
                   "in_window": in_window, "raster_src_w": src_w,
                   "raster_src_h": src_h}, fh, indent=2)


if __name__ == "__main__":
    main()
