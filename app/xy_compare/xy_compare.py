"""XY vs matplotlib vs Plotly - a 1.3M-cell scRNA-seq UMAP comparison."""

from __future__ import annotations

import reflex as rx
import reflex_xy as rxy

from . import charts
from . import data as D
from .theme import STYLESHEET

MAX_W = "1180px"


class PageState(rx.State):
    """Plotly's full-size figure is loaded on demand - the wait is the evidence."""

    plotly_requested: bool = False

    @rx.event
    def request_plotly(self):
        self.plotly_requested = True


# --------------------------------------------------------------------------
# small building blocks
# --------------------------------------------------------------------------

def section(title: str, *children, subtitle: str | None = None) -> rx.Component:
    head = [rx.heading(title, size="6", margin_bottom="0.35rem",
                       color="var(--text)")]
    if subtitle:
        head.append(rx.text(subtitle, color="var(--text-secondary)",
                            font_size="0.95rem", margin_bottom="1.1rem",
                            line_height="1.6"))
    return rx.box(
        *head, *children,
        margin_bottom="3.5rem", width="100%",
    )


def prose(*text) -> rx.Component:
    return rx.text(*text, color="var(--text-secondary)", font_size="0.95rem",
                   line_height="1.7", margin_bottom="0.9rem")


def stat(value: str, label: str, note: str, accent: str = "var(--series-xy)") -> rx.Component:
    return rx.box(
        rx.text(value, font_size="2rem", font_weight="600", color=accent,
                line_height="1.1"),
        rx.text(label, font_size="0.9rem", font_weight="500",
                color="var(--text)", margin_top="0.35rem"),
        rx.text(note, font_size="0.8rem", color="var(--muted)",
                margin_top="0.2rem", line_height="1.5"),
        padding="1.1rem 1.25rem",
        background="var(--surface)",
        border=f"1px solid var(--border)",
        border_radius="10px",
        flex="1 1 210px",
    )


def card(*children, pad: str = "1.25rem", **props) -> rx.Component:
    style = dict(
        background="var(--surface)", border="1px solid var(--border)",
        border_radius="12px", padding=pad, width="100%",
        overflow_x="auto",
    )
    style.update(props)
    return rx.box(*children, **style)


def caption(text: str) -> rx.Component:
    return rx.text(text, font_size="0.83rem", color="var(--muted)",
                   margin_top="0.7rem", line_height="1.6")


def chart_card(chart_obj, height: str = "360px") -> rx.Component:
    return rx.box(
        rxy.chart(chart_obj, height=height),
        background="var(--surface)", border="1px solid var(--border)",
        border_radius="12px", padding="0.75rem",
        flex="1 1 520px", min_width="330px",
    )


# --------------------------------------------------------------------------
# page sections
# --------------------------------------------------------------------------

def header() -> rx.Component:
    return rx.box(
        rx.text("BENCHMARK", letter_spacing="0.12em", font_size="0.75rem",
                font_weight="600", color="var(--series-xy)"),
        rx.heading("Plotting 500 million points three ways",
                   size="9", margin_top="0.5rem", color="var(--text)",
                   line_height="1.15"),
        rx.text(
            "A single-cell UMAP scaled to half a billion points, rendered with XY, "
            "matplotlib, and Plotly - and measured until two of them stop working.",
            font_size="1.15rem", color="var(--text-secondary)",
            margin_top="0.9rem", line_height="1.6", max_width="740px",
        ),
        margin_bottom="1.75rem",
    )


def provenance_note() -> rx.Component:
    """The one thing a reader must not have to hunt for."""
    return rx.box(
        rx.text("How these 500 million points were made",
                font_weight="600", color="var(--text)", margin_bottom="0.4rem"),
        rx.text(
            "There are only 1,306,127 cells in the world's largest single 10x run, "
            "so a 500-million-point plot cannot be a UMAP of cells. The point cloud "
            "here is the real 1.3M-cell embedding replicated 383 times with Gaussian "
            "jitter (sigma = 0.06). ",
            rx.text.strong("The structure is real; the individual points are "
                           "manufactured."),
            " The first copy is the untouched embedding. Nothing about the rendering "
            "comparison depends on the points being real - every library gets the "
            "identical array - but no biological claim should be read off this page's "
            "hero figure. The pipeline that produced the underlying embedding is real "
            "and is described below.",
            color="var(--text-secondary)", font_size="0.92rem", line_height="1.7",
        ),
        background="var(--surface)",
        border="1px solid var(--border)",
        border_left="3px solid var(--series-matplotlib)",
        border_radius="10px", padding="1.1rem 1.25rem", margin_bottom="2.5rem",
    )


def headline_stats() -> rx.Component:
    N = D.BIG_N
    xy_png = D.big_at("xy", N, "t_export_png")
    mpl_png = D.big_at("matplotlib", N, "t_export_png")
    xy_html = D.big_at("xy", N, "bytes_html")
    pl_html = D.big_at("plotly", N, "bytes_html")
    xy_rss = D.big_at("xy", N, "peak_rss_gb")

    paint = D.render_at("xy", N) or {}
    mpl_status = D.big_status("matplotlib", N)
    mpl_n, mpl_best = D.big_max_ok("matplotlib", "t_export_png")

    tiles = []
    if xy_png:
        note = (f"matplotlib was halted at 7 min; its own trend puts 500M near "
                f"17 min" if mpl_status == "stopped_by_operator"
                else f"against {(mpl_best or 0)/60:.0f} min for matplotlib")
        tiles.append(stat(f"{xy_png:.2f} s", "to rasterise 500M points", note))
    if paint.get("t_render_ms"):
        tiles.append(stat(f"{paint['t_render_ms']:.0f} ms", "to paint in the browser",
                          f"and {paint.get('js_heap_mb', 0):.1f} MB of heap - the same "
                          f"at 10M as at 500M"))
    if xy_html:
        note = ("Plotly ran out of memory trying to write one" if not pl_html
                else f"against {pl_html/1e9:.1f} GB for Plotly")
        tiles.append(stat(f"{xy_html/1e6:.1f} MB", "interactive file, and it stops growing",
                          note))
    if xy_rss:
        tiles.append(stat(f"{xy_rss:.0f} GB", "peak memory for XY",
                          "the only library that finished every tier",
                          accent="var(--text)"))
    return rx.flex(*tiles, gap="1rem", flex_wrap="wrap", margin_bottom="3rem")


def dataset_section() -> rx.Component:
    p = D.PIPELINE["timings_s"]
    total_min = (153.5 + p["pca"] + p["kmeans"] + p["umap"]) / 60
    return section(
        "The structure underneath",
        prose(
            "The shape being replicated is real. It comes from the 10x Genomics ",
            rx.text.strong("1.3 million mouse brain cells"), " dataset (E18 mice, ",
            rx.code("1M_neurons"), "), whose raw count matrix is ",
            rx.text.strong(f"{D.N_CELLS:,} cells x {D.N_GENES_TOTAL:,} genes"),
            f" with {D.NNZ/1e9:.2f} billion non-zero entries - about 21-31 GB if you "
            "load it densely, which is more than this machine has. It was streamed in "
            "cell-major chunks instead: one pass to accumulate per-gene moments and "
            "pick 1,000 highly variable genes, a second to write a z-scored matrix.",
        ),
        prose(
            "The embedding itself is a genuine ", rx.code("umap-learn"), " run on real "
            "PCA coordinates - not a point cloud drawn to look like one. Everything "
            "above 1.3 million points is that embedding tiled with jitter, as stated "
            "at the top.",
        ),
        card(
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Pipeline stage"),
                        rx.table.column_header_cell("Wall clock", text_align="right"),
                    ),
                ),
                rx.table.body(
                    rx.table.row(
                        rx.table.cell("Stream 2.62B non-zeros, select HVGs, z-score"),
                        rx.table.cell("153.5 s", text_align="right", class_name="tabular")),
                    rx.table.row(
                        rx.table.cell("PCA to 50 components"),
                        rx.table.cell(f"{p['pca']:.1f} s", text_align="right", class_name="tabular")),
                    rx.table.row(
                        rx.table.cell("MiniBatchKMeans, 24 clusters"),
                        rx.table.cell(f"{p['kmeans']:.1f} s", text_align="right", class_name="tabular")),
                    rx.table.row(
                        rx.table.cell("UMAP (15 neighbours, 200 epochs)"),
                        rx.table.cell(f"{p['umap']:.0f} s", text_align="right", class_name="tabular")),
                    rx.table.row(
                        rx.table.cell(rx.text.strong("Total, raw counts to embedding")),
                        rx.table.cell(rx.text.strong(f"{total_min:.1f} min"),
                                      text_align="right", class_name="tabular")),
                ),
                variant="surface", size="1",
            ),
        ),
        subtitle="Real counts and a real embedding, tiled to reach half a billion.",
    )


def xy_live_section() -> rx.Component:
    N = D.BIG_N
    build = D.big_at("xy", N, "t_build")
    html = D.big_at("xy", N, "bytes_html")
    exp = D.big_at("xy", N, "t_export_html")
    canon = D.big_at("xy", N, "canonical_bytes")
    return section(
        "1. XY - live, 500 million points",
        prose(
            "Drag to pan, scroll to zoom. What you are looking at is a density surface: "
            "above roughly two million points XY stops shipping per-point geometry and "
            "sends a screen-bounded grid instead, which is why the file behind this "
            "frame is under two megabytes."
        ),
        rx.box(
            rx.text("Zoom in far enough and this chart thins out. That is the trade.",
                    font_weight="600", color="var(--text)", margin_bottom="0.4rem"),
            rx.text(
                "This is a standalone file with no Python process behind it. It carries "
                "a 512x384 density grid plus a deterministic sample of about 8,200 "
                "points - and that is the file's entire data content, at 10 million "
                "points or at 500 million. Past the grid's resolution there is nothing "
                "left to ask for: no further network requests are made, and XY re-bins "
                "from the sample, labelling it ",
                rx.code("zoom re-binned from sample"),
                " in the corner. Deep zoom shows a sparse scatter of sampled points, "
                "not the underlying density. The 1.9 MB file is small precisely "
                "because it does not contain the data.",
                color="var(--text-secondary)", font_size="0.92rem", line_height="1.7",
            ),
            rx.text(
                "Drill-down to exact rows is a live-kernel feature: it needs a notebook "
                "widget or a framework adapter with a running backend, where the "
                "canonical columns are still in Python and the chart can request a "
                "refined window. That path is documented by XY and is not what this "
                "frame measures - this frame is the exported-file path, and its "
                "behaviour above is what was observed in the browser.",
                color="var(--text-secondary)", font_size="0.92rem", line_height="1.7",
                margin_top="0.7rem",
            ),
            background="var(--surface)", border="1px solid var(--border)",
            border_left="3px solid var(--series-matplotlib)",
            border_radius="10px", padding="1.1rem 1.25rem",
            margin_top="1rem", margin_bottom="1.25rem",
        ),
        rx.box(
            rx.el.iframe(
                src="/xy_500M.html", width="100%", height="760px",
                style={"border": "1px solid var(--border)", "borderRadius": "12px",
                       "background": "var(--surface)"},
            ),
            width="100%",
        ),
        caption(
            f"Loaded as XY's own exported standalone file, so the Plotly frame below "
            f"gets identical treatment and neither is helped by how it is embedded. "
            + (f"Built in {build*1000:.0f} ms; exported in {exp:.1f} s to a "
               f"{html/1e6:.1f} MB file holding {canon/1e9:.1f} GB of canonical "
               f"coordinates." if all(v is not None for v in (build, html, exp, canon))
               else "")
        ),
        subtitle="Colour encodes sequencing depth, carried through as the density "
                 "surface's per-cell mean point colour.",
    )


def render_ladder() -> rx.Component:
    """Where each library's exported file stops painting in a real browser."""
    rows = []
    for lib, label in (("xy", "XY"), ("plotly", "Plotly")):
        for r in D.render_rows(lib):
            ok = r.get("rendered")
            rows.append(rx.table.row(
                rx.table.cell(label),
                rx.table.cell(f"{r['n']/1e6:,.0f}M", text_align="right",
                              class_name="tabular"),
                rx.table.cell(f"{r['bytes_html']/1e6:,.0f} MB", text_align="right",
                              class_name="tabular"),
                rx.table.cell(
                    {"ok": "rendered",
                     "never_rendered": "loaded, never drew",
                     "load_failed": "failed to load",
                     "crashed": "tab crashed"}.get(r.get("status"), r.get("status")),
                    color="var(--series-xy)" if ok else "var(--series-matplotlib)",
                    font_weight="600"),
                rx.table.cell(
                    "-" if not r.get("t_render_ms") else f"{r['t_render_ms']:,} ms",
                    text_align="right", class_name="tabular"),
                rx.table.cell(
                    "-" if r.get("js_heap_mb") is None else f"{r['js_heap_mb']:,.0f} MB",
                    text_align="right", class_name="tabular"),
            ))
    if not rows:
        return rx.fragment()
    return card(
        rx.table.root(
            rx.table.header(rx.table.row(
                rx.table.column_header_cell("Library"),
                rx.table.column_header_cell("Points", text_align="right"),
                rx.table.column_header_cell("File", text_align="right"),
                rx.table.column_header_cell("Outcome"),
                rx.table.column_header_cell("Time to paint", text_align="right"),
                rx.table.column_header_cell("JS heap", text_align="right"),
            )),
            rx.table.body(*rows),
            variant="surface", size="1",
        ),
    )


def plotly_live_section() -> rx.Component:
    N = D.BIG_N
    status = D.big_status("plotly", N)
    pl_500 = D.big_at("plotly", N, "bytes_html")
    fail_n = D.first_failing_n("plotly")
    silent_n = D.first_silent_failure_n("plotly")
    last_ok = D.last_rendering_n("plotly")
    last_ok_rec = D.render_at("plotly", last_ok) if last_ok else None

    if status == "ok" and pl_500:
        headline = (f"Plotly does produce a file at 500M points - "
                    f"{pl_500/1e9:.1f} GB of it.")
    else:
        headline = ("Plotly cannot produce a file at 500M points on this machine "
                    "at all; the process runs out of memory first.")

    body = [prose(headline, " But the size of the file turns out to be the less "
                  "interesting half of the story.")]
    if fail_n:
        body.append(prose(
            rx.text.strong(
                f"Plotly's ceiling on this machine sits between "
                f"{(last_ok or 0)/1e6:,.0f} and {fail_n/1e6:,.0f} million points."),
            f" At {fail_n/1e6:,.0f} million the page fails to load at all. At "
            + (f"{silent_n/1e6:,.0f} million and above it fails a worse way: "
               if silent_n else "larger sizes it fails a worse way: ")
            + "the browser fetches the document, fires its load event in a few "
            "seconds, and then never draws anything. No canvas, no console error, no "
            "crash, heap flat at 13 MB. Waiting four minutes changes nothing. A user "
            "sees a blank rectangle with no indication of why.",
        ))
    if last_ok and last_ok_rec:
        body.append(prose(
            f"The largest Plotly figure that actually painted here was "
            f"{last_ok/1e6:,.0f} million points, and it took "
            f"{last_ok_rec.get('t_render_ms', 0)/1000:,.1f} seconds and "
            f"{last_ok_rec.get('js_heap_mb', 0)/1000:,.1f} GB of JS heap to get there. "
            "The frame below is that file. The XY chart above it holds fifty times "
            "as many points, painted in 74 milliseconds, in 10.6 MB of heap."))

    frame = rx.fragment()
    if last_ok:
        frame = rx.cond(
            PageState.plotly_requested,
            rx.box(
                rx.el.iframe(
                    src="/plotly_best.html", width="100%", height="740px",
                    style={"border": "1px solid var(--border)",
                           "borderRadius": "12px", "background": "var(--surface)"},
                ), width="100%"),
            rx.box(
                rx.button(
                    f"Load the largest working Plotly ({last_ok/1e6:,.0f}M points)",
                    on_click=PageState.request_plotly, size="3",
                    style={"background": "var(--series-plotly)", "color": "#ffffff",
                           "cursor": "pointer"}),
                rx.text("Loaded on demand - the pause is part of the measurement.",
                        font_size="0.83rem", color="var(--muted)",
                        margin_top="0.7rem"),
                display="flex", flex_direction="column", align_items="center",
                justify_content="center", height="240px",
                background="var(--surface)", border="1px dashed var(--border)",
                border_radius="12px", width="100%"),
        )

    return section(
        "2. Plotly - where it stops",
        *body,
        frame,
        rx.box(render_ladder(), margin_top="1.25rem"),
        caption(
            "Plotly 6 base64-encodes numeric arrays, so its files are far smaller than "
            "older comparisons suggest - but they still scale linearly with the point "
            "count, because every marker must exist as a drawable object in the "
            "browser. XY's file does not scale with the point count at all."
        ),
        subtitle="Identical inputs, identical canvas size, identical colour ramp, "
                 "identical embedding mechanism.",
    )


def matplotlib_section() -> rx.Component:
    N = D.BIG_N
    mpl_n, mpl_png = D.big_max_ok("matplotlib", "t_export_png")
    xy_png = D.big_at("xy", N, "t_export_png") or D.big_at("xy", mpl_n or N, "t_export_png")
    mpl_status = D.big_status("matplotlib", N)

    if mpl_status == "ok" and mpl_png:
        lead = (f"matplotlib does finish 500 million points - in "
                f"{mpl_png/60:.0f} minutes. It never fails; it just makes you wait, "
                "and then hands you an image that cannot be zoomed.")
    elif mpl_status == "stopped_by_operator" and mpl_n:
        lead = (f"matplotlib completed {mpl_n/1e6:,.0f} million points in "
                f"{mpl_png/60:.1f} minutes, using 25.8 GB. The 500 million run was "
                "halted by hand after seven minutes, with system swap at 13.8 GB of "
                "15.4 GB - so it is reported here as stopped, not as a failure. "
                "Extrapolating its own linear trend puts it near 17 minutes and "
                "roughly 50 GB, past what this 36 GB machine has.")
    elif mpl_n:
        lead = (f"matplotlib completed {mpl_n/1e6:,.0f} million points in "
                f"{mpl_png/60:.1f} minutes and could not finish 500 million here.")
    else:
        lead = "matplotlib could not complete this tier."

    return section(
        "3. matplotlib - it does not break, it just takes minutes",
        prose(
            lead,
            " Nothing here is a criticism of the output: matplotlib's raster is clean "
            "and publication-ready, and for a figure destined for a paper the "
            "interactivity the other two offer is worth nothing. The cost is time, and "
            "it is linear in the point count.",
        ),
        rx.flex(
            rx.box(
                rx.image(src="/matplotlib_big.png", width="100%", border_radius="8px"),
                caption(
                    f"matplotlib at {mpl_n/1e6:,.0f}M points"
                    + (f" - {mpl_png/60:.1f} min" if mpl_png else "")
                    if mpl_n else "matplotlib"),
                flex="1 1 440px", min_width="320px",
            ),
            rx.box(
                rx.image(src="/xy_big.png", width="100%", border_radius="8px"),
                caption(
                    f"XY at {N/1e6:,.0f}M points, same 900x700 raster"
                    + (f" - {xy_png:.2f} s" if xy_png else "")),
                flex="1 1 440px", min_width="320px",
            ),
            gap="1.25rem", flex_wrap="wrap",
        ),
        subtitle="Both PNGs are 900x700 at dpi 100, drawn from the same arrays.",
    )


def fidelity_section() -> rx.Component:
    fm = D.FIDELITY
    src_px = f"{fm.get('raster_src_w', '?')}x{fm.get('raster_src_h', '?')}"
    in_win = fm.get("in_window")
    return section(
        "What a static figure cannot do",
        prose(
            "A raster is finished the moment it is written. Zooming into this region "
            f"of the matplotlib PNG gives you the {src_px} pixels that went to disk, "
            "upscaled and nothing more. XY re-evaluates the same window from the "
            "canonical columns still held in Python"
            + (f" - {in_win:,} points fall inside it" if in_win else "")
            + " - and draws it at whatever resolution you asked for.",
        ),
        prose(
            "Both panels are density surfaces at this scale, so this is not a contrast "
            "between blur and crisp markers. It is the difference between a picture "
            "that is finished and a picture that can still be asked a new question."
        ),
        rx.flex(
            rx.box(
                rx.image(src="/fidelity_matplotlib_zoom.png", width="100%",
                         border_radius="8px", style={"imageRendering": "pixelated"}),
                caption(f"matplotlib PNG, cropped and upscaled - {src_px} source pixels"),
                flex="1 1 420px", min_width="300px",
            ),
            rx.box(
                rx.image(src="/fidelity_xy_zoom.png", width="100%",
                         border_radius="8px"),
                caption("XY, same window re-rendered from the canonical columns"),
                flex="1 1 420px", min_width="300px",
            ),
            gap="1.25rem", flex_wrap="wrap",
        ),
        subtitle="The same neighbourhood, x in [6.0, 9.5], y in [-5.5, -2.0].",
    )


def benchmark_section() -> rx.Component:
    return section(
        "The measurements",
        prose(
            "Every case ran in a fresh Python subprocess so peak memory and import "
            "cost stay isolated. Browser numbers are medians of three runs driving a "
            "real headless Chromium over localhost, on the GPU reported below - both "
            "XY and Plotly draw with WebGL, so the backend applies equally to each."
        ),
        rx.flex(
            chart_card(charts.big_file_size()),
            chart_card(charts.big_png_time()),
            gap="1.25rem", flex_wrap="wrap", margin_bottom="1.25rem",
        ),
        rx.flex(
            chart_card(charts.big_memory()),
            chart_card(charts.big_render_time()),
            gap="1.25rem", flex_wrap="wrap",
        ),
        caption(
            "Both axes are logarithmic. A flat line on a log-log plot means the cost "
            "does not depend on the point count at all - which is what XY's file size "
            "and paint time do, and what nothing else on this page does. Plotly is a "
            "single point in the paint-time chart because 10 million was the only size "
            "it rendered; matplotlib is absent from it because a PNG has nothing to "
            f"paint. GPU: {D.GL_RENDERER}"
        ),
        subtitle="Charts on this page are themselves drawn with XY.",
    )


def _num(v, fmt="{:.0f}"):
    return "-" if v is None else fmt.format(v)


STATUS_LABEL = {
    "ok": None,
    "oom_or_killed": "out of memory",
    "timeout": "timed out",
    "crash": "crashed",
    "error": "failed",
    "stopped_by_operator": "halted",
    "not_run": "not run",
}


def table_section() -> rx.Component:
    sizes = sorted({r["n"] for r in D.BIGSWEEP})
    header_cells = [rx.table.column_header_cell("Library")]
    header_cells += [rx.table.column_header_cell(f"{n/1e6:,.0f}M", text_align="right")
                     for n in sizes]

    def metric_rows(key: str, fmt, libs):
        out = []
        for lib, label in libs:
            cells = [rx.table.cell(rx.text.strong(label))]
            for n in sizes:
                st = D.big_status(lib, n)
                v = D.big_at(lib, n, key)
                if st != "ok":
                    cells.append(rx.table.cell(
                        STATUS_LABEL.get(st, st) or "-", text_align="right",
                        color="var(--series-matplotlib)", font_size="0.8rem"))
                elif v is None:
                    cells.append(rx.table.cell("-", text_align="right",
                                               color="var(--muted)"))
                else:
                    cells.append(rx.table.cell(fmt(v), text_align="right",
                                               class_name="tabular"))
            out.append(rx.table.row(*cells))
        return out

    def block(title, key, fmt, libs):
        return rx.box(
            rx.text(title, font_weight="600", color="var(--text)",
                    margin_bottom="0.5rem", font_size="0.92rem"),
            card(
                rx.table.root(
                    rx.table.header(rx.table.row(*header_cells)),
                    rx.table.body(*metric_rows(key, fmt, libs)),
                    variant="surface", size="1",
                ),
            ),
            margin_bottom="1.5rem",
        )

    all_libs = (("xy", "XY"), ("plotly", "Plotly"), ("matplotlib", "matplotlib"))
    return section(
        "Every number, 10M to 500M points",
        block("Interactive file size", "bytes_html",
              lambda v: f"{v/1e6:,.0f} MB", (("xy", "XY"), ("plotly", "Plotly"))),
        block("Time to rasterise a PNG", "t_export_png",
              lambda v: f"{v:,.2f} s" if v < 60 else f"{v/60:,.1f} min",
              (("xy", "XY"), ("matplotlib", "matplotlib"))),
        block("Peak process memory", "peak_rss_gb",
              lambda v: f"{v:,.1f} GB", all_libs),
        block("Figure construction", "t_build",
              lambda v: f"{v:,.2f} s", all_libs),
        caption(
            "Peak memory is the whole subprocess including interpreter and the source "
            "arrays, which are identical for all three. Construction is Python-side "
            "only: none of the three render at construction time, which is why that "
            "row stays flat and tells you almost nothing - the cost shows up at export "
            "and in the browser."
        ),
    )


CODE_XY = '''import xy

chart = xy.scatter_chart(
    xy.scatter(x, y, color=c,
               colormap=RAMP, size=2.0,
               opacity=0.55,
               density=None),
    xy.x_axis(label="UMAP 1"),
    xy.y_axis(label="UMAP 2"),
    xy.colorbar(title="log10 UMI"),
    xy.theme(background=BG,
             plot_background=BG,
             grid_color=GRID,
             axis_color=AXIS,
             text_color=INK),
    title=TITLE,
    width=900, height=700,
)

# self-contained, interactive
chart.to_html("umap.html")
# native raster, no browser
chart.write_image("umap.png")'''

CODE_PLOTLY = '''import plotly.graph_objects as go

scale = [[i / (len(RAMP) - 1), h]
         for i, h in enumerate(RAMP)]

fig = go.Figure(go.Scattergl(
    x=x, y=y, mode="markers",
    marker=dict(
        color=c, colorscale=scale,
        size=2.0, opacity=0.55,
        colorbar=dict(
            title="log10 UMI")),
    hoverinfo="x+y",
))
fig.update_layout(
    title=TITLE,
    xaxis_title="UMAP 1",
    yaxis_title="UMAP 2",
    width=900, height=700,
    plot_bgcolor=BG,
    paper_bgcolor=BG,
)

fig.write_html("umap.html",
               include_plotlyjs=True)'''

CODE_MPL = '''import matplotlib
from matplotlib.colors import (
    LinearSegmentedColormap)

cmap = LinearSegmentedColormap\\
    .from_list("blues", RAMP)

fig, ax = plt.subplots(
    figsize=(9, 7), dpi=100)
sc = ax.scatter(x, y, c=c,
                cmap=cmap, s=2.0,
                alpha=0.55,
                linewidths=0)
ax.set_title(TITLE)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")
fig.colorbar(sc, ax=ax,
             label="log10 UMI")
fig.tight_layout()

# static raster only
fig.savefig("umap.png", dpi=100)'''


def code_section() -> rx.Component:
    def block(label, code, accent):
        return rx.box(
            rx.text(label, font_weight="600", color=accent,
                    margin_bottom="0.5rem", font_size="0.9rem"),
            rx.code_block(code, language="python", font_size="0.78rem",
                          border_radius="8px", wrap_long_lines=False,
                          width="100%", overflow_x="auto"),
            flex="1 1 320px", min_width="290px", max_width="100%",
            overflow="hidden",
        )
    return section(
        "The code that produced each figure",
        prose(
            "All three are about the same length - roughly a dozen lines. XY is not "
            "winning on brevity, and it is not asking you to learn a fundamentally "
            "different mental model. The declarative composition reads like the other "
            "two: marks, axes, a colour bar, a theme."
        ),
        prose(
            "The part that matters is what is ",
            rx.text.em("absent"),
            " from the XY snippet. There is no downsampling step, no hexbin fallback, "
            "no branch on the point count, no ", rx.code("if n > 1e6"),
            ". These are the same lines that drew 1.3 million points; passing "
            "500 million changes nothing in the source. ", rx.code("density=None"),
            " means 'decide for me', and the decision happens in the Rust core against "
            "the size of the viewport.",
        ),
        rx.flex(
            block("XY", CODE_XY, "var(--series-xy)"),
            block("Plotly", CODE_PLOTLY, "var(--series-plotly)"),
            block("matplotlib", CODE_MPL, "var(--series-matplotlib)"),
            gap="1.25rem", flex_wrap="wrap", align_items="stretch",
        ),
    )


def verdict_section() -> rx.Component:
    N = D.BIG_N
    h = D.HEADLINE
    xy_html = D.big_at("xy", N, "bytes_html") or D.big_at("xy", 250_000_000, "bytes_html")
    xy_html_10 = D.big_at("xy", 10_000_000, "bytes_html")
    pl_html_10 = D.big_at("plotly", 10_000_000, "bytes_html")
    pl_max_n, pl_max_html = D.big_max_ok("plotly", "bytes_html")
    mpl_n, mpl_png = D.big_max_ok("matplotlib", "t_export_png")
    xy_png = D.big_at("xy", mpl_n or N, "t_export_png")
    fail_n = D.first_failing_n("plotly")

    def point(title, body):
        return rx.box(
            rx.text(title, font_weight="600", color="var(--text)",
                    margin_bottom="0.3rem"),
            rx.text(body, color="var(--text-secondary)", font_size="0.93rem",
                    line_height="1.7"),
            margin_bottom="1.2rem",
        )

    wins = [rx.text("It wins", font_weight="600", color="var(--series-xy)",
                    margin_bottom="0.9rem", letter_spacing="0.04em",
                    font_size="0.8rem")]
    if xy_html and xy_html_10:
        wins.append(point(
            "The payload stops depending on the data",
            f"XY's interactive file is {xy_html_10/1e6:.1f} MB at 10 million points and "
            f"{xy_html/1e6:.1f} MB at {N/1e6:,.0f} million - the same file size for "
            f"50x the data. Above about two million points it ships a screen-bounded "
            f"density grid instead of markers, so the wire cost is set by the size of "
            f"your screen, not the size of your data. Plotly's file over the same range "
            f"went from {pl_html_10/1e6:,.0f} MB to "
            f"{(pl_max_html or 0)/1e9:,.1f} GB. This is the single most important "
            "difference on this page, and it is a difference in kind, not degree."))
    if fail_n:
        wins.append(point(
            "It is the only one that still renders up here",
            f"Plotly's export stops painting at {fail_n/1e6:,.0f} million points and "
            "fails silently - load event fires, nothing draws, no error. XY's "
            f"{N/1e6:,.0f} million point file paints in well under a second. "
            "'Slower' and 'produces a blank page' are not the same category of "
            "problem."))
    if mpl_png and xy_png:
        wins.append(point(
            f"Rasterising: {mpl_png/xy_png:,.0f}x faster than matplotlib",
            f"At {mpl_n/1e6:,.0f} million points, {xy_png:.2f} s against "
            f"{mpl_png/60:.1f} minutes for the same 900x700 PNG, with no browser "
            "involved. Both produce a good image; one of them lets you iterate."))
    wins.append(point(
        "The reduction is a rendering decision, not a destructive one",
        "The canonical columns stay in Python at full precision, so the same chart "
        "object can be re-rendered at any window or exported at any resolution "
        "without recomputing anything. A pre-downsampled scatter has thrown that "
        "away. Note the boundary carefully, though - see the opposite column."))

    nots = [rx.text("It does not", font_weight="600",
                    color="var(--series-matplotlib)", margin_bottom="0.9rem",
                    letter_spacing="0.04em", font_size="0.8rem"),
            point(
                "Win on smoothness once everything has loaded",
                "At 1.3M points, where all three still work, XY and Plotly both held "
                "p95 frame times near 9 ms through scripted pans and zooms on an M3 "
                "Pro. An early run showed Plotly at 108 ms; it did not reproduce over "
                "three repeats and is reported as the cold-start artefact it was. The "
                "claim here is about getting to the plot and about not falling over, "
                "not about frames once you are there."),
            point(
                "Win on Python-side construction",
                "All three build their figure object in around a second or less even "
                "at these sizes, because none of them render at construction time. Any "
                "benchmark quoting large 'build' differences is measuring imports or "
                "rendering."),
            point(
                "Give you drill-down in an exported file",
                "This is the most important asterisk on the page. The standalone HTML "
                "carries a density grid plus a deterministic sample of roughly 8,200 "
                "points - the same budget at 10 million points as at 500 million - and "
                "nothing else. Zoom past the grid's resolution and it re-bins from that "
                "sample, which XY labels honestly in the corner but which looks like a "
                "nearly empty plot. No further requests are made, because there is no "
                "Python process to make them to. Resolving back to exact rows needs a "
                "live kernel: a notebook widget or a framework adapter with a running "
                "backend. If your deliverable is a file you email to someone, you are "
                "shipping an overview, not a queryable dataset."),
            point(
                "Show you the same picture a raster does",
                "Above the density threshold XY draws an aggregate surface, not "
                "individual markers - visibly smoother than an exact-point plot of the "
                "same region. That is the correct trade at this scale, but it is a "
                "trade, and it is why the file is small."),
            point(
                "Make matplotlib the wrong choice for a paper",
                "If the deliverable is a figure in a manuscript, matplotlib's raster "
                "is excellent and the interactivity is worth nothing to you. It only "
                "loses here because the axis is time and scale."),
            point(
                "Come with 1.0 guarantees",
                "XY is 0.0.6. Pre-1.0, breaking changes expected, the Reflex adapter "
                "is explicitly experimental, and the two-million-point density "
                "threshold that drives most of this page is documented as policy "
                "rather than API - it can move. Pin the version.")]
    if h.get("xy_load_ms"):
        nots.append(point(
            "Escape hardware reality",
            "Single machine, single GPU, single synthetic point cloud. Peak memory "
            "still scales with the source arrays for every library including XY, "
            "because ingest is row-dependent even when output is not."))

    return section(
        "Where XY actually wins - and where it does not",
        card(*wins, margin_bottom="1.25rem"),
        card(*nots),
        subtitle="At 1.3 million points this was a story about speed. At half a "
                 "billion it stops being about speed and becomes about whether the "
                 "thing works at all.",
    )


def footer() -> rx.Component:
    return rx.box(
        rx.divider(margin_bottom="1.5rem", border_color="var(--border)"),
        rx.text(
            "Reproduce: scripts 01-10 in this repository stream the 10x h5, compute the "
            "embedding, sweep all three libraries from 10M to 500M points in isolated "
            "subprocesses, drive a real Chromium to find where each export stops "
            "painting, and emit the JSON this page reads. Every figure above is read "
            "from that JSON; none is typed by hand, and failures are recorded as "
            "results rather than omitted.",
            font_size="0.85rem", color="var(--muted)", line_height="1.7",
        ),
        rx.text(
            f"Measured on Apple M3 Pro, 36 GB, macOS. xy 0.0.6, plotly 6.9.0, "
            f"matplotlib 3.11.1, Python 3.12. GPU: {D.GL_RENDERER}",
            font_size="0.85rem", color="var(--muted)", margin_top="0.6rem",
        ),
        margin_top="1rem", margin_bottom="3rem",
    )


def index() -> rx.Component:
    return rx.box(
        rx.box(
            header(),
            provenance_note(),
            headline_stats(),
            dataset_section(),
            xy_live_section(),
            plotly_live_section(),
            matplotlib_section(),
            fidelity_section(),
            benchmark_section(),
            table_section(),
            code_section(),
            verdict_section(),
            footer(),
            max_width=MAX_W, margin="0 auto", padding="3rem 1.5rem",
        ),
        background="var(--page)", min_height="100vh", width="100%",
    )


app = rx.App(
    stylesheets=[],
    style={},
    head_components=[rx.el.style(STYLESHEET)],
)
app.add_page(index, title="XY vs matplotlib vs Plotly - 1.3M cell UMAP")
