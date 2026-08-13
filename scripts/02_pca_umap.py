"""PCA -> k-means -> UMAP on the 1.3M-cell reduced matrix.

PCA is done by streaming the 1000x1000 gram matrix and eigendecomposing it,
which is mathematically identical to a full SVD-based PCA but touches the
5 GB memmap exactly twice instead of copying it.
"""

from __future__ import annotations

import json
import time

import numpy as np

X_PATH = "data/X_hvg.npy"
N_PC = 50
N_CLUSTERS = 24
CHUNK = 100_000
SEED = 0

timings: dict[str, float] = {}


def stopwatch(name: str):
    class _T:
        def __enter__(self):
            self.t = time.perf_counter()
            print(f"[{name}] start", flush=True)
            return self

        def __exit__(self, *a):
            timings[name] = time.perf_counter() - self.t
            print(f"[{name}] {timings[name]:.1f}s", flush=True)

    return _T()


def main() -> None:
    X = np.load(X_PATH, mmap_mode="r")
    n, d = X.shape
    print(f"X: {n:,} x {d} ({X.nbytes/1e9:.1f} GB on disk)", flush=True)

    # ---------------- PCA via streamed gram matrix ----------------
    with stopwatch("pca"):
        col_sum = np.zeros(d, dtype=np.float64)
        for i in range(0, n, CHUNK):
            col_sum += X[i : i + CHUNK].sum(axis=0, dtype=np.float64)
        mean = (col_sum / n).astype(np.float32)

        gram = np.zeros((d, d), dtype=np.float64)
        for i in range(0, n, CHUNK):
            block = np.asarray(X[i : i + CHUNK], dtype=np.float32) - mean
            gram += block.T @ block
        gram /= n - 1

        eigvals, eigvecs = np.linalg.eigh(gram)
        order = np.argsort(eigvals)[::-1][:N_PC]
        components = eigvecs[:, order].astype(np.float32)
        explained = eigvals[order] / eigvals.sum()
        print(f"  top-{N_PC} explains {explained.sum()*100:.1f}% of variance", flush=True)

        pcs = np.empty((n, N_PC), dtype=np.float32)
        for i in range(0, n, CHUNK):
            pcs[i : i + CHUNK] = (np.asarray(X[i : i + CHUNK], dtype=np.float32) - mean) @ components
        np.save("data/pca50.npy", pcs)
        np.save("data/pca_explained.npy", explained)

    # ---------------- k-means labels for colouring ----------------
    with stopwatch("kmeans"):
        from sklearn.cluster import MiniBatchKMeans

        km = MiniBatchKMeans(
            n_clusters=N_CLUSTERS, random_state=SEED, batch_size=10_000,
            n_init=5, max_iter=200,
        )
        labels = km.fit_predict(pcs).astype(np.int16)
        np.save("data/labels.npy", labels)
        sizes = np.bincount(labels)
        print(f"  cluster sizes {sizes.min():,}-{sizes.max():,}", flush=True)

    # ---------------- UMAP ----------------
    with stopwatch("umap"):
        import umap

        reducer = umap.UMAP(
            n_neighbors=15, min_dist=0.3, n_components=2, metric="euclidean",
            random_state=None, low_memory=True, verbose=True, n_jobs=-1,
        )
        emb = reducer.fit_transform(pcs).astype(np.float32)
        np.save("data/umap2.npy", emb)
        print(f"  embedding x:[{emb[:,0].min():.2f},{emb[:,0].max():.2f}] "
              f"y:[{emb[:,1].min():.2f},{emb[:,1].max():.2f}]", flush=True)

    with open("results/pipeline_timings.json", "w") as fh:
        json.dump({"n_cells": int(n), "n_hvg": int(d), "timings_s": timings}, fh, indent=2)
    print("DONE", json.dumps(timings, indent=2), flush=True)


if __name__ == "__main__":
    main()
