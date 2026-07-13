# Clustering Subsystem — QuantileCull V1.2 FP4

This document specifies the clustering engine design, algorithms, and configuration parameters.

---

## 1. Pure NumPy Algorithms

To ensure zero native dependency compilation issues on user machines, the clustering algorithms are implemented using pure NumPy:

### A. DBSCAN (Density-Based Spatial Clustering)
* **Parameters**: `threshold` (eps distance, default `0.25`), `min_samples` (default `2`).
* **Distance Matrix**: Computed using Cosine Distance:
  $$D(x, y) = 1.0 - S_{cos}(x, y)$$
* **Use Case**: Best for initial batch clustering on a new folder scan.

### B. Hierarchical Agglomerative Clustering
* **Linkage**: Average Linkage.
* **Parameters**: `threshold` (max distance boundary for merges, default `0.25`).
* **Use Case**: Alternative batch clustering.

---

## 2. Incremental Clustering

Incremental clustering adds newly scanned face embeddings to the database without re-running O(N^2) calculations across the entire database:
1. Fetch all active cluster centroids.
2. Calculate cosine similarity between the new face and each centroid.
3. If similarity exceeds the threshold (`0.75`), join the cluster and update its centroid.
4. Otherwise, spawn a new cluster.
