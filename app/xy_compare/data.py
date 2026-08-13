"""Load the measured results and the UMAP embedding for the page."""

from __future__ import annotations

import json
import os

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(ROOT, "data")
RESULTS = os.path.join(ROOT, "results")

with open(os.path.join(RESULTS, "report_data.json")) as fh:
    REPORT = json.load(fh)

BENCH = REPORT["benchmark"]
INTERACTION = [r for r in REPORT["interaction"] if r.get("status") == "ok"]
PIPELINE = REPORT["pipeline"]
BIGSWEEP = REPORT.get("bigsweep", [])
BIGINTERACTION = REPORT.get("biginteraction", [])

BIG_N = 500_000_000

try:
    with open(os.path.join(RESULTS, "fidelity_meta.json")) as fh:
        FIDELITY = json.load(fh)
except (FileNotFoundError, json.JSONDecodeError):
    FIDELITY = {}


def big_rows(lib: str, key: str) -> list[dict]:
    """Successful big-sweep rows for one library that carry `key`."""
    return sorted(
        (r for r in BIGSWEEP
         if r["lib"] == lib and r.get("status") == "ok" and r.get(key) is not None),
        key=lambda r: r["n"],
    )


def big_at(lib: str, n: int, key: str):
    for r in BIGSWEEP:
        if r["lib"] == lib and r["n"] == n:
            return r.get(key)
    return None


def big_status(lib: str, n: int) -> str:
    for r in BIGSWEEP:
        if r["lib"] == lib and r["n"] == n:
            return r.get("status", "unknown")
    return "not_run"


def big_max_ok(lib: str, key: str):
    """Largest n at which this library successfully produced `key`, and its value."""
    rows = big_rows(lib, key)
    return (rows[-1]["n"], rows[-1][key]) if rows else (None, None)


# ---- browser render outcomes for the big artifacts ----

def render_rows(lib: str) -> list[dict]:
    return sorted((r for r in BIGINTERACTION if r["lib"] == lib),
                  key=lambda r: r["n"])


def render_at(lib: str, n: int) -> dict | None:
    for r in BIGINTERACTION:
        if r["lib"] == lib and r["n"] == n:
            return r
    return None


def last_rendering_n(lib: str):
    """Largest n whose exported file actually painted a canvas in the browser."""
    ok = [r for r in render_rows(lib) if r.get("rendered")]
    return ok[-1]["n"] if ok else None


def first_failing_n(lib: str):
    """Smallest n whose exported file failed to paint, however it failed."""
    bad = [r for r in render_rows(lib) if not r.get("rendered")]
    return bad[0]["n"] if bad else None


def first_silent_failure_n(lib: str):
    """Smallest n that loaded cleanly and then simply never drew anything."""
    bad = [r for r in render_rows(lib) if r.get("status") == "never_rendered"]
    return bad[0]["n"] if bad else None

N_CELLS = PIPELINE["n_cells"]
N_GENES_TOTAL = 27_998
NNZ = 2_624_828_308


def bench_rows(lib: str) -> list[dict]:
    return sorted((r for r in BENCH if r["lib"] == lib and r.get("status") == "ok"),
                  key=lambda r: r["n"])


def inter_rows(lib: str) -> list[dict]:
    return sorted((r for r in INTERACTION if r["lib"] == lib), key=lambda r: r["n"])


def series(rows: list[dict], key: str) -> tuple[list[int], list[float]]:
    xs, ys = [], []
    for r in rows:
        if r.get(key) is not None:
            xs.append(r["n"])
            ys.append(r[key])
    return xs, ys


def at(lib: str, n: int, key: str, source: str = "bench"):
    rows = bench_rows(lib) if source == "bench" else inter_rows(lib)
    for r in rows:
        if r["n"] == n:
            return r.get(key)
    return None


FULL = N_CELLS

# ---- headline numbers, computed from the measurements (never hand-typed) ----
HEADLINE = {
    "xy_load_ms": at("xy", FULL, "t_load_ms", "inter"),
    "plotly_load_ms": at("plotly", FULL, "t_load_ms", "inter"),
    "xy_heap_mb": at("xy", FULL, "js_heap_mb", "inter"),
    "plotly_heap_mb": at("plotly", FULL, "js_heap_mb", "inter"),
    "xy_png_s": at("xy", FULL, "t_export_png"),
    "mpl_png_s": at("matplotlib", FULL, "t_export_png"),
    "xy_html_mb": (at("xy", FULL, "bytes_html") or 0) / 1e6,
    "plotly_html_mb": (at("plotly", FULL, "bytes_html") or 0) / 1e6,
    "xy_build_s": at("xy", FULL, "t_build"),
    "plotly_build_s": at("plotly", FULL, "t_build"),
    "mpl_build_s": at("matplotlib", FULL, "t_build"),
}
HEADLINE["load_speedup"] = HEADLINE["plotly_load_ms"] / HEADLINE["xy_load_ms"]
HEADLINE["heap_ratio"] = HEADLINE["plotly_heap_mb"] / HEADLINE["xy_heap_mb"]
HEADLINE["png_speedup"] = HEADLINE["mpl_png_s"] / HEADLINE["xy_png_s"]

GL_RENDERER = INTERACTION[0].get("gl_renderer", "unknown") if INTERACTION else "unknown"


def umap_columns(stride: int = 1) -> dict:
    """Embedding columns for the live chart. stride>1 subsamples for lighter pages."""
    emb = np.load(os.path.join(DATA, "umap2.npy"), mmap_mode="r")
    tot = np.load(os.path.join(DATA, "cell_meta.npz"))["total_counts"]
    ngene = np.load(os.path.join(DATA, "cell_meta.npz"))["n_genes_by_cell"]
    sl = slice(None, None, stride)
    return {
        "umap1": np.ascontiguousarray(emb[sl, 0], dtype=np.float32),
        "umap2": np.ascontiguousarray(emb[sl, 1], dtype=np.float32),
        "log_umi": np.log10(np.maximum(tot[sl], 1.0)).astype(np.float32),
        "genes": ngene[sl].astype(np.float32),
    }
