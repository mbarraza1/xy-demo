"""XY vs matplotlib vs Plotly at 250 million points - live chart, timings, summary."""

from __future__ import annotations

import reflex as rx

from . import data as D
from .live_chart import live_chart
from .theme import STYLESHEET

N = 250_000_000


def _fmt_secs(v: float | None) -> str:
    if v is None:
        return "-"
    if v < 60:
        return f"{v:,.2f} s"
    return f"{v/60:,.1f} min"


def _row(label: str, xy_v, pl_v, mp_v, note: str | None = None) -> rx.Component:
    def cell(v):
        bad = isinstance(v, str) and ("fail" in v.lower() or "never" in v.lower())
        return rx.table.cell(
            v, text_align="right", class_name="tabular",
            color="var(--series-matplotlib)" if bad else "var(--text)",
            font_weight="600" if bad else "400",
        )
    return rx.table.row(
        rx.table.cell(
            rx.box(rx.text(label, font_weight="500"),
                   rx.text(note, font_size="0.78rem", color="var(--muted)")
                   if note else rx.fragment())),
        cell(xy_v), cell(pl_v), cell(mp_v),
    )


def comparison_table() -> rx.Component:
    xy_build = D.big_at("xy", N, "t_build")
    pl_build = D.big_at("plotly", N, "t_build")
    mp_build = D.big_at("matplotlib", N, "t_build")
    xy_html = D.big_at("xy", N, "bytes_html")
    pl_html = D.big_at("plotly", N, "bytes_html")
    xy_exp = D.big_at("xy", N, "t_export_html")
    pl_exp = D.big_at("plotly", N, "t_export_html")
    mp_png = D.big_at("matplotlib", N, "t_export_png")
    xy_rss = D.big_at("xy", N, "peak_rss_gb")
    pl_rss = D.big_at("plotly", N, "peak_rss_gb")
    mp_rss = D.big_at("matplotlib", N, "peak_rss_gb")

    xy_paint = D.render_at("xy", N) or {}
    pl_paint = D.render_at("plotly", N) or {}

    return rx.box(
        rx.table.root(
            rx.table.header(rx.table.row(
                rx.table.column_header_cell(""),
                rx.table.column_header_cell("XY", text_align="right",
                                            color="var(--series-xy)"),
                rx.table.column_header_cell("Plotly", text_align="right",
                                            color="var(--series-plotly)"),
                rx.table.column_header_cell("matplotlib", text_align="right",
                                            color="var(--series-matplotlib)"),
            )),
            rx.table.body(
                _row("Build the figure in Python",
                     _fmt_secs(xy_build), _fmt_secs(pl_build), _fmt_secs(mp_build)),
                _row("Write the output file",
                     _fmt_secs(xy_exp), _fmt_secs(pl_exp), _fmt_secs(mp_png),
                     note="interactive HTML for XY and Plotly, PNG for matplotlib"),
                _row("Size of that file",
                     f"{xy_html/1e6:,.1f} MB" if xy_html else "-",
                     f"{pl_html/1e6:,.0f} MB" if pl_html else "-",
                     "0.3 MB"),
                _row("Open it in a browser",
                     f"{xy_paint.get('t_render_ms', 0):,.0f} ms"
                     if xy_paint.get("t_render_ms") else "-",
                     "fails to load" if pl_paint.get("status") != "ok" else "-",
                     "n/a", note="time until the plot is on screen"),
                _row("Peak memory while building",
                     f"{xy_rss:,.1f} GB" if xy_rss else "-",
                     f"{pl_rss:,.1f} GB" if pl_rss else "-",
                     f"{mp_rss:,.1f} GB" if mp_rss else "-"),
            ),
            variant="surface", size="2",
        ),
        background="var(--surface)", border="1px solid var(--border)",
        border_radius="12px", padding="1.25rem", overflow_x="auto", width="100%",
    )


def index() -> rx.Component:
    xy_exp = D.big_at("xy", N, "t_export_html") or 0
    pl_exp = D.big_at("plotly", N, "t_export_html") or 0
    mp_png = D.big_at("matplotlib", N, "t_export_png") or 0
    xy_paint = (D.render_at("xy", N) or {}).get("t_render_ms", 0)

    return rx.box(
        rx.box(
            rx.heading("250 million points, three ways", size="8",
                       color="var(--text)", line_height="1.15"),
            rx.text(
                "A single-cell UMAP scaled to 250 million points, rendered by XY, "
                "Plotly, and matplotlib on the same machine from the same arrays.",
                font_size="1.05rem", color="var(--text-secondary)",
                margin_top="0.7rem", line_height="1.6", max_width="700px",
            ),

            # ---- the chart ----
            rx.box(
                live_chart(),
                width="100%", margin_top="2rem",
                background="var(--surface)", border="1px solid var(--border)",
                border_radius="12px", padding="0.75rem",
            ),
            rx.text(
                "Live: drag to pan, scroll to zoom. Served by the running backend, "
                "which re-bins a real density window for each viewport - so the plot "
                "stays populated as you zoom. XY's exported file paints faster "
                f"({xy_paint:,.0f} ms) and needs no server at all, but it cannot be "
                "zoomed at this size: on zoom the client asks the kernel for a "
                "viewport-matched view, and a file has no kernel, so it falls through "
                "to the ~8,200-point sample baked into it. Measured, that drops the "
                "plot from 43% ink to 3.7% on the first wheel notch.",
                font_size="0.85rem", color="var(--muted)", margin_top="0.75rem",
                line_height="1.65",
            ),

            # ---- the numbers ----
            rx.heading("Time", size="6", margin_top="3rem",
                       margin_bottom="1rem", color="var(--text)"),
            comparison_table(),

            # ---- the summary ----
            rx.heading("In short", size="6", margin_top="3rem",
                       margin_bottom="0.9rem", color="var(--text)"),
            rx.box(
                rx.text(
                    f"XY produced a working interactive chart of 250 million points in ",
                    rx.text.strong(f"{xy_exp:,.1f} seconds"),
                    f", in a {D.big_at('xy', N, 'bytes_html')/1e6:.1f} MB file that opens "
                    f"in {xy_paint:,.0f} ms. Plotly took ",
                    rx.text.strong(f"{pl_exp:,.0f} seconds"),
                    " to write a 4.2 GB file that then fails to load in a browser at "
                    "all - so at this size it does not produce a usable result, only a "
                    "large one. matplotlib never fails, but takes ",
                    rx.text.strong(f"{mp_png/60:,.1f} minutes"),
                    " to rasterise a static PNG you cannot zoom.",
                    color="var(--text-secondary)", font_size="0.97rem",
                    line_height="1.75",
                ),
                rx.text(
                    "The reason is architectural rather than incremental. Plotly ships "
                    "every marker to the browser, so its cost tracks the point count "
                    "until the browser gives out. XY reduces to what the screen can "
                    "actually resolve before anything is sent, so its file is the same "
                    "1.9 MB at 10 million points as at 500 million. The trade is that "
                    "the exported file holds an overview, not the underlying rows.",
                    color="var(--text-secondary)", font_size="0.97rem",
                    line_height="1.75", margin_top="0.9rem",
                ),
                background="var(--surface)", border="1px solid var(--border)",
                border_radius="12px", padding="1.25rem",
            ),

            rx.text(
                "The 250M point cloud is the real 1,306,127-cell mouse brain UMAP "
                "(10x Genomics, E18) tiled with Gaussian jitter - the structure is "
                "real, the individual points are manufactured. Every library received "
                "the identical arrays. Measured on an Apple M3 Pro, 36 GB, macOS; "
                "xy 0.0.6, plotly 6.9.0, matplotlib 3.11.1.",
                font_size="0.8rem", color="var(--muted)", margin_top="2rem",
                line_height="1.65",
            ),
            max_width="960px", margin="0 auto", padding="3rem 1.5rem",
        ),
        background="var(--page)", min_height="100vh", width="100%",
    )


app = rx.App(head_components=[rx.el.style(STYLESHEET)])
app.add_page(index, title="250 million points, three ways")
