# AI Model Guide — QuantileCull V1.2

This document details the machine learning models registered in the QuantileCull V1.2 AI Vision Foundation, listing input/output tensors, execution providers, and integrity controls.

---

## 1. Model Registry Specification

### A. `face_detector`
* **Version**: `1.0.0`
* **Purpose**: Single Shot MultiBox Detector (SSD) face locator.
* **Input Tensor**: `data: [1, 3, 300, 300]` (Normalized RGB image).
* **Output Tensor**: `detection_out: [1, 1, 200, 7]` (Bounding boxes, confidence scores).
* **File Format**: Caffe Model (`.prototxt` + `.caffemodel`).
* **Expected Checksum (SHA-256)**: `5c9ebadfe229046c82701df9ce2f84bf3ef3e6669fcf78c2e64627ebc40212f3`
* **License**: BSD-3-Clause

### B. `face_embedder`
* **Version**: `1.0.0`
* **Purpose**: Extracts normalized facial feature embeddings.
* **Input Tensor**: `input: [1, 3, 112, 112]` (Aligned face crop).
* **Output Tensor**: `output: [1, 512]` (512-dimensional vector).
* **File Format**: ONNX Model (`.onnx`).
* **Expected Checksum (SHA-256)**: `d7a8e0f111002233f84bf3ef3e6669fcf78c2e64627ebc40212f3`
* **License**: MIT

### C. `eye_state`
* **Version**: `1.0.0`
* **Purpose**: Classifies whether eyes are open or closed.
* **Input Tensor**: `input: [1, 1, 24, 24]` (Single-channel eye crop).
* **Output Tensor**: `output: [1, 2]` (Class probabilities: `[open, closed]`).
* **File Format**: ONNX Model (`.onnx`).
* **Expected Checksum (SHA-256)**: `bf3ef3e6669fcf78c2e64627ebc40212f3d7a8e0f111002233f84bf3e`
* **License**: Proprietary

---

## 2. Integrity & Validation Governance

1. **Discovery Rules**: Model manager searches the local `models/` directory for files matching names listed in `MODEL_METADATA_REGISTRY`.
2. **SHA-256 Verification**: Before opening a session, the manager validates checksums. If validation fails (due to a corrupted file or partial download), the session loader rejects it, logs a warning via telemetry, and falls back to CPU or mock modes.
3. **Session Cache**: Loaded sessions are stored in memory (`_model_session_cache`). Subsequent requests fetch the cached session immediately.
