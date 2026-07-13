# Storytelling & Event Intelligence Specification — QuantileCull V1.2 FP8

This document specifies the timeline segmentation, scene classification heuristics, highlight metrics, coverage checks, and DAM exports.

---

## 1. Timeline Segmentation

Photos are ordered chronologically and divided into chapters by identifying temporal gaps:
$$\Delta t_i = t_i - t_{i-1} > \text{gap\_seconds}$$
Default value: `900` seconds (15 minutes).

---

## 2. Heuristic Scene Classification Heuristics

Scenes are categorized based on face counts, face sizes, and smile values:
* **Details/Decor**: 0 faces.
* **Portraits**: 1-2 faces where at least one face bounding box width or height exceeds 150px.
* **Reception**: 3-6 faces with average smile confidence $>60.0\%$.
* **Dance Floor**: $>6$ faces with average smile confidence $>55.0\%$.
* **Ceremony**: $>2$ faces with lower smile averages (formal pose).
* **General**: Fallback for any other cases.

---

## 3. Curated Selections & Export Manifests

* **Automatic Highlights**: Selects top-N images with the highest average face quality scores.
* **Coverage Gaps**:
  * Identifies underrepresented person IDs appearing in $<5\%$ of total face occurrences.
  * Identifies narrative temporal gaps exceeding 1 hour.
* **Lightroom DAM Export**: Writes XML file containing a list of photo locations.
