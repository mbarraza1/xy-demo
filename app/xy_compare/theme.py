"""Design tokens for the comparison page.

One palette, defined once, consumed by role. Series colours follow the entity
(library), never its rank, so XY is blue in every chart on the page.
"""

# Categorical slots 1-3 of the validated palette. Verified all-pairs in both
# modes: worst CVD dE 9.2, worst normal-vision dE 24.0.
SERIES = {
    "xy":         {"light": "#2a78d6", "dark": "#3987e5"},
    "matplotlib": {"light": "#eb6834", "dark": "#d95926"},
    "plotly":     {"light": "#1baf7a", "dark": "#199e70"},
}

# Sequential blue ramp, light -> dark, used by every UMAP rendering.
BLUE_RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
             "#256abf", "#184f95", "#0d366b"]

LIGHT = {
    "surface": "#fcfcfb",
    "page": "#f9f9f7",
    "text": "#0b0b0b",
    "text_secondary": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "border": "rgba(11,11,11,0.10)",
}

DARK = {
    "surface": "#1a1a19",
    "page": "#0d0d0d",
    "text": "#ffffff",
    "text_secondary": "#c3c2b7",
    "muted": "#898781",
    "grid": "#2c2c2a",
    "axis": "#383835",
    "border": "rgba(255,255,255,0.10)",
}

# Roles resolved as CSS custom properties so light/dark swap in one place.
STYLESHEET = """
:root {
  color-scheme: light;
  --surface: %(l_surface)s;
  --page: %(l_page)s;
  --text: %(l_text)s;
  --text-secondary: %(l_text_secondary)s;
  --muted: %(l_muted)s;
  --grid: %(l_grid)s;
  --axis: %(l_axis)s;
  --border: %(l_border)s;
  --series-xy: %(l_xy)s;
  --series-matplotlib: %(l_matplotlib)s;
  --series-plotly: %(l_plotly)s;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --surface: %(d_surface)s;
    --page: %(d_page)s;
    --text: %(d_text)s;
    --text-secondary: %(d_text_secondary)s;
    --muted: %(d_muted)s;
    --grid: %(d_grid)s;
    --axis: %(d_axis)s;
    --border: %(d_border)s;
    --series-xy: %(d_xy)s;
    --series-matplotlib: %(d_matplotlib)s;
    --series-plotly: %(d_plotly)s;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --surface: %(d_surface)s;
  --page: %(d_page)s;
  --text: %(d_text)s;
  --text-secondary: %(d_text_secondary)s;
  --muted: %(d_muted)s;
  --grid: %(d_grid)s;
  --axis: %(d_axis)s;
  --border: %(d_border)s;
  --series-xy: %(d_xy)s;
  --series-matplotlib: %(d_matplotlib)s;
  --series-plotly: %(d_plotly)s;
}
body {
  background: var(--page);
  color: var(--text);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
.tabular { font-variant-numeric: tabular-nums; }
""" % {
    **{f"l_{k}": v for k, v in LIGHT.items()},
    **{f"d_{k}": v for k, v in DARK.items()},
    **{f"l_{k}": v["light"] for k, v in SERIES.items()},
    **{f"d_{k}": v["dark"] for k, v in SERIES.items()},
}
