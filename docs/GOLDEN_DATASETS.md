# QuantileCull Production Validation: Golden Datasets

This document catalogs the permanent production validation datasets used to verify the accuracy, quality, and performance of the QuantileCull culling engine.

---

## 1. Governance Rule
Any modification affecting duplicate detection, selection scoring, storytelling, hero extraction, or export behavior **MUST** be validated against these datasets prior to completion. Regression tests alone are insufficient.

---

## 2. Dataset Catalog

### 📊 Conference_01
* **Type**: Corporate Conference (Single Track)
* **Image Count**: 1,950 images
* **Baseline Retention**: 25.0%
* **Focus**: Baseline duplicates detection, composition accuracy, and standard scan throughput.

### 📊 Conference_02
* **Type**: Multi-Track Industry Conference
* **Image Count**: 2,412 images
* **Baseline Retention**: 31.0%
* **Focus**: Large-scale duplicate clustering, warm-cache optimization stability, and scalability.

### 📊 Expo_01
* **Type**: Trade Show & Exhibition Floor
* **Image Count**: TBD
* **Baseline Retention**: TBD
* **Focus**: High clutter environments, exhibit booth duplicates, and fast-moving crowd scene handling.

### 📊 Networking_01
* **Type**: Evening Networking Reception (Low/Variable Illumination)
* **Image Count**: TBD
* **Baseline Retention**: TBD
* **Focus**: Face-matching under challenging lighting, sharpness estimation, and candidate grouping.

### 📊 Awards_01
* **Type**: Stage Awards Ceremony & Keynotes
* **Image Count**: TBD
* **Baseline Retention**: TBD
* **Focus**: Keynote/speaker duplicate sequence reduction, storytelling continuity, and stage lighting contrast handling.
