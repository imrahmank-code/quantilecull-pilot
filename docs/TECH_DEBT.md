# Technical Debt Register — QuantileCull V1.2

This document logs deferred tasks, design compromises, and refactoring opportunities. It serves as the backlog for engineering improvements in future release cycles.

---

## 1. Architectural Debt

### DT-001: Path String Representations
* **Description**: The codebase uses raw string manipulations for file paths (`os.path.join`, `os.path.split`, string indexing) instead of standard `pathlib.Path` objects.
* **Deferred Reason**: Preserved compatibility with legacy legacy V1.0 file utility methods.
* **Priority**: **Medium**
* **Impact**: Low risk of platform compatibility issues when expanding to macOS/Linux.
* **Suggested Version**: V1.3 Refactoring.

### DT-002: Monolithic app.py Class
* **Description**: `app.py`'s `WebviewApi` class manages UI routing, thread submission, licensing validation, telemetry log generation, and file exporting.
* **Deferred Reason**: Fast-path delivery of feature sets.
* **Priority**: **High**
* **Impact**: Decreases maintainability and increases risk of developer merge conflicts.
* **Suggested Version**: V1.2 Feature Pack 3.

---

## 2. Performance Debt

### DT-003: CPU Preview Downscaling Bottleneck
* **Description**: RAW image preview downscaling is done using standard Pillow/CPU methods in `preview_engine.py` instead of utilizing hardware-accelerated SIMD instructions or GPU shaders.
* **Deferred Reason**: Minimizing binary sizes and dependencies.
* **Priority**: **Medium**
* **Impact**: Generates minor latency spikes when pre-caching large folders of CR3/NEF assets.
* **Suggested Version**: V1.2 Feature Pack 2 (Clustering).

---

## 3. UX & UI Debt

### DT-004: Direct DOM Manipulations in JS
* **Description**: `static/js/app.js` performs verbose direct DOM manipulation (e.g. `document.createElement`, modifying `style.cssText` directly) rather than using a clean declarative component UI strategy.
* **Deferred Reason**: Kept standard vanilla HTML/JS stack to bypass heavy compilation steps.
* **Priority**: **Low**
* **Impact**: Increased difficulty adding advanced tabbed states or responsive UI panel modifications.
* **Suggested Version**: V2.0 Web Interface.

---

## 4. Testing Debt

### DT-005: Mocked RAW Test Assets
* **Description**: Unit and integration test suites mock the binary headers and mock `rawpy` calls rather than running assertions against a small, physical RAW image format file.
* **Deferred Reason**: Reducing Git repository bloat.
* **Priority**: **Medium**
* **Impact**: Limits validation of real-world EXIF extraction anomalies.
* **Suggested Version**: V1.2 QA Phase.
