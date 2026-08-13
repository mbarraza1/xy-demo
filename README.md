# 250 million points, three ways

A benchmark of [XY](https://github.com/reflex-dev/xy) against Plotly and matplotlib,
rendering a single-cell RNA-seq UMAP scaled to 250 million points. Ends in a Reflex
page with the live chart, the timings, and a short summary.

Every figure on the page is read from `results/report_data.json`, which the scripts
produce. Failures are recorded as results, not omitted.

## Results at 250M points

| | XY | Plotly | matplotlib |
|---|---|---|---|
| Build the figure in Python | 0.02 s | 1.44 s | 5.84 s |
| Write the output file | **1.46 s** | 26.95 s | 8.6 min |
| Size of that file | **1.9 MB** | 4,216 MB | 0.3 MB (PNG) |
| Open it in a browser | **118 ms** | **fails to load** | n/a |
| Peak memory while building | 9.4 GB | 12.7 GB | 25.8 GB |

Plotly writes a 4.2 GB document that a browser will not load. Measured across the
range, its ceiling sits between 10M and 25M points, and above it the failure is
*silent* — the load event fires and nothing is ever drawn.

XY's file is **1.9 MB at 10M points and 1.9 MB at 500M**: above ~2M points it sends a
screen-bounded density surface instead of per-point geometry, so the payload stops
tracking the data. The trade is that the exported file carries the surface, not the
rows — deep zoom falls back to an ~8,200-point sample.

## The data

The 250M point cloud is the real 10x Genomics **1.3 million mouse brain cell** dataset
(E18) tiled with Gaussian jitter. **The structure is real; the individual points are
manufactured** — there are only 1,306,127 cells, so a 250-million-point plot cannot be
a UMAP of cells. Every library received the identical arrays.

The embedding underneath is genuine: streamed from the raw count matrix (1,306,127 ×
27,998 with 2.62 billion non-zeros), then PCA → k-means → `umap-learn`, 11.9 minutes
end to end.

## Reproducing

```bash
python3 -m venv .venv
.venv/bin/pip install "xy[reflex]" scanpy umap-learn matplotlib plotly \
                      playwright h5py pillow psutil
.venv/bin/python -m playwright install chromium

curl -L -o data/1M_neurons_filtered_gene_bc_matrices_h5.h5 \
  https://cf.10xgenomics.com/samples/cell-exp/1.3.0/1M_neurons/1M_neurons_filtered_gene_bc_matrices_h5.h5

.venv/bin/python scripts/01_preprocess.py     # stream 2.62B nnz  (~2.5 min)
.venv/bin/python scripts/02_pca_umap.py       # PCA -> UMAP       (~9 min)
.venv/bin/python scripts/09_bigsweep.py       # 10M-500M sweep, resumable
.venv/bin/python scripts/10_biginteraction.py # where each export stops painting
.venv/bin/python scripts/05_aggregate.py      # -> report_data.json
.venv/bin/python scripts/11_assets.py         # stage what the page serves

cd app && ../.venv/bin/reflex run             # http://localhost:3000
```

**Memory warning.** `09_bigsweep.py` pushes matplotlib and Plotly until they fail. On a
36 GB machine the 250M matplotlib case peaks at 25.8 GB and the 500M case exhausts
swap. It caches completed cases in `results/bigsweep.json`, so it is safe to stop and
restart. Reduce `SIZES` if you have less RAM.

## Fairness and caveats

- Identical inputs: same arrays, same colour ramp, same 900×700 canvas, same marker
  size and opacity. Every case runs in a fresh subprocess so peak RSS is isolated.
- `scale=1` is forced on XY's PNG export; it defaults to a 2× device-pixel-ratio.
- Browser numbers come from real headless Chromium on the GPU (ANGLE Metal, M3 Pro).
  Both XY and Plotly draw with WebGL, so the backend applies equally.
- **The exported file has no drill-down.** It carries a density grid plus an ~8,200
  point sample — the same budget at 10M as at 500M. Resolving individual rows needs a
  live backend (`@rxy.data`), which was measured working at 10M but costs 16 bytes per
  point resident and adds a ~0.5 s round trip per zoom, rising to 0.9–1.7 s at 250M.
  The page embeds the export because that is the version that is actually fast.
- **matplotlib is still right for a paper figure** — it only loses here on time.
- **XY is alpha** (0.0.6); the ~2M density threshold is documented as policy, not API.
- Single machine, single GPU. Not a general law.

## Layout

```
scripts/01_preprocess.py     stream 2.62B nnz -> 1.3M x 1000 z-scored matrix
scripts/02_pca_umap.py       PCA -> k-means -> UMAP
scripts/bench_big.py         one (library, n) case at 10M-500M
scripts/09_bigsweep.py       sweep orchestrator (resumable)
scripts/10_biginteraction.py where each export stops painting in a browser
scripts/05_aggregate.py      merge -> results/report_data.json
scripts/11_assets.py         stage the artifacts the page serves
app/                         the Reflex page
```

Earlier revisions carried a much larger page (size sweeps, fidelity comparisons, code
listings, a live state-backed chart). That history is in git; `scripts/03`, `04`, `06`
and `07` still produce those measurements.
