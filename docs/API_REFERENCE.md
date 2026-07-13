# Public API Specification — QuantileCull V1.2

This document specifies the public API contracts introduced in Feature Pack 1. It serves as the official integration guide for developers contributing to future Feature Packs.

---

## 1. raw_engine

Provides utilities to identify and decode RAW photographic formats.

### `is_raw_file(file_path: str) -> bool`
* **Purpose**: Identifies whether a file extension matches the supported RAW list.
* **Parameters**:
  * `file_path` (str): Absolute file system path to the image.
* **Return Type**: `bool` (True if RAW, False otherwise).
* **Exceptions**: None.
* **Thread Safety**: Fully thread-safe (stateless file extension check).

### `load_raw_image(file_path: str, half_size: bool = False) -> Optional[np.ndarray]`
* **Purpose**: Decodes and postprocesses a RAW image file into a NumPy RGB array.
* **Parameters**:
  * `file_path` (str): Absolute file system path to the RAW file.
  * `half_size` (bool): Downsamples RAW raw-bayer interpolation by 50% for fast quality checks.
* **Return Type**: `Optional[np.ndarray]` (NumPy array of shape `(H, W, 3)` or `None` if corrupted/unsupported).
* **Exceptions**: Catch-all for `rawpy.LibRawError` (logged via telemetry, returns `None`).
* **Thread Safety**: Fully thread-safe (handles independent memory maps).

```python
from raw_engine import is_raw_file, load_raw_image

if is_raw_file("DSC02381.ARW"):
    image_data = load_raw_image("DSC02381.ARW", half_size=True)
    if image_data is not None:
        print("RAW decoded shape:", image_data.shape)
```

---

## 2. preview_engine

Extracts embedded previews from RAW assets to bypass full raw-bayer rendering bottlenecks.

### `extract_raw_preview(file_path: str) -> Optional[bytes]`
* **Purpose**: Retrieves the original embedded high-resolution JPEG byte stream directly from the RAW file.
* **Parameters**:
  * `file_path` (str): Absolute path to the RAW file.
* **Return Type**: `Optional[bytes]` (JPEG byte stream or `None` if missing/corrupt).
* **Exceptions**: Handles file access or decoding exceptions (returns `None`).
* **Thread Safety**: Fully thread-safe.

### `generate_raw_thumbnail(file_path: str, max_dim: int) -> Optional[bytes]`
* **Purpose**: Generates a downscaled JPEG thumbnail byte stream from the embedded preview.
* **Parameters**:
  * `file_path` (str): Absolute path to the RAW file.
  * `max_dim` (int): Maximum bounding box dimension for downscaling.
* **Return Type**: `Optional[bytes]` (Resized JPEG byte stream or `None`).
* **Exceptions**: Handled internally, logs warning, returns `None`.
* **Thread Safety**: Fully thread-safe.

```python
from preview_engine import extract_raw_preview, generate_raw_thumbnail

# Streaming a 400px thumbnail byte array for UI culling grid
thumb_bytes = generate_raw_thumbnail("session_01.CR3", max_dim=400)
```

---

## 3. metadata_engine

Reads EXIF exposure values and camera metrics.

### `extract_raw_metadata(file_path: str) -> dict`
* **Purpose**: Parses EXIF headers for camera, lens, and exposure tags.
* **Parameters**:
  * `file_path` (str): Absolute path to the RAW file.
* **Return Type**: `dict` containing camera make, model, lens, ISO, shutter speed, and aperture.
* **Exceptions**: Logs parse warnings and returns a dict with default `"Unknown"` values if parsing fails.
* **Thread Safety**: Fully thread-safe.

```python
from metadata_engine import extract_raw_metadata

meta = extract_raw_metadata("shoot_01.NEF")
print(f"Shot on {meta['camera_model']} using {meta['lens']}")
```

---

## 4. xmp_engine

Handles read/write operations on Adobe XMP sidecar files.

### `read_xmp_metadata(image_path: str) -> dict`
* **Purpose**: Reads star ratings, color labels, and reject flags from the `.xmp` sidecar.
* **Parameters**:
  * `image_path` (str): Absolute path to the main photo.
* **Return Type**: `dict` (`{"rating": int, "label": str, "rejected": bool, "keywords": list}`)
* **Exceptions**: Returns empty defaults if the `.xmp` file does not exist.
* **Thread Safety**: Fully thread-safe.

### `write_xmp_metadata(image_path: str, rating: int = 0, label: str = "", rejected: bool = False) -> bool`
* **Purpose**: Updates or creates an `.xmp` sidecar file, preserving unrelated tags.
* **Parameters**:
  * `image_path` (str): Absolute path to the main photo.
  * `rating` (int): 0 to 5.
  * `label` (str): Lightroom label color class name.
  * `rejected` (bool): Reject flag.
* **Return Type**: `bool` (True if success, False otherwise).
* **Exceptions**: Logs to stderr and returns False if file is write-locked or read-only.
* **Thread Safety**: Thread-safe (protected via database locking when syncing cached schemas).

```python
from xmp_engine import write_xmp_metadata

# Write a 5-star rating and Green label to XMP sidecar
success = write_xmp_metadata("portrait.CR2", rating=5, label="Green", rejected=False)
```

---

## 5. cache_engine

Manages the SQLite database metadata cache.

### `get_cached_item(path: str, mtime: float, xmp_mtime: float) -> Optional[dict]`
* **Purpose**: Fetches cached image dimensions and quality metrics if both mtimes match the database values.
* **Parameters**:
  * `path` (str): Absolute path to the image.
  * `mtime` (float): Modification timestamp of the image.
  * `xmp_mtime` (float): Modification timestamp of the XMP sidecar.
* **Return Type**: `Optional[dict]` (Cached item record or `None` on cache miss).
* **Exceptions**: Returns `None` on DB read query failures.
* **Thread Safety**: Thread-safe (uses Python thread-local storage for SQLite connections).

### `set_cached_item(path: str, mtime: float, xmp_mtime: float, sha256: str, phash: Optional[object], ratio: float, timestamp: Optional[object], metrics: dict) -> bool`
* **Purpose**: Caches image characteristics and computer vision results in SQLite database.
* **Parameters**:
  * `path` (str): Absolute path to the image.
  * `mtime` (float): Modification timestamp of the image.
  * `xmp_mtime` (float): Modification timestamp of the XMP sidecar.
  * `sha256` (str): SHA-256 file checksum.
  * `metrics` (dict): Quality score dictionary.
* **Return Type**: `bool` (True if cached successfully, False otherwise).
* **Exceptions**: Catches SQLite exceptions and writes logs via telemetry.
* **Thread Safety**: Thread-safe (SQLite connection pool write-locked).
