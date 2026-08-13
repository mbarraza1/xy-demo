"""A /live route that tests whether the STATE-BACKED adapter path drills down on zoom.

There are two distinct reflex_xy paths and they behave differently:

  static      rxy.chart(chart_obj) with a plain dict in data= - the adapter
              compiles a content-addressed binary asset at build time and the
              backend is never involved. Identical in behaviour to an export.
  state-backed  @rxy.data on a State method - columns travel as binary frames
              over the app's websocket and the chart is registered as live.

This route uses the second. The point count sits above XY's ~2M direct budget
so the first render is a density surface and any refinement on zoom is
unambiguous.
"""

from __future__ import annotations

from typing import TypedDict

import numpy as np
import reflex as rx
import reflex_xy as rxy
import xy

from .theme import BLUE_RAMP

N = 10_000_000


class Cloud(TypedDict):
    umap1: np.ndarray
    umap2: np.ndarray
    log_umi: np.ndarray


def _build(n: int) -> Cloud:
    emb = np.load("../data/umap2.npy")
    tot = np.load("../data/cell_meta.npz")["total_counts"]
    c = np.log10(np.maximum(tot, 1.0)).astype(np.float32)
    src = emb.shape[0]
    rng = np.random.default_rng(0)
    xs = np.empty(n, dtype=np.float32)
    ys = np.empty(n, dtype=np.float32)
    cs = np.empty(n, dtype=np.float32)
    w = 0
    i = 0
    while w < n:
        take = min(src, n - w)
        xs[w:w + take] = emb[:take, 0]
        ys[w:w + take] = emb[:take, 1]
        cs[w:w + take] = c[:take]
        if i:
            xs[w:w + take] += rng.normal(0, 0.06, take).astype(np.float32)
            ys[w:w + take] += rng.normal(0, 0.06, take).astype(np.float32)
        w += take
        i += 1
    return {"umap1": xs, "umap2": ys, "log_umi": cs}


class LiveState(rx.State):
    hovered: dict = {}

    @rxy.data
    def cloud(self) -> Cloud:
        return _build(N)

    @rx.event
    def record_hover(self, event: rxy.PointHoverEvent):
        self.hovered = {**event.get("data", {}), **event.get("datum", {})}


def live_probe() -> rx.Component:
    return rx.box(
        rx.heading(f"Live-kernel probe - {N:,} points", size="6"),
        rx.text("State-backed via @rxy.data, so the chart is registered live and "
                "columns travel over the app websocket.",
                color="#52514e", margin_bottom="1rem"),
        rxy.scatter_chart(
            data=LiveState.cloud,
            x="umap1", y="umap2",
            color="log_umi", colormap=BLUE_RAMP,
            size=2.0, opacity=0.6, density=None,
            x_axis=xy.x_axis(label="UMAP 1"),
            y_axis=xy.y_axis(label="UMAP 2"),
            on_hover=LiveState.record_hover,
            height="700px",
        ),
        rx.text(LiveState.hovered.to_string(), font_size="0.8rem",
                color="#898781", margin_top="0.75rem"),
        padding="2rem", background="#f9f9f7", min_height="100vh",
    )
