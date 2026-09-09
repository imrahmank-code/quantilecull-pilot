"""
Unit tests for FastPreviewEngine (Pillar 2).
Tests Dual-Ring (Active/Speculative) caching, memory thresholds & eviction,
double-mtime cache invalidation, SIMD preview scaling, and background pre-warming.
"""

import unittest
from datetime import datetime
import os
import sys
import tempfile
import time
import shutil

import cv2
import numpy as np

# Ensure repository root is on sys.path
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from fast_preview_engine import (
    FastPreviewEngine,
    DualRingCache,
    PreviewResult
)


class TestFastPreviewEngine(unittest.TestCase):
    """Comprehensive test suite for FastPreviewEngine and DualRingCache."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = FastPreviewEngine(
            max_memory_mb=16,       # 16 MB memory budget for tests
            ring_a_capacity=5,      # Small Ring A capacity for testing eviction
            worker_threads=2
        )

    def tearDown(self):
        self.engine.shutdown(wait=True)
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_sample_image(self, filename: str, width: int = 800, height: int = 600, color=(100, 150, 200)) -> str:
        """Helper to generate a real JPEG image file on disk."""
        path = os.path.join(self.test_dir, filename)
        img = np.full((height, width, 3), color, dtype=np.uint8)
        cv2.imwrite(path, img)
        return path

    def test_dual_ring_cache_promotion(self):
        """Verify Ring B speculative items are promoted to Ring A upon access."""
        cache = DualRingCache(max_bytes=1024 * 1024, ring_a_capacity=5)

        dummy_bytes = b"JPEG_DATA_DUMMY_12345"
        item = PreviewResult(
            path="/photos/spec1.jpg",
            data=dummy_bytes,
            width=800,
            height=600,
            format="jpeg",
            latency_ms=10.0,
            source="draft_raw",
            mtime=1000.0
        )

        # Place into Ring B
        cache.put_speculative("/photos/spec1.jpg", item)
        self.assertIn("/photos/spec1.jpg", cache.ring_b)
        self.assertNotIn("/photos/spec1.jpg", cache.ring_a)

        # First read: hits Ring B and promotes to Ring A
        res1 = cache.get("/photos/spec1.jpg", current_mtime=1000.0)
        self.assertIsNotNone(res1)
        self.assertEqual(res1.source, "cache_ring_b")
        self.assertIn("/photos/spec1.jpg", cache.ring_a)
        self.assertNotIn("/photos/spec1.jpg", cache.ring_b)

        # Second read: hits Ring A
        res2 = cache.get("/photos/spec1.jpg", current_mtime=1000.0)
        self.assertIsNotNone(res2)
        self.assertEqual(res2.source, "cache_ring_a")

    def test_ring_a_capacity_demotion_to_ring_b(self):
        """Verify that overflowing Ring A capacity demotes oldest active item to Ring B."""
        cache = DualRingCache(max_bytes=1024 * 1024, ring_a_capacity=2)

        for i in range(3):
            p = f"/photos/img_{i}.jpg"
            item = PreviewResult(
                path=p,
                data=b"DATA" * 50,
                width=100,
                height=100,
                format="jpeg",
                latency_ms=1.0,
                source="embedded_jpeg",
                mtime=100.0 + i
            )
            cache.put_active(p, item)

        # Ring A capacity is 2. The first item (img_0) should have been demoted to Ring B
        self.assertEqual(len(cache.ring_a), 2)
        self.assertIn("/photos/img_1.jpg", cache.ring_a)
        self.assertIn("/photos/img_2.jpg", cache.ring_a)
        self.assertIn("/photos/img_0.jpg", cache.ring_b)

    def test_memory_budget_eviction(self):
        """Verify speculative Ring B frames are evicted before active Ring A frames when over budget."""
        # Budget: 500 bytes
        cache = DualRingCache(max_bytes=500, ring_a_capacity=5)

        # Active item: 200 bytes
        item_active = PreviewResult(
            path="/photos/active.jpg",
            data=b"X" * 200,
            width=100,
            height=100,
            format="jpeg",
            latency_ms=1.0,
            source="draft_raw",
            mtime=100.0
        )
        cache.put_active("/photos/active.jpg", item_active)

        # Speculative item 1: 200 bytes (Total: 400 bytes, under 500 budget)
        item_spec1 = PreviewResult(
            path="/photos/spec1.jpg",
            data=b"Y" * 200,
            width=100,
            height=100,
            format="jpeg",
            latency_ms=1.0,
            source="draft_raw",
            mtime=100.0
        )
        cache.put_speculative("/photos/spec1.jpg", item_spec1)

        self.assertEqual(cache.current_bytes, 400)
        self.assertIn("/photos/spec1.jpg", cache.ring_b)

        # Speculative item 2: 200 bytes (Total would be 600, exceeding 500 budget)
        item_spec2 = PreviewResult(
            path="/photos/spec2.jpg",
            data=b"Z" * 200,
            width=100,
            height=100,
            format="jpeg",
            latency_ms=1.0,
            source="draft_raw",
            mtime=100.0
        )
        cache.put_speculative("/photos/spec2.jpg", item_spec2)

        # Memory limit enforcement should evict oldest speculative item (spec1)
        self.assertLessEqual(cache.current_bytes, 500)
        self.assertNotIn("/photos/spec1.jpg", cache.ring_b)
        self.assertIn("/photos/spec2.jpg", cache.ring_b)
        # Active item in Ring A must remain intact!
        self.assertIn("/photos/active.jpg", cache.ring_a)

    def test_double_mtime_invalidation(self):
        """Verify cache invalidation when the image file or its companion XMP file is modified."""
        img_path = self._create_sample_image("wedding_001.jpg", width=400, height=300)
        xmp_path = os.path.splitext(img_path)[0] + ".xmp"

        with open(xmp_path, "w") as f:
            f.write("<xmp:Rating>3</xmp:Rating>")

        # Initial fetch -> populates cache
        res1 = self.engine.get_preview(img_path)
        self.assertIsNotNone(res1)
        self.assertEqual(res1.source, "standard_image")

        # Second fetch -> cache hit
        res2 = self.engine.get_preview(img_path)
        self.assertIsNotNone(res2)
        self.assertEqual(res2.source, "cache_ring_a")

        # Modify XMP sidecar on disk
        time.sleep(0.05)
        with open(xmp_path, "w") as f:
            f.write("<xmp:Rating>5</xmp:Rating>")
        os.utime(xmp_path, (time.time() + 10, time.time() + 10))

        # Third fetch -> detects XMP mtime difference, invalidates, and re-reads
        res3 = self.engine.get_preview(img_path)
        self.assertIsNotNone(res3)
        self.assertEqual(res3.source, "standard_image")

    def test_simd_thumbnail_generation(self):
        """Verify fast downscaling of large images into standard 400px thumbnails."""
        img_path = self._create_sample_image("ceremony_large.jpg", width=1920, height=1080)

        thumb_bytes = self.engine.generate_thumbnail(img_path, max_dim=400)
        self.assertIsNotNone(thumb_bytes)
        self.assertGreater(len(thumb_bytes), 0)

        # Validate decoded dimensions of thumbnail
        nparr = np.frombuffer(thumb_bytes, np.uint8)
        decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        h, w = decoded.shape[:2]
        self.assertLessEqual(max(h, w), 400)

    def test_background_speculative_prewarming(self):
        """Verify non-blocking background speculative cache pre-warming."""
        paths = [
            self._create_sample_image(f"burst_{i}.jpg", width=200, height=200)
            for i in range(5)
        ]

        # Trigger speculative pre-warming
        self.engine.warm_cache_speculative(paths, max_dim=400)

        # Give background worker thread a moment to process
        time.sleep(0.3)

        stats = self.engine.get_cache_stats()
        self.assertGreater(stats["total_items"], 0)

        # Accessing pre-warmed image should be a cache hit (promoted from Ring B)
        res = self.engine.get_preview(paths[0])
        self.assertIsNotNone(res)
        self.assertIn(res.source, ["cache_ring_a", "cache_ring_b"])

    def test_cache_telemetry_stats(self):
        """Verify accurate reporting of hits, misses, and memory occupancy."""
        img_path = self._create_sample_image("telemetry_test.jpg", width=300, height=300)

        # Initial get (Miss)
        self.engine.get_preview(img_path)
        stats1 = self.engine.get_cache_stats()
        self.assertEqual(stats1["ring_a_count"], 1)
        self.assertGreater(stats1["current_bytes"], 0)

        # Subsequent get (Hit)
        self.engine.get_preview(img_path)
        stats2 = self.engine.get_cache_stats()
        self.assertEqual(stats2["hits"], 1)
        self.assertGreaterEqual(stats2["hit_ratio"], 0.5)


if __name__ == "__main__":
    unittest.main()
