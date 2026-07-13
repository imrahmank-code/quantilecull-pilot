# Feature Dependency Matrix — QuantileCull V1.2

This document defines the dependency hierarchy for all Feature Packs (FPs) planned in the V1.2 release cycle. It ensures architectural isolation, clean modular boundaries, and structured development sequencing.

---

## 1. Dependency Tree

```text
QuantileCull V1.2 Lifecycle
│
├── Feature Pack 1: Professional RAW & Performance Foundation (COMPLETED)
│   ├── raw_engine (RAW recognition, decoding)
│   ├── preview_engine (Preview extraction, downscaling)
│   ├── metadata_engine (EXIF mapping)
│   ├── xmp_engine (Non-destructive XMP rating/label sidecars)
│   ├── cache_engine (Double-mtime cache validation)
│   └── background_tasks (Off-thread pre-caching, preloading)
│
├── Feature Pack 2: Intelligent Clustering & Advanced Culling (PLANNED)
│   ├── Requires: FP1 (raw_engine, metadata_engine, cache_engine)
│   ├── Modules:
│   │   ├── cluster_engine (Perceptual similarity, clustering)
│   │   └── storytelling_engine (Sequence flow, event boundary extraction)
│
├── Feature Pack 3: Smart Face Culling & Local Swaps (PLANNED)
│   ├── Requires: FP1 + FP2 (cluster_engine, preview_engine)
│   ├── Modules:
│   │   ├── facial_detector (DNN facial feature extractor)
│   │   ├── expression_analyzer (Eye openness, smiling metrics)
│   │   └── correction_engine (Seamless eye/face swap alignment)
│
└── Future Packs (POST-V1.2 / ROADMAP)
    ├── GPU Acceleration Module (Requires FP1 + FP3)
    └── Cloud Export & Synchronization (Requires FP1)
```

---

## 2. Module Dependency Matrix

The table below outlines which future Feature Packs rely on the APIs introduced in Feature Pack 1:

| Feature Pack 1 Module | FP2: Clustering | FP3: Face Swapping | Future: GPU acceleration | Future: Cloud Sync |
| :--- | :---: | :---: | :---: | :---: |
| `raw_engine` | **Prerequisite** | Direct dependency | - | - |
| `preview_engine` | - | **Prerequisite** | - | - |
| `metadata_engine` | **Prerequisite** | Direct dependency | - | - |
| `xmp_engine` | Direct dependency | - | - | **Prerequisite** |
| `cache_engine` | **Prerequisite** | Direct dependency | Direct dependency | - |
| `background_tasks` | Direct dependency | **Prerequisite** | - | - |

---

## 3. Governance Guidelines for Future Packs

1. **Strict Upstream Isolation**: A module in an earlier Feature Pack must never import or depend upon a module from a later Feature Pack.
2. **Loosely Coupled Interfaces**: All communication across Feature Packs should flow through public API contracts defined in `docs/API_REFERENCE.md`.
3. **No Direct Database Access**: Future packs must access SQLite database tables via `cache_engine` methods rather than opening raw connection cursors.
