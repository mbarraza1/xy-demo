"""Orchestrate the XY / matplotlib / plotly sweep, one subprocess per case."""

from __future__ import annotations

import json
import subprocess
import sys
import time

SIZES = [10_000, 50_000, 100_000, 250_000, 500_000, 1_000_000, 1_306_127]
LIBS = ["matplotlib", "plotly", "xy"]
TIMEOUT_S = 1_200
REPEATS_SMALL = 3          # sizes at or below this get repeated and medianed
SMALL_CUTOFF = 100_000

OUT = "results/benchmark.json"


def run_case(lib: str, n: int, save: bool) -> dict:
    cmd = [sys.executable, "scripts/bench_one.py", "--lib", lib, "--n", str(n)]
    if save:
        cmd.append("--save-artifacts")
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"lib": lib, "n": n, "status": "timeout",
                "error": f"exceeded {TIMEOUT_S}s", "wall_s": TIMEOUT_S}
    wall = time.perf_counter() - t0
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        return {"lib": lib, "n": n, "status": "crash", "wall_s": wall,
                "error": " | ".join(tail[-3:])[:400]}
    try:
        rec = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"lib": lib, "n": n, "status": "badoutput", "wall_s": wall,
                "error": (proc.stdout or "")[-300:]}
    rec["wall_s"] = wall
    return rec


def median(vals):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    m = len(vals) // 2
    return vals[m] if len(vals) % 2 else (vals[m - 1] + vals[m]) / 2


def main() -> None:
    results = []
    for n in SIZES:
        reps = REPEATS_SMALL if n <= SMALL_CUTOFF else 1
        for lib in LIBS:
            runs = []
            for r in range(reps):
                save = (n == SIZES[-1] and r == 0)   # keep only full-size artifacts
                rec = run_case(lib, n, save)
                runs.append(rec)
                status = rec.get("status")
                if status != "ok":
                    print(f"  {lib:11} n={n:>9,}  {status.upper()}: "
                          f"{rec.get('error','')[:110]}", flush=True)
                    break
            ok = [r for r in runs if r.get("status") == "ok"]
            if not ok:
                results.append(runs[-1])
                continue
            merged = dict(ok[0])
            merged["repeats"] = len(ok)
            for key in ("t_build", "t_export_html", "t_export_png", "t_import",
                        "peak_rss_mb", "peak_over_baseline_mb", "wall_s"):
                vals = [r.get(key) for r in ok if r.get(key) is not None]
                if vals:
                    merged[key] = median(vals)
            results.append(merged)
            tb = merged.get("t_build", 0)
            th = merged.get("t_export_html")
            tp = merged.get("t_export_png")
            parts = [f"build {tb:6.2f}s"]
            if th is not None:
                parts.append(f"html {th:6.2f}s / {merged['bytes_html']/1e6:7.1f}MB")
            if tp is not None:
                parts.append(f"png {tp:6.2f}s / {merged['bytes_png']/1e6:5.2f}MB")
            parts.append(f"peakRSS {merged.get('peak_rss_mb',0):6.0f}MB")
            print(f"  {lib:11} n={n:>9,}  " + "  ".join(parts), flush=True)

            with open(OUT, "w") as fh:
                json.dump(results, fh, indent=2)
        print("", flush=True)

    with open(OUT, "w") as fh:
        json.dump(results, fh, indent=2)
    print(f"wrote {OUT} ({len(results)} cases)", flush=True)


if __name__ == "__main__":
    main()
