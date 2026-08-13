"""Stage the single artifact the Reflex page serves: XY's 250M export."""

from __future__ import annotations

import json
import os
import shutil

BIG = "results/big"
ART = "results/artifacts"
ASSETS = "app/assets"
PAGE_N = 250_000_000   # the point count the page embeds


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

    # The page embeds exactly one chart: XY's 250M export. It is the only version
    # that is both interactive and fast - the state-backed live path costs 16
    # bytes/point resident and ~1 s per zoom at this size.
    if not copy(f"{BIG}/xy_{PAGE_N}_synthetic.html", "xy_250M.html"):
        print(f"  run: python scripts/bench_big.py --lib xy --n {PAGE_N} --keep")

    copy("results/report_data.json", "report_data.json")

    # Everything else the sweep produced stays in results/ and is referenced by
    # the page only as numbers, not as embedded files.
    n_sweep = sum(1 for r in sweep if r.get("status") == "ok")
    n_inter = sum(1 for r in inter if r.get("rendered"))
    print(f"  ({n_sweep} sweep cases and {n_inter} rendered browser cases "
          f"feed the page's tables from JSON)")


if __name__ == "__main__":
    main()
