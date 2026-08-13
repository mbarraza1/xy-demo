"""Zoom fidelity: a raster is fixed at export resolution; XY re-renders from source rows.

Both panels show the same small neighbourhood of the embedding. The matplotlib
panel is what you get by cropping and upscaling the exported 900x700 PNG - the
only thing a static figure can offer once it is written. The XY panel is the
same region re-rendered from the canonical columns, which is what a zoom in the
live chart actually does.
"""

from __future__ import annotations

import numpy as np

# A dense island in the lower-middle of the embedding.
X_LO, X_HI = 6.0, 9.5
Y_LO, Y_HI = -5.5, -2.0
W, H = 700, 700

BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
             "#256abf", "#184f95", "#0d366b"]


def main() -> None:
    import xy
    from PIL import Image

    emb = np.load("data/umap2.npy")
    tot = np.load("data/cell_meta.npz")["total_counts"]
    c = np.log10(np.maximum(tot, 1.0)).astype(np.float32)

    # ---- what the exported raster can give you: crop + upscale ----
    full = Image.open("results/artifacts/matplotlib_1306127.png")
    # Map data coords -> pixel coords of the 900x700 matplotlib axes box.
    # Axes box measured from the saved figure's layout.
    ax_l, ax_r, ax_t, ax_b = 62, 723, 33, 640
    dx_lo, dx_hi = -5.4, 18.0     # matplotlib's autoscaled data limits
    dy_lo, dy_hi = -6.3, 18.5

    def px(x, y):
        fx = (x - dx_lo) / (dx_hi - dx_lo)
        fy = (y - dy_lo) / (dy_hi - dy_lo)
        return ax_l + fx * (ax_r - ax_l), ax_b - fy * (ax_b - ax_t)

    x0, y1 = px(X_LO, Y_LO)
    x1, y0 = px(X_HI, Y_HI)
    crop = full.crop((int(x0), int(y0), int(x1), int(y1)))
    crop = crop.resize((W, H), Image.NEAREST)
    crop.save("results/artifacts/fidelity_matplotlib_zoom.png")
    print(f"matplotlib crop: source region was {crop.width}x{crop.height} upscaled "
          f"from {int(x1-x0)}x{int(y1-y0)} px")

    # ---- what XY gives you: the same window, re-rendered from source rows ----
    sel = ((emb[:, 0] >= X_LO) & (emb[:, 0] <= X_HI)
           & (emb[:, 1] >= Y_LO) & (emb[:, 1] <= Y_HI))
    print(f"cells in window: {int(sel.sum()):,}")

    chart = xy.scatter_chart(
        xy.scatter(emb[:, 0], emb[:, 1], color=c, colormap=BLUE_RAMP,
                   size=3.0, opacity=0.7, density=None),
        xy.x_axis(label="UMAP 1", domain=(X_LO, X_HI)),
        xy.y_axis(label="UMAP 2", domain=(Y_LO, Y_HI)),
        xy.theme(background="#fcfcfb", plot_background="#fcfcfb",
                 grid_color="#e1e0d9", axis_color="#c3c2b7", text_color="#0b0b0b"),
        title=None, width=W, height=H,
    )
    chart.write_image("results/artifacts/fidelity_xy_zoom.png",
                      width=W, height=H, scale=1)
    print("wrote results/artifacts/fidelity_xy_zoom.png")


if __name__ == "__main__":
    main()
