# Workflow Automation & Professional Export Pipeline — QuantileCull V1.2 FP9

This document specifies the sidecar XMP format updates, preset mappings, report generators, folder structures, and batch progress queues.

---

## 1. Non-Destructive XMP Updates

Lightroom-compatible metadata changes write/update standard XMP tags sidecars:
* **Star Ratings**: `<xmp:Rating>{rating}</xmp:Rating>`
* **Color Labels**: `<xmp:Label>{label}</xmp:Label>`
* **Keywords**: `<dc:subject><rdf:Bag><rdf:li>{keyword}</rdf:li></rdf:Bag></dc:subject>`

---

## 2. Configurable Export Presets

* **Wedding Preset**:
  * Highlights: 5 Stars + Red label
  * Portraits: 4 Stars + Blue label
  * Ceremony: 3 Stars + Green label
  * Reception: 3 Stars + Yellow label
* **Corporate Preset**:
  * Highlights: 5 Stars + Blue label
  * Portraits: 4 Stars
  * Others: 3 Stars + Purple label
* **Sports Preset**:
  * Highlights: 5 Stars + Red label
  * Others: 3 Stars

---

## 3. Delivery Directory Hierarchies

Delivery structures are created based on photographer requirements:
* **scenes**: ceremony, reception, portraits folders.
* **chapters**: chapter timeline segment subfolders.
* **highlights**: highlight vs regular divisions.
* **persons**: sorted by resolved person names.
