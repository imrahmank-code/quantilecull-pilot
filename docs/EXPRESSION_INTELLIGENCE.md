# Expression Intelligence Specification — QuantileCull V1.2 FP6

This document specifies the face metric formulas, landmarks mapping, and selection algorithms.

---

## 1. Face Metric Formulas

Each face crop is evaluated on the following dimensions:

### A. Smile Confidence
Smile pulling uses lip corners compared to lip vertical height center:
$$\text{corners\_y} = \frac{Y_{61} + Y_{291}}{2.0}$$
$$\text{center\_y} = \frac{Y_{0} + Y_{17}}{2.0}$$
$$\text{pull} = \text{center\_y} - \text{corners\_y}$$
$$\text{width} = \|\vec{P}_{61} - \vec{P}_{291}\|$$
$$\text{ratio} = \frac{\text{pull}}{\text{width}}$$
$$\text{smile\_confidence} = \text{clamp}\left(\frac{\text{ratio} + 0.02}{0.12} \cdot 100.0, 0.0, 100.0\right)$$

### B. Occlusion Score
If any landmark coordinates reside in the outer 2% margin, the face is flagged:
$$\text{occlusion\_score} = 100.0\text{ (if boundary clip else 0.0)}$$

### C. Lighting Quality
HSV Value ($V$) channel mean and standard deviation (contrast):
$$\text{mean\_factor} = \max\left(0.0, 1.0 - \frac{|\bar{V} - 130.0|}{110.0}\right)$$
$$\text{contrast\_factor} = \min(1.0, \sigma_V / 40.0)$$
$$\text{lighting\_quality} = \text{mean\_factor} \cdot \text{contrast\_factor} \cdot 100.0$$

### D. Pose & Orientation
* `looking_at_camera`: True if $|\text{yaw}| < 15.0$ and $|\text{pitch}| < 15.0$.
* `head_pose_score`:
  $$\text{head\_pose\_score} = \max(0.0, 100.0 - (|\text{yaw}| + |\text{pitch}| + |\text{roll}|) \cdot 1.2)$$

### E. Face Quality Score (Aggregate)
$$\text{quality\_score} = 0.3 \cdot \text{sharpness} + 0.2 \cdot \text{eye\_openness} + 0.15 \cdot \text{smile\_confidence} + 0.15 \cdot \text{pose\_score} + 0.1 \cdot \text{lighting} + 0.1 \cdot (100.0 - \text{occlusion})$$

---

## 2. Best Shot Selection

The `best_shot_selector` maps each person/cluster ID across a set of burst duplicates, groups them, and determines the file path yielding the highest aggregate `face_quality_score`.
