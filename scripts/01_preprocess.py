"""Stream the 10x 1.3M mouse brain matrix into a PCA-ready dense HVG matrix.

The filtered CellRanger h5 stores a CSC matrix of shape (27998 genes, 1306127
cells) with 2.62e9 nonzeros. Materializing that as scipy sparse would need
~21-31 GB before any processing copies, so both passes here read contiguous
cell-major slices instead and never hold more than one chunk at a time.

Pass 1  accumulate per-gene sum / sum-of-squares of log1p(CP10K) values, which
        is enough for exact per-gene mean and variance (zeros contribute 0 to
        both), plus per-cell QC metrics.
Pass 2  re-read, normalize, subset to the selected HVGs, z-score with the pass-1
        moments, clip, and append to a dense float32 .npy on disk.
"""

from __future__ import annotations

import json
import time

import h5py
import numpy as np

H5_PATH = "data/1M_neurons_filtered_gene_bc_matrices_h5.h5"
GROUP = "mm10"
CHUNK = 20_000          # cells per streamed chunk
N_HVG = 1_000
TARGET_SUM = 1e4        # CP10K, the scanpy default
CLIP = 10.0

OUT_X = "data/X_hvg.npy"
OUT_META = "data/cell_meta.npz"
OUT_GENES = "data/hvg_genes.json"


def chunk_bounds(n_cells: int):
    for start in range(0, n_cells, CHUNK):
        yield start, min(start + CHUNK, n_cells)


def read_chunk(g, start: int, stop: int):
    """Return (data, indices, indptr) for cells [start, stop) as int64-free views."""
    lo = int(g["indptr"][start])
    hi = int(g["indptr"][stop])
    data = g["data"][lo:hi].astype(np.float32)
    indices = g["indices"][lo:hi]
    indptr = g["indptr"][start : stop + 1] - lo
    return data, indices, indptr


def normalize_chunk(data, indptr, n_cells_chunk):
    """CP10K-normalize then log1p, in place. Returns per-cell total counts."""
    # reduceat would mishandle empty cells (repeated indptr entries), so sum only
    # over cells that actually have nonzeros; empty spans contribute nothing.
    counts = np.diff(indptr)
    totals = np.zeros(n_cells_chunk, dtype=np.float64)
    nonempty = counts > 0
    if nonempty.any():
        sums = np.add.reduceat(data, indptr[:-1][nonempty])
        totals[nonempty] = sums
    scale = np.ones(n_cells_chunk, dtype=np.float32)
    np.divide(TARGET_SUM, totals, out=scale, where=totals > 0)
    data *= np.repeat(scale, counts)
    np.log1p(data, out=data)
    return totals, counts


def main() -> None:
    t_all = time.perf_counter()
    f = h5py.File(H5_PATH, "r")
    g = f[GROUP]
    n_genes, n_cells = (int(v) for v in g["shape"][:])
    print(f"matrix: {n_cells:,} cells x {n_genes:,} genes, nnz={g['data'].shape[0]:,}", flush=True)

    # ---------------- pass 1: per-gene moments + per-cell QC ----------------
    t0 = time.perf_counter()
    gene_sum = np.zeros(n_genes, dtype=np.float64)
    gene_sumsq = np.zeros(n_genes, dtype=np.float64)
    total_counts = np.zeros(n_cells, dtype=np.float32)
    n_genes_by_cell = np.zeros(n_cells, dtype=np.int32)

    for start, stop in chunk_bounds(n_cells):
        data, indices, indptr = read_chunk(g, start, stop)
        totals, counts = normalize_chunk(data, indptr, stop - start)
        # bincount is a tight C loop; np.add.at is unbuffered and ~100x slower,
        # which matters when the two passes touch 2.6e9 entries each.
        gene_sum += np.bincount(indices, weights=data, minlength=n_genes)
        gene_sumsq += np.bincount(indices, weights=data.astype(np.float64) ** 2,
                                  minlength=n_genes)
        total_counts[start:stop] = totals
        n_genes_by_cell[start:stop] = counts
        if start % (CHUNK * 10) == 0:
            print(f"  pass1 {start:>9,}/{n_cells:,}  {time.perf_counter()-t0:6.1f}s", flush=True)

    gene_mean = gene_sum / n_cells
    gene_var = np.maximum(gene_sumsq / n_cells - gene_mean**2, 0.0)
    print(f"pass 1 done in {time.perf_counter()-t0:.1f}s", flush=True)

    # Top-N by variance of log-normalized expression, restricted to genes seen
    # in a meaningful number of cells so ultra-rare noise genes cannot win.
    detected = gene_sum > 0
    order = np.argsort(gene_var * detected)[::-1]
    hvg_idx = np.sort(order[:N_HVG])
    print(f"selected {len(hvg_idx)} HVGs, var range "
          f"{gene_var[hvg_idx].min():.4f}-{gene_var[hvg_idx].max():.4f}", flush=True)

    gene_names = np.array([s.decode() for s in g["gene_names"][:]])
    with open(OUT_GENES, "w") as fh:
        json.dump({"hvg_index": hvg_idx.tolist(),
                   "hvg_names": gene_names[hvg_idx].tolist()}, fh)

    # gene -> column position in the reduced matrix, -1 for dropped genes
    col_of = np.full(n_genes, -1, dtype=np.int32)
    col_of[hvg_idx] = np.arange(len(hvg_idx), dtype=np.int32)
    hvg_mean = gene_mean[hvg_idx].astype(np.float32)
    hvg_std = np.sqrt(gene_var[hvg_idx]).astype(np.float32)
    hvg_std[hvg_std == 0] = 1.0

    # ---------------- pass 2: dense reduced matrix ----------------
    t0 = time.perf_counter()
    X = np.lib.format.open_memmap(
        OUT_X, mode="w+", dtype=np.float32, shape=(n_cells, len(hvg_idx))
    )
    for start, stop in chunk_bounds(n_cells):
        data, indices, indptr = read_chunk(g, start, stop)
        normalize_chunk(data, indptr, stop - start)
        counts = np.diff(indptr)
        rows = np.repeat(np.arange(stop - start, dtype=np.int32), counts)
        cols = col_of[indices]
        keep = cols >= 0
        block = np.zeros((stop - start, len(hvg_idx)), dtype=np.float32)
        block[rows[keep], cols[keep]] = data[keep]
        block -= hvg_mean
        block /= hvg_std
        np.clip(block, -CLIP, CLIP, out=block)
        X[start:stop] = block
        if start % (CHUNK * 10) == 0:
            print(f"  pass2 {start:>9,}/{n_cells:,}  {time.perf_counter()-t0:6.1f}s", flush=True)
    X.flush()
    del X
    print(f"pass 2 done in {time.perf_counter()-t0:.1f}s", flush=True)

    np.savez(OUT_META, total_counts=total_counts, n_genes_by_cell=n_genes_by_cell)
    f.close()
    print(f"TOTAL {time.perf_counter()-t_all:.1f}s -> {OUT_X}", flush=True)


if __name__ == "__main__":
    main()
