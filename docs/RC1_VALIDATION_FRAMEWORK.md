# RC1 Production Validation Framework — QuantileCull V1.2

This document specifies the validation criteria, threshold scaling factors, and culling matrices utilized during Release Candidate 1 certification.

---

## 1. Hardware Performance Scale Tiers

Timing limits are scaled to prevent false failures on lower-spec workstations:
* **Tier A** (High-end): Factor = $1.00\times$
* **Tier B** (Mainstream): Factor = $1.30\times$
* **Tier C** (Mobile/Laptop): Factor = $1.70\times$

### Latency Budgets (Base $\times$ Factor)
* **Header Parse**: $15\text{ ms}$
* **Preview Extraction**: $40\text{ ms}$
* **Embedding Extraction**: $15\text{ ms}$
* **Face Detection**: $35\text{ ms}$
* **Expression Scoring**: $8\text{ ms}$

---

## 2. Metadata Compatibility Verification

* **Required Columns**: Camera Make, Model, Capture Timestamp, Orientation, Lens Information, Color Space, Image Dimensions, Bit Depth, Compression Mode, Color Profile.
* **Maker Notes Classification**: `SUPPORTED`, `PARTIAL`, `UNSUPPORTED`.

---

## 3. Geometric Eye Correction Validation

* **Pose Angles**: $\le 12.0^{\circ}$ deviation for yaw, pitch, and roll.
* **Exposure**: Mean HSV difference $\le 15.0\%$.
* **IPD Check**: Inter-pupil distance difference must be $\le 5.0\%$. Exceeding this boundary rejects the eye replacement.
