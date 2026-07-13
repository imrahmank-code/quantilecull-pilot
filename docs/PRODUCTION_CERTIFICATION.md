# Production Certification Specification — QuantileCull V1.2 FP10

This document defines the profiling boundaries, recovery policies, settings migrations, and update mechanisms for the stable release.

---

## 1. Large-Library Performance Targets

Scalability target sizes for culling operations are defined as:
* **Total Images**: 100,000 metadata entries.
* **Identities**: 10,000 cluster centroids.
* **Embeddings**: 100,000 face descriptors (512-dim vectors).
* **Speed Target**: Cosine similarity batch math must complete in $<1.0$ second.

---

## 2. Configuration Settings Migration

User configurations from legacy versions (V1.1) map automatically to the V1.2 format:
* Default **eye openness threshold** is set to $75\%$.
* Default **smile confidence threshold** is set to $50\%$.
* **Auto eye correction** default is enabled.
* **Developer Mode diagnostics** default is disabled for regular production workflows.

---

## 3. Stress Testing & Recovery Policy

Scanners recover cleanly from the following faults:
* **Corrupted Image Headers**: Skips and logs files gracefully.
* **Missing Databases**: Automatic schema recreation on restart.
* **SQLite Locking**: Employs global connection serialization.
