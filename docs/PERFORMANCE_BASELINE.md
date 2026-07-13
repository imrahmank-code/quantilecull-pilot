# Performance Baseline Specification — QuantileCull V1.2

This document specifies the official performance metrics and system resource baselines for QuantileCull V1.2. All future Feature Packs must compare performance logs against these baseline figures.

---

## 1. System Culling Throughput

The following statistics represent processing efficiency tested over a 100-photo standard dataset (800x600 px) using an AMD/Intel 4-Core CPU system:

### Cold Scan Speed (First run, empty cache)
* **Scan Duration (Total)**: **39.597 seconds**
* **Scan Speed (Per image)**: **0.395 seconds**
* **Active Tasks**: File checksum computation, EXIF parsing, OpenCV DNN facial detection model execution, Laplacian variance sharpness estimation, and duplicate distance clustering.

### Warm Scan Speed (Subsequent run, active cache)
* **Scan Duration (Total)**: **0.117 seconds**
* **Scan Speed (Per image)**: **1.17 milliseconds**
* **Speedup Ratio**: **~338x faster** than cold scan.

### Cache Hit Ratio
* **Target Rate**: **100%** (Assuming no change to target image source files or corresponding XMP sidecar timestamps).

---

## 2. Resource Utilization Baselines

| Resource Category | Cold Scan (Peak) | Warm Scan (Peak) | Idle / Standby |
| :--- | :---: | :---: | :---: |
| **CPU Utilization** | ~45% | <2% | <0.1% |
| **Peak Memory Allocation** | **126.60 MB** | **5.05 MB** | ~45 MB (base app footprint) |
| **I/O Disk Read Throughput** | ~25 MB/s | <0.5 MB/s | 0.0 MB/s |
| **Database Transaction Time** | ~1.5 ms / write | <0.1 ms / read | - |

---

## 3. UI Response Latency

* **Image Grid Card Loading**: **<15ms** (when using pre-cached thumbnails).
* **Adjacent Preloading Bounded Wait**: **<50ms** (for full-resolution viewer transition).
* **Interactive Rating/Label Update Sync**: **<8ms** (instantaneous local memory state update; off-thread sidecar write).

---

## 4. Export Pipeline

* **JPEG Downscaling & Export Rate**: **4.60 milliseconds per image** (100 images exported in 0.460s).
* **Maximum Thread Pool Workers**: Matches system physical cores count (`cpu_count`).
