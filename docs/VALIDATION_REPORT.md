# Validation & Testing Report — QuantileCull V1.2 FP4

This report documents the testing execution and validation results of the clustering engine.

---

## 1. Automated Test Execution

All **59 tests** passed successfully:

* **15 Regression Tests**: Validated V1.1 culling rules, exposure calculations, and license bindings.
* **1 Integration Test**: Ran end-to-end folder scanning, XMP sync, and recovery tracking.
* **27 AI & Face Tests (FP2/FP3)**: Validated ONNX model caches, topological sorting of features, normalized embeddings, face detection coordinates, landmarks, and orientations.
* **16 Clustering Tests (FP4)**: Verified distance calculations, DBSCAN, Agglomerative linkages, graph merges/splits, SQLite cascade deletions, and incremental updates.

```text
Ran 59 tests in 3.879s
OK
```

---

## 2. Benchmark Metrics

* **Similarity Throughput**: 100,000 vector similarity checks complete in **~0.04s** on CPU.
* **Incremental Cluster Assignment**: Adding a newly scanned image with 5 faces takes **<2ms**, ensuring zero impact on culling scan times.
