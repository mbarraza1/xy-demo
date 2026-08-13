"""Stage the artifacts the Reflex page serves, choosing them from the measurements.

Which Plotly file gets embedded is not a judgement call - it is whichever one the
browser actually painted, as recorded by 10_biginteraction.py.
"""

from __future__ import annotations

import json
import os
import shutil

BIG = "results/big"
ART = "results/artifacts"
ASSETS = "app/assets"


def load(path, default):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def copy(src: str, dst: str) -> bool:
    if not os.path.exists(src):
        print(f"  MISSING {src}")
        return False
    shutil.copy2(src, os.path.join(ASSETS, dst))
    size = os.path.getsize(src) / 1e6
    print(f"  {dst:32} <- {os.path.basename(src)}  ({size:,.1f} MB)")
    return True


def main() -> None:
    os.makedirs(ASSETS, exist_ok=True)
    sweep = load("results/bigsweep.json", [])
    inter = load("results/biginteraction.json", [])

    # --- XY: the 500M export and its raster ---
    copy(f"{BIG}/xy_500000000_synthetic.html", "xy_500M.html")
    copy(f"{BIG}/xy_500000000_synthetic.png", "xy_big.png")

    # --- matplotlib: the largest raster actually produced ---
    mpl = sorted((r for r in sweep
                  if r["lib"] == "matplotlib" and r.get("status") == "ok"),
                 key=lambda r: r["n"])
    if mpl:
        n = mpl[-1]["n"]
        if not copy(f"{BIG}/matplotlib_{n}_synthetic.png", "matplotlib_big.png"):
            for r in reversed(mpl[:-1]):
                if copy(f"{BIG}/matplotlib_{r['n']}_synthetic.png",
                        "matplotlib_big.png"):
                    break

    # --- Plotly: the largest export that actually painted a canvas ---
    rendered = sorted((r for r in inter
                       if r["lib"] == "plotly" and r.get("rendered")),
                      key=lambda r: r["n"])
    if rendered:
        best = rendered[-1]
        copy(f"{BIG}/{best['file']}", "plotly_best.html")
        print(f"  -> embedding Plotly at {best['n']:,} points "
              f"(largest that rendered)")
    else:
        print("  no Plotly artifact rendered; page will omit the live frame")

    # --- fidelity panels + the data the page reads ---
    copy(f"{ART}/fidelity_matplotlib_zoom.png", "fidelity_matplotlib_zoom.png")
    copy(f"{ART}/fidelity_xy_zoom.png", "fidelity_xy_zoom.png")
    copy("results/report_data.json", "report_data.json")


if __name__ == "__main__":
    main()
