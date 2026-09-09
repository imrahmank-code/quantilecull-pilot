# QuantileCull Next-Iteration Module Architecture Specification
**Document Version:** 1.0.0  
**Target Milestone:** QuantileCull V1.3-Enterprise  
**Branch:** `feature/next-iteration`  
**Author:** Principal Systems Reliability Engineer & Executive Operations Architect  
**Status:** Approved Architectural Baseline  

---

## 1. Executive Summary & Problem Statement

QuantileCull V1.2 successfully established automated RAW image ingestion, facial clustering, blink recovery, expression intelligence, and non-destructive Lightroom XMP tagging. Feedback from production wedding studios and high-volume event photographers indicates three primary operational bottlenecks in real-world 3,000+ RAW workflows:

1. **Multi-Camera Clock Drift:** Wedding shoots utilize 2–4 distinct camera bodies (e.g., Canon EOS R5, Sony A7IV) whose internal clocks drift by seconds to minutes, causing burst interleaving errors during chronological culling.
2. **Preview Latency on Heavy RAW Formats:** Generating high-fidelity previews across uncompressed 45MP+ RAW assets (CR3, NEF, ARW) induces CPU bottlenecks during rapid candidate selection.
3. **Granular Lightroom Tagging & Rating Profiles:** Studios require custom mappings for star ratings (1–5 stars) and color labels (Pick, Reject, Second Shooter Review, Highlight) compatible with Adobe Lightroom Classic, Capture One, and Photo Mechanic.

This specification defines the next-generation modular architecture to resolve these bottlenecks while strictly preserving 100% backward compatibility.

---

## 2. Architectural Pillars & Core Subsystems

```
                                  +---------------------------------------+
                                  |    QuantileCull Desktop Ingestion     |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |  MultiCameraSyncEngine (Pillar 1)     |
                                  |  - EXIF Timestamp Offset Calibration  |
                                  |  - Flash-Burst Temporal Alignment    |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |    FastPreviewEngine (Pillar 2)       |
                                  |  - SIMD/LibRaw Thumbnail Extraction   |
                                  |  - Async Dual-Ring LRU Cache          |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |     AI Culling & Ranking Pipeline     |
                                  |  - Facial Quality & Expression Score  |
                                  |  - Blur & Eye-Openness Evaluation     |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  |   EnhancedXmpEngine (Pillar 3)        |
                                  |  - Adobe XMP Sidecar Generation       |
                                  |  - Customizable Color/Star Schemas    |
                                  +-------------------+-------------------+
                                                      |
                                                      v
                                  +---------------------------------------+
                                  | ResilientLicensingManager (Pillar 4)  |
                                  |  - Offline Heartbeat & Grace Period   |
                                  |  - VIP Supabase Registry Fallback     |
                                  +---------------------------------------+
```

---

### Pillar 1: Multi-Camera Temporal Alignment (`MultiCameraSyncEngine`)

* **Objective:** Automatically detect and calibrate timestamp skew between multiple camera bodies without modifying original RAW capture files.
* **Component Design:**
  * **Input:** Manifest of image metadata extracted by `metadata_engine`.
  * **Clustering by Serial Number:** Groups photos by `EXIF.BodySerialNumber` and `EXIF.Model`.
  * **Drift Estimation:**
    * *Manual Offset Override:* Studio inputs manual delta (e.g., `Camera B = +00:02:14`).
    * *Auto-Correlation Heuristic:* Identifies simultaneous flash-sync events or high-similarity scene transitions captured by both bodies within a 10-second sliding window.
  * **Virtual Timeline Normalization:** Outputs a normalized epoch timestamp (`normalized_timestamp_ms`) used by `similarity_engine` and `storytelling_engine` to organize continuous burst sequences.

---

### Pillar 2: SIMD-Accelerated Fast Preview Engine (`FastPreviewEngine`)

* **Objective:** Reduce per-image preview render latency from ~120ms to <25ms on standard multicore laptop hardware.
* **Component Design:**
  * **Direct Embedded JPEG Extraction:** Bypasses full sensor demosaicing whenever high-resolution embedded JPEG previews (2048px+) exist in the RAW container (`rawpy.extract_thumb()` / `exiftool` accelerated buffers).
  * **SIMD Rescaling:** Employs hardware-accelerated bilinear/bicubic scaling via `Pillow-SIMD` or OpenCV SSE4/AVX2 routines.
  * **Dual-Ring LRU Memory Cache:**
    * Ring A (Foreground Active): Keeps current cluster and ±5 adjacent images in uncompressed memory for instant instantaneous rendering.
    * Ring B (Background Speculative): Asynchronously warms upcoming clusters in a low-priority worker thread.

---

### Pillar 3: Granular Sidecar & Metadata Tagging (`EnhancedXmpEngine`)

* **Objective:** Expand the current binary Pick/Reject metadata export into a comprehensive, configurable metadata bridge for post-processing software.
* **Component Design:**
  * **Standard Profiles:**
    * *Adobe Lightroom Classic:* XMP tags `<xmp:Rating>` (1–5) and `<photoshop:SidecarForExtension>`.
    * *Capture One:* Injects `<photoshop:ColorLabel>` (None, Red, Green, Blue, Yellow, Purple).
    * *Photo Mechanic Compatibility:* Generates standard `.xmp` companion files alongside RAW assets.
  * **Studio Preset Mapping:**
    * `5 Stars` = Best in Sequence (Primary Pick).
    * `4 Stars` = Alternative / Variant Pick.
    * `1 Star` = Blurry / Closed Eyes / Technical Flaw (Auto-Reject).
    * `Color Label: Green` = Approved for Client Sneak Peek.
    * `Color Label: Red` = Culling Reject.

---

### Pillar 4: Resilient Edge Licensing & Offline Heartbeat (`ResilientLicensingManager`)

* **Objective:** Ensure professional wedding photographers working on-location without cellular or Wi-Fi internet can execute uninhibited culling runs for up to 14 days without licensing interruptions.
* **Component Design:**
  * **Cryptographic Token Vault:** Offline licenses signed with asymmetric RSA/Ed25519 signatures issued by Paddle/Supabase licensing backend.
  * **Tamper-Resistant Clock Drift Detection:** Compares system local time against file system modification timestamps and monotonic hardware uptime to prevent system clock rollback bypass.
  * **Grace Period Subsystem:** 14-day rolling offline validation window with automated background renewal upon network reconnect.

---

## 3. Data Flow & Interface Contracts

### MultiCameraSync Contract
```python
class CameraSyncConfig:
    camera_id: str
    serial_number: str
    offset_seconds: float

class NormalizedPhotoMetadata:
    original_path: str
    camera_id: str
    original_timestamp: datetime
    normalized_timestamp: datetime
    cluster_id: Optional[str]
```

### XmpExport Contract
```python
class XmpExportProfile:
    target_application: str  # "Lightroom" | "CaptureOne" | "PhotoMechanic"
    pick_rating: int        # e.g., 5
    reject_rating: int      # e.g., 1
    pick_color_label: str   # e.g., "Green"
    reject_color_label: str # e.g., "Red"
    write_mode: str         # "sidecar_xmp" | "embedded"
```

---

## 4. Quality, Reliability, and Regression Safeguards

1. **Zero Raw Mutation Guarantee:** Under no circumstances are raw sensor bits (`.CR3`, `.NEF`, `.ARW`, `.DNG`) altered. All operations strictly produce detached `.xmp` companion sidecars or read-only preview frames.
2. **Memory Footprint Bounds:** Total preview cache consumption is capped at 1.5 GB RAM; memory overruns automatically evict Ring B speculative frames.
3. **Test Automation Baseline:** All new modules must achieve ≥ 90% branch test coverage before integration into release candidate builds.
