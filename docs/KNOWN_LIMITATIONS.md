# Known Limitations — QuantileCull V1.2

This document catalog-lists the known limitations, boundaries, and unimplemented capabilities of QuantileCull V1.2. It defines the current boundaries of Feature Pack 1.

---

## 1. Operating System & Platform Limits

* **Windows Only**: The current build relies on specific Win32 file locking mechanisms (`tempfile.gettempdir()`, `.quantilecull_cache.db`), registry folder selectors, and local AppData directory structures.
  * **No macOS support** (relies on different file permission schemes).
  * **No Linux support** (requires custom PyWebView/GTK package configuration).

---

## 2. Hardware & Acceleration Constraints

* **CPU-Only Inference**: All computer vision model evaluations (facial detection, sharpness estimation, eye openness calculations) run on the CPU.
  * **No GPU acceleration** (CUDA, OpenCL, TensorRT, or DirectML delegates are not compiled).
  * **No ONNX Runtime execution**: Currently relies on OpenCV's DNN module loading Caffe/Protobuf models.

---

## 3. Culling & Metric Limitations

* **No Perceptual Image Grouping**: Perceptual clustering and smart scene partitioning are not yet implemented. Candidate sets are grouped solely by file naming structures or timestamp ranges.
* **Simple Eye Blink swap bounds**: Eye swap corrections require identical camera orientation and bounding box placement. High-angle rotation or significant scale changes across blink sequences are not adjusted.
* **Metadata Exclusions**: GPS coordinate tags, IPTC copyright fields, and user comments are ignored during metadata analysis (though they are safely preserved inside XMP sidecars during modification).

---

## 4. Architectural & Deployment Bounds

* **Fully Local**: All culling, analysis, and metadata modifications run locally. No cloud synchronization, mobile sharing, or distributed multi-node processing is available.
* **SQLite Database Lock limits**: Multi-window culling of the same directory may cause brief SQLite write-block timeouts if database writes overlap.
