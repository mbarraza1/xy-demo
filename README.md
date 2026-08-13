# Plotting 500 million points three ways

A benchmark of [XY](https://github.com/reflex-dev/xy) against matplotlib and Plotly,
scaling a real single-cell RNA-seq UMAP up to half a billion points. Ends in a Reflex
page that shows the surviving renderings live and reports every measurement.

No number on the page is typed by hand — the page reads `results/report_data.json`,
which the scripts produce. Failures are recorded as results, not omitted.

## What the points are

There are only **1,306,127 cells** in the 10x Genomics 1.3M mouse brain dataset, so a
500-million-point plot cannot be a UMAP of cells. The large point clouds are that real
embedding **replicated with Gaussian jitter (σ = 0.06)**. The structure is real; the
individual points are manufactured. Every library receives the identical array, so the
rendering comparison is unaffected — but no biological claim should be read off the
hero figure.

The embedding underneath is genuine: a real `umap-learn` run on real PCA coordinates
from the real count matrix (2.62 billion non-zeros, streamed in cell-major chunks).

## Headline results

**Browser** — does the exported file actually paint?

| points | 10M | 25M | 50M | 100M | 500M |
|---|---|---|---|---|---|
| XY paint time | 114 ms | 74 ms | 60 ms | 61 ms | **74 ms** |
| XY JS heap | 10.6 MB | 10.6 MB | 10.6 MB | 10.6 MB | **10.6 MB** |
| Plotly | 15,594 ms / 3.1 GB | failed to load | loaded, never drew | loaded, never drew | OOM |

XY's paint time and heap are **flat** from 10M to 500M. Plotly's ceiling on this
machine is between 10M and 25M, and above it the failure is *silent*: the load event
fires, then nothing is ever drawn — no canvas, no console error, no crash.

**Export**

| points | 10M | 25M | 50M | 100M | 250M | 500M |
|---|---|---|---|---|---|---|
| XY file | 2 MB | 2 MB | 2 MB | 2 MB | 2 MB | **2 MB** |
| Plotly file | 173 MB | 426 MB | 847 MB | 1,689 MB | 4,216 MB | out of memory |
| XY PNG | 0.04 s | 0.06 s | 0.10 s | 0.22 s | 1.00 s | **1.96 s** |
| matplotlib PNG | 20.0 s | 50.1 s | 101.0 s | 218.4 s | 516.8 s | halted |
| XY peak RSS | 0.5 GB | 1.1 GB | 2.0 GB | 3.9 GB | 9.4 GB | 18.7 GB |

Above roughly 2 million points XY stops shipping per-point geometry and sends a
screen-bounded density surface, so its payload is set by the size of the viewport
rather than the size of the data. That is why the file size row is constant.

**The matplotlib 500M run was halted by hand**, not observed to fail: it was stopped
after 7 minutes at 7.4 GB RSS with system swap at 13.8 GB of 15.4 GB. Extrapolating
its own linear trend from 250M puts it near 17 minutes and ~50 GB, past what this
36 GB machine has. It is reported as `stopped_by_operator`.

## Pipeline

Raw counts to embedding in **11.9 minutes**:

| Stage | Time |
|---|---|
| Stream 2.62B non-zeros, select 1,000 HVGs, z-score | 153.5 s |
| PCA to 50 components (streamed gram matrix) | 9.3 s |
| MiniBatchKMeans, 24 clusters | 5.2 s |
| UMAP, 15 neighbours, 200 epochs | 528.7 s |

## Reproducing

```bash
python3 -m venv .venv
.venv/bin/pip install "xy[reflex]" scanpy umap-learn matplotlib plotly \
                      playwright h5py pillow psutil
.venv/bin/python -m playwright install chromium

# 4.2 GB download
curl -L -o data/1M_neurons_filtered_gene_bc_matrices_h5.h5 \
  https://cf.10xgenomics.com/samples/cell-exp/1.3.0/1M_neurons/1M_neurons_filtered_gene_bc_matrices_h5.h5

.venv/bin/python scripts/01_preprocess.py     # ~2.5 min
.venv/bin/python scripts/02_pca_umap.py       # ~9 min
.venv/bin/python scripts/03_benchmark.py      # 10k-1.3M sweep
for r in 1 2 3; do
  .venv/bin/python scripts/04_interaction.py --out results/interaction_run$r.json
done
.venv/bin/python scripts/09_bigsweep.py       # 10M-500M sweep, ~45 min, resumable
.venv/bin/python scripts/10_biginteraction.py # where each export stops painting
.venv/bin/python scripts/05_aggregate.py      # -> report_data.json
.venv/bin/python scripts/06_fidelity.py --source synthetic --n 100000000 \
    --raster app/assets/matplotlib_big.png
.venv/bin/python scripts/11_assets.py         # stage what the page serves

cd app && ../.venv/bin/reflex run             # http://localhost:3000
```

**Memory warning.** `09_bigsweep.py` pushes matplotlib and Plotly until they fail. On a
36 GB machine the 250M matplotlib case peaks at 25.8 GB and the 500M case will exhaust
swap. It is resumable — completed cases are cached in `results/bigsweep.json` — so it
is safe to stop it and restart. Reduce `SIZES` in that script if you have less RAM.

## How the comparison is kept fair

- Identical inputs: the same arrays, the same validated blue ramp, the same 900×700
  canvas, the same marker size and opacity.
- Every case runs in a **fresh subprocess**, so peak RSS and import cost are isolated.
- Both interactive exports are embedded the same way — each library's own standalone
  HTML file in an iframe — so neither is helped by the embedding mechanism.
- `scale=1` is forced on XY's PNG export; it defaults to a 2× device-pixel-ratio, which
  would have quadrupled the pixel count against matplotlib's.
- Browser results come from real headless Chromium on the GPU (ANGLE Metal, M3 Pro).
  Both libraries draw with WebGL, so the backend applies equally.

## Honest caveats

- **The 500M point cloud is synthetic.** See "What the points are" above.
- **Steady-state smoothness is a tie** where both libraries work. At 1.3M points both
  held ~9 ms p95 frame times through scripted pans and zooms. XY's advantage is in
  getting to the plot and in not falling over, not in frames once you are there.
- **Python-side construction is a wash** — none of the three render at construction
  time, so all are sub-second even at 500M.
- **XY's density surface is an aggregate**, visibly smoother than an exact-point plot.
  That is the correct trade at this scale, but it is a trade.
- **The exported file has no drill-down.** This is the biggest asterisk on the 2 MB
  headline. A standalone XY export carries a 512×384 density grid plus a deterministic
  sample of ~8,200 points — the same budget at 10M points as at 500M — and nothing
  else. Zoom past the grid's resolution and it re-bins from that sample (XY labels this
  `zoom re-binned from sample` in the corner), which looks like a nearly empty plot;
  measured in Chromium, zero further network requests are made, because there is no
  Python process to make them to. Resolving back to exact rows requires a **live
  kernel** — a notebook widget or a framework adapter with a running backend. The file
  is small precisely because it does not contain the data.
- **matplotlib is still right for a paper figure.** It only loses here because the axis
  is time and scale.
- **XY is alpha** (0.0.6). Pre-1.0, the Reflex adapter is experimental, and the ~2M
  density threshold driving most of this is documented as policy, not API. Pin it.
- Single machine, single GPU. These numbers are not a general law.

## Layout

```
scripts/01_preprocess.py     stream 2.62B nnz -> 1.3M x 1000 z-scored matrix
scripts/02_pca_umap.py       PCA -> k-means -> UMAP
scripts/bench_one.py         one (library, n) case at 10k-1.3M
scripts/03_benchmark.py      small-scale sweep orchestrator
scripts/04_interaction.py    Chromium: load time, frame times, JS heap
scripts/bench_big.py         one (library, n) case at 10M-500M
scripts/09_bigsweep.py       big sweep orchestrator (resumable)
scripts/10_biginteraction.py where each export stops painting
scripts/05_aggregate.py      medians + merge -> results/report_data.json
scripts/06_fidelity.py       zoom-fidelity figures
scripts/11_assets.py         stage the artifacts the page serves
scripts/07_screenshot.py     screenshot the running page
app/                         Reflex comparison page
```
