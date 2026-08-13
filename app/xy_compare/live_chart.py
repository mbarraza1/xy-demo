"""The live, state-backed chart - the half of XY the exported file cannot show.

Two things matter here and both are deliberate:

1. The point count is 250M, not the 500M of the export. A live chart holds
   XY's canonical store resident at 16 bytes/point, so 500M would pin 8 GB and
   spike to ~18.7 GB while building - past what a 36 GB machine has free. At
   250M that is 4.0 GB resident and ~9.4 GB peak. Same behaviour, no swapping.

2. The columns are built ONCE per process, not once per session. `rx.State` is
   per-session, so a naive @rxy.data method would rebuild 3 GB of arrays for
   every browser tab. The lazy module-level cache below hands every session a
   reference to the same arrays.
"""

from __future__ import annotations

import threading
from typing import TypedDict

import numpy as np
import reflex as rx
import reflex_xy as rxy
import xy

from .theme import BLUE_RAMP

# 10M, not 250M. The live path re-scans source rows on every refine, so zoom
# latency tracks the total point count even though the payload does not: ~484 ms
# median refine here against 0.9-1.7 s at 250M. First paint is ~0.6 s either way
# and the Python build below costs 0.20 s, so the cost is entirely in refining.
# This section exists to prove drill-down resolves to individual markers, which
# was only observed at 10M; the 500M export above carries the scale argument.
N = 10_000_000

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
        if i:                                  # first copy stays exact
            xs[sl] += rng.normal(0, 0.06, take).astype(np.float32)
            ys[sl] += rng.normal(0, 0.06, take).astype(np.float32)
        written += take
        i += 1
    return {"umap1": xs, "umap2": ys, "log_umi": cs}


def columns() -> Cloud:
    """Built on first use and shared by every session in this process."""
    global _COLUMNS
    if _COLUMNS is None:
        with _LOCK:
            if _COLUMNS is None:
                _COLUMNS = _build(N)
    return _COLUMNS


class LiveState(rx.State):
    hovered: dict = {}

    @rxy.data
    def cloud(self) -> Cloud:
        return columns()

    @rx.event
    def record_hover(self, event: rxy.PointHoverEvent):
        datum = {**event.get("data", {}), **event.get("datum", {})}
        self.hovered = {k: datum[k] for k in ("umap1", "umap2", "log_umi")
                        if k in datum}


def live_chart() -> rx.Component:
    return rxy.scatter_chart(
        data=LiveState.cloud,
        x="umap1", y="umap2",
        color="log_umi", colormap=BLUE_RAMP,
        size=2.0, opacity=0.6, density=None,
        zoom_size_factor=2.2, zoom_opacity=0.9,
        x_axis=xy.x_axis(label="UMAP 1"),
        y_axis=xy.y_axis(label="UMAP 2"),
        on_hover=LiveState.record_hover,
        height="700px",
    )
