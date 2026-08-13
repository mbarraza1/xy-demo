"""Merge the three interaction repeats into medians and emit the report dataset."""

from __future__ import annotations

import json
import re
import statistics

RUNS = [f"results/interaction_run{i}.json" for i in (1, 2, 3)]
OUT = "results/report_data.json"


def med(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), 1) if vals else None


def main() -> None:
    per_file: dict[str, list[dict]] = {}
    for path in RUNS:
        for rec in json.load(open(path)):
            per_file.setdefault(rec["file"], []).append(rec)

    interaction = []
    for fname, recs in sorted(per_file.items()):
        ok = [r for r in recs if r.get("status") == "ok"]
        if not ok:
            interaction.append({"file": fname, "status": recs[0].get("status")})
            continue
        lib, n = re.match(r"(\w+?)_(\d+)\.html", fname).groups()
        interaction.append({
            "file": fname, "lib": lib, "n": int(n), "status": "ok",
            "repeats": len(ok),
            "t_load_ms": med([r.get("t_load_ms") for r in ok]),
            "t_quiet_ms": med([r.get("t_quiet_ms") for r in ok]),
            "pan_p95_ms": med([r.get("pan", {}).get("p95_frame_ms") for r in ok]),
            "pan_fps": med([r.get("pan", {}).get("fps") for r in ok]),
            "zoom_p95_ms": med([r.get("zoom", {}).get("p95_frame_ms") for r in ok]),
            "js_heap_mb": med([r.get("js_heap_mb") for r in ok]),
            "gl_renderer": ok[0].get("gl_renderer"),
        })

    bench = json.load(open("results/benchmark.json"))
    pipeline = json.load(open("results/pipeline_timings.json"))

    report = {"benchmark": bench, "interaction": interaction, "pipeline": pipeline}
    with open(OUT, "w") as fh:
        json.dump(report, fh, indent=2)

    print(f"{'file':26} {'load ms':>8} {'quiet ms':>9} {'pan p95':>8} "
          f"{'zoom p95':>9} {'heap MB':>8}")
    for r in sorted(interaction, key=lambda r: (r.get("lib", ""), r.get("n", 0))):
        if r.get("status") != "ok":
            print(f"{r['file']:26} {r.get('status')}")
            continue
        print(f"{r['file']:26} {r['t_load_ms']:>8} {r['t_quiet_ms']:>9} "
              f"{r['pan_p95_ms']:>8} {r['zoom_p95_ms']:>9} {r['js_heap_mb']:>8}")
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
