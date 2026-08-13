"""Benchmark charts, built with XY itself.

Each chart carries two series, so a legend is always present and the marks are
directly readable. Colour follows the library, not the rank: XY is blue in every
chart on the page, matplotlib orange, Plotly aqua.
"""

from __future__ import annotations

import xy

from . import data as D
from .theme import SERIES

LINE_W = 2.0
DOT = 9.0


def _theme() -> xy.Theme:
    return xy.theme(
        background="#fcfcfb", plot_background="#fcfcfb",
        grid_color="#e1e0d9", axis_color="#c3c2b7", text_color="#0b0b0b",
    )


def _series(name: str, lib: str, xs, ys):
    color = SERIES[lib]["light"]
    return [
        xy.line(xs, ys, name=name, color=color, width=LINE_W),
        xy.scatter(xs, ys, color=color, size=DOT, opacity=1.0,
                   stroke="#fcfcfb", stroke_width=1.5),
    ]


def _chart(title, y_label, specs, y_format=None, log_y=False, height=340,
           x_domain=None):
    children = []
    for name, lib, xs, ys in specs:
        children.extend(_series(name, lib, xs, ys))
    # Pin the log domain to the measured range; the autoscaled default leaves a
    # decade of empty gutter before the first point.
    if x_domain is None:
        all_x = [v for _, _, xs, _ in specs for v in xs]
        x_domain = (min(all_x) * 0.8, max(all_x) * 1.25)
    children += [
        xy.x_axis(label="cells plotted", type_="log", tick_count=5, format=",.0f",
                  domain=x_domain),
        xy.y_axis(label=y_label, type_="log" if log_y else None,
                  format=y_format, tick_count=6),
        xy.legend(loc="upper left"),
        _theme(),
    ]
    return xy.chart(*children, title=title, width=560, height=height,
                    padding=(12, 18, 46, 74))


def time_to_first_plot() -> xy.Chart:
    xs_xy, ys_xy = D.series(D.inter_rows("xy"), "t_load_ms")
    xs_pl, ys_pl = D.series(D.inter_rows("plotly"), "t_load_ms")
    return _chart(
        "Time to first plot in the browser",
        "milliseconds until load",
        [("XY", "xy", xs_xy, ys_xy), ("Plotly", "plotly", xs_pl, ys_pl)],
        y_format=",.0f",
    )


def browser_memory() -> xy.Chart:
    xs_xy, ys_xy = D.series(D.inter_rows("xy"), "js_heap_mb")
    xs_pl, ys_pl = D.series(D.inter_rows("plotly"), "js_heap_mb")
    return _chart(
        "Browser memory held by the chart",
        "JS heap (MB)",
        [("XY", "xy", xs_xy, ys_xy), ("Plotly", "plotly", xs_pl, ys_pl)],
        y_format=",.0f",
    )


def static_render() -> xy.Chart:
    xs_xy, ys_xy = D.series(D.bench_rows("xy"), "t_export_png")
    xs_mp, ys_mp = D.series(D.bench_rows("matplotlib"), "t_export_png")
    return _chart(
        "Time to rasterise a PNG",
        "seconds",
        [("XY", "xy", xs_xy, ys_xy), ("matplotlib", "matplotlib", xs_mp, ys_mp)],
        y_format=",.2f", log_y=True,
    )


def file_size() -> xy.Chart:
    rows_xy = [r for r in D.bench_rows("xy") if r.get("bytes_html")]
    rows_pl = [r for r in D.bench_rows("plotly") if r.get("bytes_html")]
    return _chart(
        "Size of the self-contained HTML file",
        "megabytes",
        [("XY", "xy", [r["n"] for r in rows_xy], [r["bytes_html"] / 1e6 for r in rows_xy]),
         ("Plotly", "plotly", [r["n"] for r in rows_pl], [r["bytes_html"] / 1e6 for r in rows_pl])],
        y_format=",.1f",
    )


def umap_chart(stride: int = 1) -> xy.Chart:
    """The hero chart: every cell, coloured by sequencing depth."""
    cols = D.umap_columns(stride)
    from .theme import BLUE_RAMP
    return xy.scatter_chart(
        xy.scatter("umap1", "umap2", color="log_umi", colormap=BLUE_RAMP,
                   size=2.0, opacity=0.55, density=None,
                   zoom_size_factor=2.2, zoom_opacity=0.9),
        xy.x_axis(label="UMAP 1"),
        xy.y_axis(label="UMAP 2"),
        xy.colorbar(title="log10 UMI"),
        xy.tooltip(fields=["umap1", "umap2", "log_umi", "genes"],
                   labels={"umap1": "UMAP 1", "umap2": "UMAP 2",
                           "log_umi": "log10 UMI", "genes": "genes detected"},
                   format={"umap1": ".2f", "umap2": ".2f", "log_umi": ".2f",
                           "genes": ",.0f"}),
        xy.interaction_config(hover=True, zoom=True, pan=True),
        _theme(),
        data=cols,
        width=1080, height=720,
        padding=(14, 20, 48, 74),
    )
