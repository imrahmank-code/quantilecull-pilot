# AI Feature Registry Specification — QuantileCull V1.2

This document details the registry, parameters, priorities, and dependency rules of all AI modules.

---

## 1. Feature Specifications

| Feature Name | Prerequisite Dependencies | Required Model | Priority | Est. Runtime |
| :--- | :--- | :--- | :---: | :---: |
| **QUALITY** | None | None (Classical CV) | 0 | 0.02s |
| **FACE_DETECTION** | None | `face_detector` | 1 | 0.05s |
| **FACE_EMBEDDING** | `FACE_DETECTION` | `face_embedder` | 2 | 0.15s |
| **EYE_STATE** | `FACE_DETECTION` | `eye_state` | 3 | 0.08s |
| **SMILE** | `FACE_DETECTION` | `smile_classifier` | 4 | 0.06s |
| **SUBJECT** | None | `subject_detector` | 5 | 0.12s |
| **BODY** | None | `body_detector` | 6 | 0.10s |
| **SCENE** | None | `scene_classifier` | 7 | 0.08s |
| **STORY** | `SCENE`, `FACE_EMBEDDING` | `storytelling_analyzer` | 8 | 0.20s |

---

## 2. Execution Order Resolution (Topological Sort)

Dependencies are resolved dynamically using a Depth-First Search (DFS) topological sort:

1. **Cycle Prevention**: Visited nodes are tracked. If a feature is re-visited before completion, a `ValueError` is raised, preventing infinite recursion loops.
2. **Prerequisites Precedence**: Prerequisite nodes are appended to the execution list before their parent nodes (e.g. `FACE_DETECTION` will always precede `FACE_EMBEDDING` and `EYE_STATE`).
3. **Registry Modification**: Custom modules can register themselves at runtime using:
   `feature_registry.register_feature(name, required_model, dependencies, priority, est_runtime)`
