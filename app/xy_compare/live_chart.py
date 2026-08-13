"""The live, state-backed 250M chart.

Why this and not the exported file: on zoom, XY's client asks the kernel for a
viewport-matched density view. An exported HTML file has no kernel, so any zoom
falls through to the ~8,200 point sample baked into the file - measured, the
plot drops from 43% ink to 3.7% on the FIRST wheel notch and stays empty. The
export is fast and fine to look at, but it cannot be zoomed at this size.

A live backend re-serves a real density window for each viewport, so the chart
stays populated as you zoom. The cost is memory: XY's canonical store is a flat
16 bytes per point, and the float32 source columns are retained alongside it.

Columns are built once per process behind a lock and shared across sessions -
rx.State is per-session, so the naive version would rebuild them per browser tab.
"""

from __future__ import annotations

import threading
from typing import TypedDict

import numpy as np
import reflex as rx
import reflex_xy as rxy
import xy

from .theme import BLUE_RAMP

N = 250_000_000

_COLUMNS: dict | None = None
_LOCK = threading.Lock()


class Cloud(TypedDict):
    umap1: np.ndarray
    umap2: np.ndarray
    log_umi: np.ndarray


def _build(n: int) -> Cloud:
    emb = np.load("../data/umap2.npy")
    tot = np.load("../data/cell_meta.npz")["total_counts"]
    depth = np.log10(np.maximum(tot, 1.0)).astype(np.float32)
    src = emb.shape[0]
    rng = np.random.default_rng(0)
    xs = np.empty(n, dtype=np.float32)
    ys = np.empty(n, dtype=np.float32)
    cs = np.empty(n, dtype=np.float32)
    written = i = 0
    while written < n:
        take = min(src, n - written)
        sl = slice(written, written + take)
        xs[sl] = emb[:take, 0]
        ys[sl] = emb[:take, 1]
        cs[sl] = depth[:take]
        if i:                                   # first copy stays exact
            xs[sl] += rng.normal(0, 0.06, take).astype(np.float32)
            ys[sl] += rng.normal(0, 0.06, take).astype(np.float32)
        written += take
        i += 1
    return {"umap1": xs, "umap2": ys, "log_umi": cs}


def columns() -> Cloud:
    global _COLUMNS
    if _COLUMNS is None:
        with _LOCK:
            if _COLUMNS is None:
                _COLUMNS = _build(N)
    return _COLUMNS


class LiveState(rx.State):
    @rxy.data
    def cloud(self) -> Cloud:
        return columns()


def live_chart() -> rx.Component:
    return rxy.scatter_chart(
        data=LiveState.cloud,
        x="umap1", y="umap2",
        color="log_umi", colormap=BLUE_RAMP,
        size=2.0, opacity=0.6, density=None,
        x_axis=xy.x_axis(label="UMAP 1"),
        y_axis=xy.y_axis(label="UMAP 2"),
        height="700px",
    )
