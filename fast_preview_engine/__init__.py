"""
FastPreviewEngine - Pillar 2 of QuantileCull Next-Iteration Architecture
High-throughput RAW preview and thumbnail generation engine with hardware SIMD acceleration
and Dual-Ring (Active/Speculative) LRU memory caching.
"""

from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
from typing import List, Dict, Optional, Tuple, Any, Union
import concurrent.futures
import os
import threading
import time

import cv2
import numpy as np
from PIL import Image
import rawpy


@dataclass
class PreviewResult:
    """Represents a generated or cached preview frame."""
    path: str
    data: bytes
    width: int
    height: int
    format: str  # "jpeg" | "raw_rgb"
    latency_ms: float
    source: str  # "cache_ring_a" | "cache_ring_b" | "embedded_jpeg" | "draft_raw"
    mtime: float
    xmp_mtime: Optional[float] = None
    byte_size: int = 0

    def __post_init__(self):
        if not self.byte_size and self.data:
            self.byte_size = len(self.data)


class DualRingCache:
    """
    Thread-safe Dual-Ring LRU Memory Cache:
    - Ring A (Foreground Active): Stores the active viewport cluster and adjacent frames.
    - Ring B (Background Speculative): Stores pre-warmed upcoming images.
    Enforces strict memory footprint bounds (evicting speculative frames first).
    """

    def __init__(self, max_bytes: int = 512 * 1024 * 1024, ring_a_capacity: int = 25):
        self.max_bytes: int = max_bytes
        self.ring_a_capacity: int = ring_a_capacity
        self.current_bytes: int = 0

        self.ring_a: OrderedDict[str, PreviewResult] = OrderedDict()
        self.ring_b: OrderedDict[str, PreviewResult] = OrderedDict()
        self._lock = threading.RLock()

        self.hits: int = 0
        self.misses: int = 0

    def get(self, path: str, current_mtime: float, current_xmp_mtime: Optional[float] = None) -> Optional[PreviewResult]:
        """
        Retrieves a cached item if present and validates against disk mtimes.
        Promotes hits to Ring A (most recently used).
        """
        with self._lock:
            # Check Ring A (Active)
            if path in self.ring_a:
                item = self.ring_a[path]
                if self._is_stale(item, current_mtime, current_xmp_mtime):
                    self._remove_item(path, "ring_a")
                    self.misses += 1
                    return None
                # Mark as MRU in Ring A
                self.ring_a.move_to_end(path)
                self.hits += 1
                return PreviewResult(
                    path=item.path,
                    data=item.data,
                    width=item.width,
                    height=item.height,
                    format=item.format,
                    latency_ms=0.0,
                    source="cache_ring_a",
                    mtime=item.mtime,
                    xmp_mtime=item.xmp_mtime,
                    byte_size=item.byte_size
                )

            # Check Ring B (Speculative)
            if path in self.ring_b:
                item = self.ring_b[path]
                if self._is_stale(item, current_mtime, current_xmp_mtime):
                    self._remove_item(path, "ring_b")
                    self.misses += 1
                    return None
                # Promote from Ring B to Ring A
                self._remove_item(path, "ring_b")
                self._put_ring_a(path, item)
                self.hits += 1
                return PreviewResult(
                    path=item.path,
                    data=item.data,
                    width=item.width,
                    height=item.height,
                    format=item.format,
                    latency_ms=0.0,
                    source="cache_ring_b",
                    mtime=item.mtime,
                    xmp_mtime=item.xmp_mtime,
                    byte_size=item.byte_size
                )

            self.misses += 1
            return None

    def put_active(self, path: str, item: PreviewResult) -> None:
        """Stores a freshly decoded preview directly into Ring A."""
        with self._lock:
            # Invalidate any existing entries
            self.invalidate(path)
            self._put_ring_a(path, item)
            self._enforce_memory_limit()

    def put_speculative(self, path: str, item: PreviewResult) -> None:
        """Stores an asynchronously pre-warmed preview into Ring B."""
        with self._lock:
            if path in self.ring_a or path in self.ring_b:
                return  # Do not demote or overwrite active frames
            self.ring_b[path] = item
            self.current_bytes += item.byte_size
            self._enforce_memory_limit()

    def invalidate(self, path: str) -> bool:
        """Evicts a specific path from both cache rings."""
        with self._lock:
            removed_a = self._remove_item(path, "ring_a")
            removed_b = self._remove_item(path, "ring_b")
            return removed_a or removed_b

    def clear(self) -> None:
        """Wipes all cached items and resets memory counters."""
        with self._lock:
            self.ring_a.clear()
            self.ring_b.clear()
            self.current_bytes = 0

    def _put_ring_a(self, path: str, item: PreviewResult) -> None:
        """Inserts an item into Ring A, demoting the oldest item to Ring B if capacity is exceeded."""
        self.ring_a[path] = item
        self.current_bytes += item.byte_size

        if len(self.ring_a) > self.ring_a_capacity:
            oldest_path, oldest_item = self.ring_a.popitem(last=False)
            # Demote oldest active frame to Ring B
            self.ring_b[oldest_path] = oldest_item

    def _remove_item(self, path: str, ring_name: str) -> bool:
        """Removes an item from a specific ring and decrements memory size."""
        ring = self.ring_a if ring_name == "ring_a" else self.ring_b
        if path in ring:
            item = ring.pop(path)
            self.current_bytes = max(0, self.current_bytes - item.byte_size)
            return True
        return False

    def _enforce_memory_limit(self) -> None:
        """Evicts speculative Ring B items first, then oldest Ring A items if over budget."""
        while self.current_bytes > self.max_bytes and self.ring_b:
            oldest_path, oldest_item = self.ring_b.popitem(last=False)
            self.current_bytes = max(0, self.current_bytes - oldest_item.byte_size)

        while self.current_bytes > self.max_bytes and self.ring_a:
            oldest_path, oldest_item = self.ring_a.popitem(last=False)
            self.current_bytes = max(0, self.current_bytes - oldest_item.byte_size)

    @staticmethod
    def _is_stale(item: PreviewResult, current_mtime: float, current_xmp_mtime: Optional[float]) -> bool:
        """Checks if the file or its companion XMP has been modified on disk."""
        if abs(item.mtime - current_mtime) > 1e-4:
            return True
        if current_xmp_mtime is not None and item.xmp_mtime is not None:
            if abs(item.xmp_mtime - current_xmp_mtime) > 1e-4:
                return True
        return False

    def stats(self) -> Dict[str, Any]:
        """Returns diagnostic metrics on cache occupancy and hit rates."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_ratio = (self.hits / total_requests) if total_requests > 0 else 0.0
            return {
                "ring_a_count": len(self.ring_a),
                "ring_b_count": len(self.ring_b),
                "total_items": len(self.ring_a) + len(self.ring_b),
                "current_bytes": self.current_bytes,
                "current_mb": round(self.current_bytes / (1024 * 1024), 2),
                "max_mb": round(self.max_bytes / (1024 * 1024), 2),
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio": round(hit_ratio, 4)
            }


class FastPreviewEngine:
    """
    High-Performance RAW Preview Engine with SIMD Hardware Acceleration,
    Direct Embedded JPEG Extraction, and Dual-Ring Asynchronous Pre-Warming.
    """

    def __init__(
        self,
        max_memory_mb: int = 512,
        ring_a_capacity: int = 25,
        worker_threads: int = 2
    ):
        """
        Initialize the fast preview engine.

        Args:
            max_memory_mb: Maximum RAM allocation in megabytes.
            ring_a_capacity: Number of foreground active cluster images.
            worker_threads: Thread count for background pre-warming.
        """
        self.max_memory_bytes = max_memory_mb * 1024 * 1024
        self.cache = DualRingCache(
            max_bytes=self.max_memory_bytes,
            ring_a_capacity=ring_a_capacity
        )
        self.worker_threads = worker_threads
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.worker_threads,
            thread_name_prefix="FastPreviewWorker"
        )
        self._pending_futures: Dict[str, concurrent.futures.Future] = {}
        self._lock = threading.Lock()

    def get_preview(
        self,
        path: str,
        max_dim: int = 2048,
        prioritize_active: bool = True
    ) -> Optional[PreviewResult]:
        """
        Retrieves an optimized high-resolution JPEG preview for the given image.
        Uses Dual-Ring cache if available, or decodes via fast embedded SIMD pipeline.

        Args:
            path: Absolute filesystem path to the RAW or standard image file.
            max_dim: Maximum width or height of the output preview in pixels.
            prioritize_active: Whether to promote this item into foreground Ring A.

        Returns:
            PreviewResult containing encoded JPEG bytes and metadata, or None if decode fails.
        """
        if not os.path.exists(path):
            return None

        mtime = os.path.getmtime(path)
        xmp_path = self._resolve_xmp_path(path)
        xmp_mtime = os.path.getmtime(xmp_path) if xmp_path and os.path.exists(xmp_path) else None

        # 1. Fast Cache Check
        cached = self.cache.get(path, current_mtime=mtime, current_xmp_mtime=xmp_mtime)
        if cached is not None:
            return cached

        # 2. Decode via Accelerated Pipeline
        t0 = time.perf_counter()
        preview_bytes, width, height, source = self._extract_and_scale(path, max_dim)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        if not preview_bytes:
            return None

        result = PreviewResult(
            path=path,
            data=preview_bytes,
            width=width,
            height=height,
            format="jpeg",
            latency_ms=latency_ms,
            source=source,
            mtime=mtime,
            xmp_mtime=xmp_mtime
        )

        # 3. Store in Cache
        if prioritize_active:
            self.cache.put_active(path, result)
        else:
            self.cache.put_speculative(path, result)

        return result

    def generate_thumbnail(self, path: str, max_dim: int = 400) -> Optional[bytes]:
        """
        Generates a lightweight downscaled JPEG thumbnail (e.g. 400px) optimized for grid view.
        Leverages fast preview extraction and OpenCV SIMD area downsampling.

        Args:
            path: Filepath to image.
            max_dim: Maximum dimension (default 400px).

        Returns:
            Raw JPEG bytes or None.
        """
        # If full preview is already in cache, scale directly from memory
        preview = self.get_preview(path, max_dim=max_dim, prioritize_active=False)
        if not preview or not preview.data:
            return None

        if max(preview.width, preview.height) <= max_dim:
            return preview.data

        # Downscale using OpenCV SIMD INTER_AREA
        nparr = np.frombuffer(preview.data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return None

        h, w = img.shape[:2]
        scale = max_dim / max(h, w)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))

        # Hardware-accelerated SIMD resize
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        success, encoded = cv2.imencode('.jpg', resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        return encoded.tobytes() if success else None

    def warm_cache_speculative(self, paths: List[str], max_dim: int = 2048) -> None:
        """
        Asynchronously warms Ring B cache for upcoming images in a background worker thread.

        Args:
            paths: Ordered list of filepaths to pre-warm.
            max_dim: Preview maximum dimension.
        """
        with self._lock:
            for p in paths:
                if p in self.cache.ring_a or p in self.cache.ring_b:
                    continue
                if p in self._pending_futures and not self._pending_futures[p].done():
                    continue

                fut = self._executor.submit(self._warm_worker_task, p, max_dim)
                self._pending_futures[p] = fut

    def _warm_worker_task(self, path: str, max_dim: int) -> None:
        """Background thread worker to decode and store speculative items."""
        try:
            self.get_preview(path, max_dim=max_dim, prioritize_active=False)
        except Exception:
            pass

    def cancel_pending_speculation(self) -> None:
        """Cancels all queued speculative pre-warm tasks."""
        with self._lock:
            for fut in self._pending_futures.values():
                fut.cancel()
            self._pending_futures.clear()

    def shutdown(self, wait: bool = True) -> None:
        """Terminates background worker threads and cleans up resources."""
        self.cancel_pending_speculation()
        self._executor.shutdown(wait=wait)
        self.cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Retrieves operational telemetry for the preview cache."""
        return self.cache.stats()

    def _extract_and_scale(
        self,
        path: str,
        max_dim: int
    ) -> Tuple[Optional[bytes], int, int, str]:
        """
        Executes fast embedded JPEG extraction or fallback draft decode,
        followed by SIMD-accelerated resizing.
        """
        ext = os.path.splitext(path)[1].lower()
        is_raw = ext in {".cr2", ".cr3", ".nef", ".arw", ".dng", ".orf", ".rw2", ".pef"}

        raw_bytes: Optional[bytes] = None
        source: str = "standard_image"

        if is_raw:
            raw_bytes, source = self._extract_raw_buffer(path)

        if not raw_bytes:
            # Fallback to direct OpenCV/Pillow load
            try:
                img = cv2.imread(path, cv2.IMREAD_COLOR)
                if img is not None:
                    h, w = img.shape[:2]
                    scaled, sw, sh = self._simd_resize_cv2(img, max_dim)
                    success, enc = cv2.imencode('.jpg', scaled, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                    if success:
                        return enc.tobytes(), sw, sh, "standard_image"
            except Exception:
                pass
            return None, 0, 0, "failed"

        # Decode buffer and rescale
        try:
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                h, w = img.shape[:2]
                scaled, sw, sh = self._simd_resize_cv2(img, max_dim)
                success, enc = cv2.imencode('.jpg', scaled, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if success:
                    return enc.tobytes(), sw, sh, source
        except Exception:
            pass

        return None, 0, 0, "failed"

    @staticmethod
    def _extract_raw_buffer(path: str) -> Tuple[Optional[bytes], str]:
        """
        Extracts embedded preview bytes from RAW container via rawpy.
        Falls back to half-size draft demosaicing if no embedded thumb exists.
        """
        try:
            with rawpy.imread(path) as raw:
                try:
                    thumb = raw.extract_thumb()
                    if thumb.format == rawpy.ThumbFormat.JPEG:
                        return thumb.data, "embedded_jpeg"
                    elif thumb.format == rawpy.ThumbFormat.BITMAP:
                        img = Image.fromarray(thumb.data)
                        out = BytesIO()
                        img.save(out, format="JPEG", quality=90)
                        return out.getvalue(), "embedded_bitmap"
                except (rawpy.LibRawNoThumbnailError, rawpy.LibRawUnsupportedThumbnailError):
                    pass

                # Draft demosaicing (half-size fast preview)
                rgb = raw.postprocess(
                    half_size=True,
                    use_camera_wb=True,
                    fast_pct=True,
                    no_auto_bright=True
                )
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                success, enc = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
                if success:
                    return enc.tobytes(), "draft_raw"
        except Exception:
            pass
        return None, "failed"

    @staticmethod
    def _simd_resize_cv2(img: np.ndarray, max_dim: int) -> Tuple[np.ndarray, int, int]:
        """
        Performs hardware SIMD-accelerated resizing via OpenCV.
        Employs INTER_AREA for decimation (preserving sharpness) and INTER_LINEAR for enlargement.
        """
        h, w = img.shape[:2]
        if max(h, w) <= max_dim:
            return img, w, h

        scale = max_dim / max(h, w)
        new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))

        # INTER_AREA maps to SSE4/AVX2 vectorized decimation in OpenCV
        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        return resized, new_w, new_h

    @staticmethod
    def _resolve_xmp_path(photo_path: str) -> Optional[str]:
        """Resolves companion .xmp sidecar path if present."""
        base, _ = os.path.splitext(photo_path)
        candidate1 = base + ".xmp"
        candidate2 = photo_path + ".xmp"
        if os.path.exists(candidate1):
            return candidate1
        if os.path.exists(candidate2):
            return candidate2
        return None
