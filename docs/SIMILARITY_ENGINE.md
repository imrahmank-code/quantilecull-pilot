# Similarity Engine Specification — QuantileCull V1.2 FP4

This document specifies the vector math operations, distance calculations, and search routines of the similarity engine.

---

## 1. Metrics & Distances

* **Cosine Similarity**: Measures the cosine of the angle between two multi-dimensional embeddings:
  $$S_{cos}(\vec{u}, \vec{v}) = \frac{\vec{u} \cdot \vec{v}}{\|\vec{u}\| \|\vec{v}\|}$$
* **Cosine Distance**: Normalized distance scale:
  $$D_{cos}(\vec{u}, \vec{v}) = 1.0 - S_{cos}(\vec{u}, \vec{v})$$
* **Euclidean Distance**: Straight-line distance:
  $$D_{euc}(\vec{u}, \vec{v}) = \sqrt{\sum (u_i - v_i)^2}$$

---

## 2. Nearest Neighbors Search

* **Routines**: `find_similar_faces(query, candidates, threshold)`
* **Execution**: Iterates through candidate arrays, computes similarity, filters indices exceeding the threshold, and returns results sorted by descending similarity score.
* **Matrix Builder**: `build_similarity_matrix(embeddings)` yields a symmetric 2D similarity matrix for all combinations.
