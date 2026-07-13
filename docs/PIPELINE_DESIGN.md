# Analysis Pipeline Design — QuantileCull V1.2

This document specifies the pipeline design, preprocessing rules, topological sorting resolution, and output schemas of the QuantileCull V1.2 AI Vision subsystem.

---

## 1. Pipeline Execution Flow

When `analysis_pipeline.run_pipeline(image_path, enabled_features)` is invoked:

1. **Format Check & Load**:
   * Inspects extension. If RAW, invokes `raw_engine.load_raw_image` (downsamples by 50% for fast processing).
   * If standard JPEG/PNG, loads via OpenCV and converts to RGB color space.
2. **Execution Sequence Resolution**:
   * Queries the `feature_registry` topological sorter with the requested list of features. Prerequisite tasks (like `FACE_DETECTION` before `FACE_EMBEDDING`) are automatically sorted to run first.
3. **Engine Initialization**:
   * Triggers `ai_engine.initialize()`, preparing providers (DirectML, CUDA, CPU).
4. **Iterative Module Execution**:
   * Evaluates each sorted feature. Crop tensors are resized, normalized, and run through `ai_engine.run_inference`.
5. **Output Aggregation**:
   * Merges all individual module results into the unified JSON analysis schema, logging warning messages if an individual feature fails.

---

## 2. Standard Analysis Object Schema

```json
{
  "ImageInfo": {
    "width": "Integer (Image width)",
    "height": "Integer (Image height)",
    "format": "String (e.g. CR3, NEF, JPG)"
  },
  "Quality": {
    "overall_score": "Float (Combined rating)",
    "sharpness": "Float (Sharpness percentage)",
    "exposure": "Float (Exposure rating)",
    "contrast": "Float (Contrast percentage)"
  },
  "Faces": [
    {
      "face_id": "Integer (Unique id)",
      "bbox": "List [X, Y, W, H]",
      "confidence": "Float (Bounding box score)",
      "embedding": "List [512 floats]"
    }
  ],
  "Eyes": {
    "left_eye_open": "Boolean",
    "right_eye_open": "Boolean"
  },
  "Smile": {
    "is_smiling": "Boolean"
  },
  "People": "List (Future expansion)",
  "Scene": {
    "category": "String (Scene label)"
  },
  "Objects": "List (Future expansion)",
  "Metadata": "Dict (Camera EXIF details)",
  "Scores": "Dict (Sub-scores)",
  "Warnings": "List (Execution exception logs)"
}
```
