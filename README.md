# Plotting 1.3 million cells three ways

A benchmark of [XY](https://github.com/reflex-dev/xy) against matplotlib and Plotly,
using a real single-cell RNA-seq UMAP of the 10x Genomics **1.3 million mouse brain
cells** dataset (E18 mice). Ends in a Reflex page that shows all three renderings
live and reports every measurement.

No number on the page is typed by hand — the page reads `results/report_data.json`,
which the scripts produce.

## Headline results, at 1,306,127 cells

| | XY | Plotly | matplotlib |
|---|---|---|---|
| Figure build (Python) | 0.017 s | 0.038 s | 0.051 s |
| Self-contained HTML | 21.3 MB | 26.9 MB | — |
| PNG rasterise | **0.05 s** | — | 2.52 s |
| Time to first plot (browser) | **157 ms** | 2,222 ms | — |
| JS heap once settled | **68 MB** | 588 MB | — |
| Pan p95 frame time | 9.0 ms | 9.1 ms | — |

XY is **14× faster to first plot**, holds **8.6× less browser memory**, and
rasterises **51× faster** than matplotlib. Steady-state pan/zoom smoothness is a
**tie** with Plotly on this hardware — see "Honest caveats" below.

## Pipeline

Raw counts to embedding in **11.9 minutes** on an M3 Pro:

| Stage | Time |
|---|---|
| Stream 2.62B non-zeros, select 1,000 HVGs, z-score | 153.5 s |
| PCA to 50 components (streamed gram matrix) | 9.3 s |
| MiniBatchKMeans, 24 clusters | 5.2 s |
| UMAP, 15 neighbours, 200 epochs | 528.7 s |

The raw matrix is 1,306,127 cells × 27,998 genes with **2.62 billion non-zeros** —
roughly 21–31 GB dense, more than this machine has. `01_preprocess.py` streams it in
cell-major chunks and never holds more than one chunk at a time.

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
.venv/bin/python scripts/03_benchmark.py      # sweep, isolated subprocesses
for r in 1 2 3; do
  .venv/bin/python scripts/04_interaction.py --out results/interaction_run$r.json
done
.venv/bin/python scripts/05_aggregate.py      # medians -> report_data.json
.venv/bin/python scripts/06_fidelity.py       # zoom comparison figures

cd app && ../.venv/bin/reflex run             # http://localhost:3000
```

## How the comparison is kept fair

- Identical inputs: same UMAP coordinates, same continuous colour values, same
  validated blue ramp, same 900×700 canvas, same marker size and opacity.
- Every benchmark case runs in a **fresh subprocess**, so peak RSS and import cost
  are isolated and no warm cache flatters the next library.
- `scale=1` is forced on XY's PNG export; it defaults to a 2× device-pixel-ratio,
  which would have quadrupled the pixel count and made the byte comparison
  meaningless.
- Both interactive exports are self-contained (`include_plotlyjs=True` for Plotly).
- Browser numbers are **medians of three runs** driving real headless Chromium on
  the GPU (ANGLE Metal, Apple M3 Pro). Both libraries draw with WebGL, so the
  backend applies equally.

## Honest caveats

- **Steady-state interaction is a tie.** Once loaded, both XY and Plotly held ~9 ms
  p95 frame times. An early run showed Plotly at 108 ms; it did not reproduce across
  three repeats and is reported as the cold-start artefact it was. XY's advantage is
  in *getting to* the plot, not in frames after you are there.
- **File size is a modest win** (21%), not the order of magnitude older comparisons
  show. Plotly 6 already base64-encodes numeric arrays.
- **Python-side build time is a wash** — none of the three render at construction
  time, so all are sub-100 ms.
- **matplotlib is still fine for a static figure.** 2.5 s for a publication-quality
  PNG is a non-problem if the output is a page in a manuscript.
- **XY is alpha** (0.0.6). Pre-1.0, breaking changes expected, the Reflex adapter is
  explicitly experimental, and the density thresholds are documented as policy
  rather than API. Pin the version.
- Single machine, single GPU, single dataset. These numbers are not a general law.

## Layout

```
scripts/01_preprocess.py    stream 2.62B nnz -> 1.3M x 1000 z-scored matrix
scripts/02_pca_umap.py      PCA -> k-means -> UMAP
scripts/bench_one.py        one (library, n) case; the three chart implementations
scripts/03_benchmark.py     sweep orchestrator
scripts/04_interaction.py   Chromium: load time, frame times, JS heap
scripts/05_aggregate.py     medians -> results/report_data.json
scripts/06_fidelity.py      zoom-fidelity figures
scripts/07_screenshot.py    screenshot the running page
app/                        Reflex comparison page
```
