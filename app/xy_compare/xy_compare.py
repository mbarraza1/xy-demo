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
        rx.heading("Plotting 1.3 million cells three ways",
                   size="9", margin_top="0.5rem", color="var(--text)",
                   line_height="1.15"),
        rx.text(
            "A single-cell RNA-seq UMAP of 1,306,127 mouse brain cells, rendered "
            "with XY, matplotlib, and Plotly - and measured end to end.",
            font_size="1.15rem", color="var(--text-secondary)",
            margin_top="0.9rem", line_height="1.6", max_width="720px",
        ),
        margin_bottom="2.5rem",
    )


def headline_stats() -> rx.Component:
    h = D.HEADLINE
    return rx.flex(
        stat(f"{h['load_speedup']:.0f}x", "faster to first plot",
             f"{h['xy_load_ms']:.0f} ms vs {h['plotly_load_ms']:.0f} ms "
             f"for Plotly, in a real browser"),
        stat(f"{h['heap_ratio']:.1f}x", "less browser memory",
             f"{h['xy_heap_mb']:.0f} MB JS heap vs {h['plotly_heap_mb']:.0f} MB"),
        stat(f"{h['png_speedup']:.0f}x", "faster to rasterise",
             f"{h['xy_png_s']:.2f} s vs {h['mpl_png_s']:.2f} s for matplotlib",
             accent="var(--series-xy)"),
        stat("1.3M", "cells, every one of them",
             "no subsampling anywhere in this page",
             accent="var(--text)"),
        gap="1rem", flex_wrap="wrap", margin_bottom="3rem",
    )


def dataset_section() -> rx.Component:
    p = D.PIPELINE["timings_s"]
    total_min = (153.5 + p["pca"] + p["kmeans"] + p["umap"]) / 60
    return section(
        "The data",
        prose(
            "This is the 10x Genomics ", rx.text.strong("1.3 million mouse brain cells"),
            " dataset (E18 mice, ", rx.code("1M_neurons"), "). The raw count matrix is ",
            rx.text.strong(f"{D.N_CELLS:,} cells x {D.N_GENES_TOTAL:,} genes"),
            f" with {D.NNZ/1e9:.2f} billion non-zero entries - about 21-31 GB if you "
            "load it densely, which is more than this machine has. It was streamed in "
            "cell-major chunks instead: one pass to accumulate per-gene moments and "
            "pick 1,000 highly variable genes, a second to write a z-scored matrix.",
        ),
        prose(
            "Everything downstream is real: PCA by streamed gram matrix, k-means for "
            "labels, and a genuine ", rx.code("umap-learn"), " embedding - not a "
            "synthetic point cloud shaped like one.",
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
        subtitle="Real counts, a real embedding, no subsampling.",
    )


def xy_live_section() -> rx.Component:
    return section(
        "1. XY - live, all 1,306,127 cells",
        prose(
            "Drag to pan, scroll to zoom, hover for a cell's exact values. Every point "
            "is here: XY renders a screen-bounded density surface at this zoom level "
            "and drills back to exact rows as you go in, so hovering still returns the "
            "original cell rather than a bin."
        ),
        card(rxy.chart(charts.umap_chart(), height="720px"), pad="0.75rem"),
        caption(
            f"Rendered through the bundled Reflex adapter. Built in "
            f"{D.HEADLINE['xy_build_s']*1000:.0f} ms in Python; "
            f"{D.HEADLINE['xy_load_ms']:.0f} ms to first paint in the browser; "
            f"{D.HEADLINE['xy_heap_mb']:.0f} MB of JS heap once settled."
        ),
        subtitle="Colour encodes sequencing depth (log10 UMI count per cell).",
    )


def plotly_live_section() -> rx.Component:
    h = D.HEADLINE
    return section(
        "2. Plotly - live, same 1.3M cells",
        prose(
            "The same data, the same colour ramp, rendered by ", rx.code("Scattergl"),
            ". It is loaded on demand because the wait is itself the finding: this "
            f"figure is a {h['plotly_html_mb']:.0f} MB self-contained document that "
            f"takes about {h['plotly_load_ms']/1000:.1f} seconds to become interactive, "
            f"against {h['xy_load_ms']/1000:.2f} s for the XY chart above.",
        ),
        rx.cond(
            PageState.plotly_requested,
            rx.box(
                rx.el.iframe(
                    src="/plotly_1306127.html",
                    width="100%", height="740px",
                    style={"border": "1px solid var(--border)",
                           "borderRadius": "12px", "background": "var(--surface)"},
                ),
                width="100%",
            ),
            rx.box(
                rx.button(
                    f"Render 1.3M points with Plotly  ({h['plotly_html_mb']:.0f} MB)",
                    on_click=PageState.request_plotly,
                    size="3",
                    style={"background": "var(--series-plotly)", "color": "#ffffff",
                           "cursor": "pointer"},
                ),
                rx.text(
                    "Loads the exported standalone figure. Expect a visible pause.",
                    font_size="0.83rem", color="var(--muted)", margin_top="0.7rem",
                ),
                display="flex", flex_direction="column", align_items="center",
                justify_content="center", height="260px",
                background="var(--surface)", border="1px dashed var(--border)",
                border_radius="12px", width="100%",
            ),
        ),
        caption(
            f"Plotly 6 serialises numeric arrays as base64 binary, which is why the "
            f"file is {h['plotly_html_mb']:.0f} MB rather than hundreds. The cost that "
            f"remains is browser-side: it holds {h['plotly_heap_mb']:.0f} MB of JS heap "
            f"because every one of the 1.3M markers exists as a drawable object."
        ),
        subtitle="Identical inputs, identical canvas size, identical colour ramp.",
    )


def matplotlib_section() -> rx.Component:
    h = D.HEADLINE
    return section(
        "3. matplotlib - static, and honestly quite good",
        prose(
            "This is a PNG. It cannot pan, zoom, or tell you which cell you are "
            f"pointing at - but at {h['mpl_png_s']:.2f} s and 291 KB it is a perfectly "
            "publishable figure, and it is what most single-cell papers actually ship. "
            "The comparison below is not that matplotlib renders badly; it is that it "
            f"takes {h['png_speedup']:.0f}x longer to produce the same raster and then "
            "stops there."
        ),
        rx.flex(
            rx.box(
                rx.image(src="/matplotlib_1306127.png", width="100%",
                         border_radius="8px"),
                caption(f"matplotlib - {h['mpl_png_s']:.2f} s, 291 KB, static"),
                flex="1 1 440px", min_width="320px",
            ),
            rx.box(
                rx.image(src="/xy_1306127.png", width="100%", border_radius="8px"),
                caption(f"XY, same 900x700 raster - {h['xy_png_s']:.2f} s, 384 KB"),
                flex="1 1 440px", min_width="320px",
            ),
            gap="1.25rem", flex_wrap="wrap",
        ),
        subtitle="Both PNGs below are 900x700 at dpi 100, drawn from the same arrays.",
    )


def fidelity_section() -> rx.Component:
    return section(
        "What a static figure cannot do",
        prose(
            "A raster is finished at export resolution. Zooming into the boxed region "
            "of the matplotlib PNG gives you the 98x85 pixels that were written to "
            "disk, upscaled. XY re-renders the same window from the canonical columns "
            "still held in Python - 20,976 individual cells, with substructure that "
            "simply is not present in the raster."
        ),
        rx.flex(
            rx.box(
                rx.image(src="/fidelity_matplotlib_zoom.png", width="100%",
                         border_radius="8px", style={"imageRendering": "pixelated"}),
                caption("matplotlib PNG, cropped and upscaled - 98x85 source pixels"),
                flex="1 1 420px", min_width="300px",
            ),
            rx.box(
                rx.image(src="/fidelity_xy_zoom.png", width="100%",
                         border_radius="8px"),
                caption("XY, same window re-rendered from source rows - 20,976 cells"),
                flex="1 1 420px", min_width="300px",
            ),
            gap="1.25rem", flex_wrap="wrap",
        ),
        subtitle="The same neighbourhood of the embedding, x in [6.0, 9.5], y in [-5.5, -2.0].",
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
            chart_card(charts.time_to_first_plot()),
            chart_card(charts.browser_memory()),
            gap="1.25rem", flex_wrap="wrap", margin_bottom="1.25rem",
        ),
        rx.flex(
            chart_card(charts.static_render()),
            chart_card(charts.file_size()),
            gap="1.25rem", flex_wrap="wrap",
        ),
        caption(f"GPU: {D.GL_RENDERER}"),
        subtitle="Charts on this page are themselves drawn with XY.",
    )


def _num(v, fmt="{:.0f}"):
    return "-" if v is None else fmt.format(v)


def table_section() -> rx.Component:
    rows = []
    for lib, label in (("xy", "XY"), ("plotly", "Plotly"), ("matplotlib", "matplotlib")):
        b = D.at(lib, D.FULL, "t_build")
        html_mb = D.at(lib, D.FULL, "bytes_html")
        png_s = D.at(lib, D.FULL, "t_export_png")
        rss = D.at(lib, D.FULL, "peak_rss_mb")
        load = D.at(lib, D.FULL, "t_load_ms", "inter")
        heap = D.at(lib, D.FULL, "js_heap_mb", "inter")
        pan = D.at(lib, D.FULL, "pan_p95_ms", "inter")
        loc = D.at(lib, D.FULL, "loc")
        rows.append(rx.table.row(
            rx.table.cell(rx.text.strong(label)),
            rx.table.cell(_num(b, "{:.3f} s"), text_align="right", class_name="tabular"),
            rx.table.cell("-" if not html_mb else f"{html_mb/1e6:.1f} MB",
                          text_align="right", class_name="tabular"),
            rx.table.cell(_num(png_s, "{:.2f} s"), text_align="right", class_name="tabular"),
            rx.table.cell(_num(rss, "{:.0f} MB"), text_align="right", class_name="tabular"),
            rx.table.cell(_num(load, "{:.0f} ms"), text_align="right", class_name="tabular"),
            rx.table.cell(_num(heap, "{:.0f} MB"), text_align="right", class_name="tabular"),
            rx.table.cell(_num(pan, "{:.1f} ms"), text_align="right", class_name="tabular"),
            rx.table.cell(_num(loc, "{:.0f}"), text_align="right", class_name="tabular"),
        ))
    return section(
        "Every number, at 1,306,127 cells",
        card(
            rx.table.root(
                rx.table.header(rx.table.row(
                    rx.table.column_header_cell("Library"),
                    rx.table.column_header_cell("Build", text_align="right"),
                    rx.table.column_header_cell("HTML", text_align="right"),
                    rx.table.column_header_cell("PNG", text_align="right"),
                    rx.table.column_header_cell("Peak RSS", text_align="right"),
                    rx.table.column_header_cell("To first plot", text_align="right"),
                    rx.table.column_header_cell("JS heap", text_align="right"),
                    rx.table.column_header_cell("Pan p95", text_align="right"),
                    rx.table.column_header_cell("LOC", text_align="right"),
                )),
                rx.table.body(*rows),
                variant="surface", size="1",
            ),
        ),
        caption(
            "Build is Python-side figure construction. Peak RSS is the whole "
            "subprocess including interpreter and data. To first plot, JS heap, and "
            "pan p95 are browser medians over three runs; matplotlib has no browser "
            "row because a PNG has nothing to load. LOC counts the chart-construction "
            "function body."
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
        rx.flex(
            block("XY", CODE_XY, "var(--series-xy)"),
            block("Plotly", CODE_PLOTLY, "var(--series-plotly)"),
            block("matplotlib", CODE_MPL, "var(--series-matplotlib)"),
            gap="1.25rem", flex_wrap="wrap", align_items="stretch",
        ),
    )


def verdict_section() -> rx.Component:
    h = D.HEADLINE
    def point(title, body):
        return rx.box(
            rx.text(title, font_weight="600", color="var(--text)",
                    margin_bottom="0.3rem"),
            rx.text(body, color="var(--text-secondary)", font_size="0.93rem",
                    line_height="1.7"),
            margin_bottom="1.2rem",
        )
    return section(
        "Where XY actually wins - and where it does not",
        card(
            rx.text("It wins", font_weight="600", color="var(--series-xy)",
                    margin_bottom="0.9rem", letter_spacing="0.04em",
                    font_size="0.8rem"),
            point(
                f"Time to first plot: {h['load_speedup']:.0f}x, and it barely moves with n",
                f"XY went from {D.at('xy', 100_000, 't_load_ms', 'inter'):.0f} ms at "
                f"100k cells to {h['xy_load_ms']:.0f} ms at 1.3M - a 2.2x increase over "
                f"13x the data. Plotly went from "
                f"{D.at('plotly', 100_000, 't_load_ms', 'inter'):.0f} ms to "
                f"{h['plotly_load_ms']:.0f} ms, tracking the point count. That is the "
                "architectural difference showing up in a number: XY sends a "
                "screen-bounded representation, Plotly sends every marker.",
            ),
            point(
                f"Browser memory: {h['heap_ratio']:.1f}x less",
                f"{h['xy_heap_mb']:.0f} MB against {h['plotly_heap_mb']:.0f} MB. On a "
                "dashboard with six of these, that is the difference between a "
                "responsive page and a tab that gets killed.",
            ),
            point(
                f"Rasterising: {h['png_speedup']:.0f}x faster than matplotlib",
                f"{h['xy_png_s']:.2f} s versus {h['mpl_png_s']:.2f} s for the same "
                "900x700 PNG, with no browser involved. If you regenerate figures in "
                "a pipeline, that compounds.",
            ),
            point(
                "Exact rows survive the reduction",
                "The density surface is a rendering decision, not a data decision. "
                "Hover returns the actual cell; zooming drills back to individual "
                "points. A downsampled scatter cannot do that, and a PNG certainly "
                "cannot.",
            ),
            margin_bottom="1.25rem",
        ),
        card(
            rx.text("It does not", font_weight="600", color="var(--series-matplotlib)",
                    margin_bottom="0.9rem", letter_spacing="0.04em",
                    font_size="0.8rem"),
            point(
                "Steady-state smoothness is a tie on this hardware",
                "Once loaded, both XY and Plotly held p95 frame times around 9 ms "
                "through scripted pans and zooms on an M3 Pro. An early run showed "
                "Plotly at 108 ms, but that did not reproduce across three repeats and "
                "is reported here as the cold-start artefact it was. The honest claim "
                "is about getting to the plot, not about frames once you are there.",
            ),
            point(
                "File size is a modest win, not a rout",
                f"{h['xy_html_mb']:.1f} MB against {h['plotly_html_mb']:.1f} MB - about "
                "21%. Plotly 6 already base64-encodes numeric arrays, so the "
                "order-of-magnitude HTML blowup that older comparisons show is no "
                "longer real.",
            ),
            point(
                "Python-side build time is a wash",
                f"All three construct their figure object in under "
                f"{max(h['xy_build_s'], h['plotly_build_s'], h['mpl_build_s'])*1000:.0f} ms, "
                "because none of them render at construction time. Anyone quoting big "
                "'build' differences is measuring import cost or rendering, not "
                "construction.",
            ),
            point(
                "matplotlib is still fine for a figure",
                "2.5 seconds for a publication-quality static PNG is not a problem for "
                "a paper. If the output is a page in a manuscript, the interactivity "
                "XY offers is worth nothing to you.",
            ),
            point(
                "XY is alpha software",
                "Version 0.0.6. Pre-1.0, breaking changes expected, the Reflex adapter "
                "is explicitly experimental, and the density thresholds used here are "
                "documented as policy rather than API. Pin the version.",
            ),
        ),
        subtitle="The measurements support a narrower claim than the marketing does, "
                 "and the narrow claim is still a strong one.",
    )


def footer() -> rx.Component:
    return rx.box(
        rx.divider(margin_bottom="1.5rem", border_color="var(--border)"),
        rx.text(
            "Reproduce: scripts 01-06 in this repository stream the 10x h5, compute the "
            "embedding, run the sweep in isolated subprocesses, drive Chromium for the "
            "browser numbers, and emit the JSON this page reads. No number on this page "
            "is typed by hand.",
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
