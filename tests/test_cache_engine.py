import unittest
import os
import datetime
import imagehash
from cache_engine import get_cached_item, set_cached_item, clear_cache

class TestCacheEngine(unittest.TestCase):
    def setUp(self):
        self.image_path = "test_cache_photo.jpg"
        self.metrics = {"scoring_version": 4, "overall_score": 92.5}
        # Clean setup
        clear_cache()

    def tearDown(self):
        clear_cache()

    def test_cache_hit_and_double_mtime_invalidation(self):
        # Initial timestamps
        mtime = 1700000000.0
        xmp_mtime = 1700000005.0
        
        # 1. Store item in cache
        set_cached_item(
            path=self.image_path,
            mtime=mtime,
            xmp_mtime=xmp_mtime,
            sha256="abcde12345",
            phash=imagehash.hex_to_hash("ffffffffffffffff"),
            ratio=1.5,
            timestamp=datetime.datetime.min,
            metrics=self.metrics
        )
        
        # 2. Query cache with identical timestamps (should be a hit!)
        cached = get_cached_item(self.image_path, mtime, xmp_mtime)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["sha256"], "abcde12345")
        self.assertEqual(cached["metrics"]["overall_score"], 92.5)
        
        # 3. Query cache after image file mtime changes (should be a cache miss!)
        cached_miss_1 = get_cached_item(self.image_path, mtime + 10.0, xmp_mtime)
        self.assertIsNone(cached_miss_1)
        
        # 4. Query cache after XMP file mtime changes (should be a cache miss!)
        cached_miss_2 = get_cached_item(self.image_path, mtime, xmp_mtime + 5.0)
        self.assertIsNone(cached_miss_2)

if __name__ == '__main__':
    unittest.main()
