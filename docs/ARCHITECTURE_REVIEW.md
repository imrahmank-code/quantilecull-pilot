# Architecture Validation Report — QuantileCull V1.2 FP1

This document evaluates the architectural design, modularity, performance, coupling, and AI scalability of the V1.2 platform.

---

## 1. Architectural Score

* **Modularity**: 9.5 / 10
* **Scalability**: 9.0 / 10
* **Maintainability**: 8.5 / 10
* **Performance**: 9.5 / 10
* **Coupling**: 9.0 / 10 (Low coupling)
* **Cohesion**: 9.5 / 10 (High cohesion)
* **Overall Readiness Score**: **9.1 / 10**

---

## 2. Component Evaluation

### Caching Strategy (Double-Mtime DB validation)
* **Strengths**: The cache lookup uses a double check matching the modification times of BOTH the image source file and the XMP sidecar. This avoids loading outdated CV metrics if the user changes ratings or labels in external tools (like Lightroom).
* **Weaknesses**: Modification timestamps rely on file system mtime float values. On some older FAT32 external drives, precision is limited to 2 seconds, which can cause edge-case cache hits if edits occur in rapid succession.

### Threading Model
* **Strengths**: Heavy photographic disk reads (RAW preview extraction) and sidecar writing are executed on system thread worker pools (`ThreadPoolExecutor`). This maintains visual smoothness in the main Bottle/PyWebView window.
* **Weaknesses**: JavaScript communicates using async Promise chains. If too many calls are made sequentially, PyWebView API calls can queue up on slow disks.

### AI Expansion Readiness
* **Strengths**: The `image_analyzer` and local sub-modules are structured with modular functions, making it trivial to plug in ONNX inference models, GPU delegates, or face clustering pipelines without refactoring core routing.

---

## 3. Risks & Mitigation Recommendations

| Risk Description | Severity | Mitigation Strategy |
| :--- | :---: | :--- |
| **Out-of-Memory (OOM) on massive folders**: Extracting and caching 50,000 RAW thumbnails simultaneously could exhaust RAM. | **High** | Implement a sliding page buffer in the preloader; limit background pre-caching to active window boundaries (+/- 100 images). |
| **XMP Sidecar Write Collisions**: Lightroom and QuantileCull modifying the same sidecar concurrently could lock the file. | **Medium** | Implement an file-write retry loop with exponential backoff (e.g. 3 attempts over 500ms). |
| **Floating-Point mtime Drift**: File sync tools may modify mtime values slightly during network syncs, causing unnecessary cache invalidations. | **Low** | Store file checksums (SHA-256) inside the database to verify matches if mtime timestamps differ. |
