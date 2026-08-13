"""Sweep all three libraries from 10M to 500M points, one subprocess per case.

Failure is expected at the top of this range and is recorded as a result:
a library that cannot produce the figure at all is the most important finding
the sweep can return.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

SIZES = [10_000_000, 25_000_000, 50_000_000, 100_000_000, 250_000_000, 500_000_000]
LIBS = ["xy", "plotly", "matplotlib"]
TIMEOUT_S = 3_600
OUT = "results/bigsweep.json"


def run(lib: str, n: int, keep: bool) -> dict:
    cmd = [sys.executable, "scripts/bench_big.py", "--lib", lib, "--n", str(n)]
    if keep:
        cmd.append("--keep")
    t0 = time.perf_counter()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        return {"lib": lib, "n": n, "status": "timeout",
                "error": f"exceeded {TIMEOUT_S}s", "wall_s": TIMEOUT_S}
    wall = time.perf_counter() - t0
    if proc.returncode != 0:
        tail = (proc.stderr or "").strip().splitlines()
        killed = proc.returncode < 0 or "MemoryError" in (proc.stderr or "")
        return {"lib": lib, "n": n, "wall_s": wall,
                "status": "oom_or_killed" if killed else "crash",
                "returncode": proc.returncode,
                "error": " | ".join(tail[-3:])[:300]}
    try:
        rec = json.loads(proc.stdout.strip().splitlines()[-1])
    except Exception:
        return {"lib": lib, "n": n, "status": "badoutput", "wall_s": wall,
                "error": (proc.stdout or "")[-200:]}
    rec["wall_s"] = wall
    return rec


def main() -> None:
    # Resume: successful cases from a previous run are expensive (matplotlib at
    # 100M alone is 3.6 minutes) and deterministic, so keep them.
    try:
        prior = json.load(open(OUT))
    except (FileNotFoundError, json.JSONDecodeError):
        prior = []
    done = {(r["lib"], r["n"]): r for r in prior if r.get("status") == "ok"}
    if done:
        print(f"resuming: {len(done)} case(s) already complete", flush=True)

    results = []
    for n in SIZES:
        for lib in LIBS:
            if (lib, n) in done:
                results.append(done[(lib, n)])
                print(f"  {lib:11} n={n:>12,}  (cached)", flush=True)
                continue
            keep = (n == 500_000_000 and lib in ("xy", "plotly"))
            rec = run(lib, n, keep)
            results.append(rec)
            if rec.get("status") != "ok":
                print(f"  {lib:11} n={n:>12,}  {rec['status'].upper()}: "
                      f"{rec.get('error','')[:100]}", flush=True)
            else:
                bits = [f"build {rec.get('t_build',0):7.2f}s"]
                if rec.get("t_export_html") is not None:
                    bits.append(f"html {rec['t_export_html']:7.2f}s / "
                                f"{rec['bytes_html']/1e6:9.1f}MB")
                if rec.get("t_export_png") is not None:
                    bits.append(f"png {rec['t_export_png']:8.2f}s")
                bits.append(f"peakRSS {rec.get('peak_rss_gb',0):5.1f}GB")
                print(f"  {lib:11} n={n:>12,}  " + "  ".join(bits), flush=True)
            with open(OUT, "w") as fh:
                json.dump(results, fh, indent=2)
        print("", flush=True)
    print(f"wrote {OUT}", flush=True)


if __name__ == "__main__":
    main()
