import unittest
import os
import sys
import shutil
import tempfile
import time
from unittest.mock import MagicMock, patch

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)

import image_analyzer
import cache_engine
import raw_engine
import preview_engine
import xmp_engine
import recovery
import app

class TestCullingIntegration(unittest.TestCase):
    def setUp(self):
        # Create temp folder for scanning
        self.test_dir = tempfile.mkdtemp()
        cache_engine.clear_cache()

    def tearDown(self):
        # Clean up files
        shutil.rmtree(self.test_dir, ignore_errors=True)
        cache_engine.clear_cache()

    @patch('raw_engine.rawpy.imread')
    def test_end_to_end_culling_pipeline(self, mock_imread):
        import rawpy
        import numpy as np
        mock_raw = MagicMock()
        mock_raw.postprocess.return_value = np.zeros((100, 150, 3), dtype=np.uint8)
        
        def imread_side_effect(filename, *args, **kwargs):
            if "corrupt" in filename:
                raise rawpy.LibRawError("Input/output error")
            mock_context = MagicMock()
            mock_context.__enter__.return_value = mock_raw
            return mock_context
            
        mock_imread.side_effect = imread_side_effect
        
        # 1. Create a mock RAW photo (CR2)
        raw_path = os.path.join(self.test_dir, "photo_1.CR2")
        with open(raw_path, "wb") as f:
            f.write(b"DUMMY RAW DATA")
            
        # 2. Create a mock companion JPEG
        jpg_path = os.path.join(self.test_dir, "photo_1.JPG")
        with open(jpg_path, "wb") as f:
            f.write(b"DUMMY JPEG DATA")
            
        # 3. Create a mock corrupted RAW file
        corrupt_path = os.path.join(self.test_dir, "photo_corrupt.NEF")
        with open(corrupt_path, "wb") as f:
            f.write(b"CORRUPTED BYTES")

        # Verify RAW detection
        self.assertTrue(raw_engine.is_raw_file(raw_path))
        self.assertTrue(raw_engine.is_raw_file(corrupt_path))
        self.assertFalse(raw_engine.is_raw_file(jpg_path))
        
        # Verify RAW loading (corrupted returns None, valid returns image shape)
        self.assertIsNone(raw_engine.load_raw_image(corrupt_path))
        img = raw_engine.load_raw_image(raw_path)
        self.assertIsNotNone(img)
        self.assertEqual(img.shape, (100, 150, 3))
        
        # Verify metadata extraction (non-destructive fallback check)
        meta = xmp_engine.read_xmp_metadata(raw_path)
        self.assertEqual(meta["rating"], 0)
        
        # Write some XMP tags
        success = xmp_engine.write_xmp_metadata(raw_path, rating=4, label="Blue", rejected=False)
        self.assertTrue(success)
        
        # Verify they are read correctly
        meta = xmp_engine.read_xmp_metadata(raw_path)
        self.assertEqual(meta["rating"], 4)
        self.assertEqual(meta["label"], "Blue")
        
        image_paths, scan_diag = image_analyzer.scan_directory_for_images(self.test_dir)
        self.assertEqual(len(image_paths), 3)  # Scan finds all files with matching extensions
        
        # Verify double-mtime cache functionality
        mtime = os.path.getmtime(raw_path)
        xmp_mtime = os.path.getmtime(xmp_engine.get_xmp_path(raw_path))
        
        # Cache item
        import datetime
        cache_engine.set_cached_item(
            path=raw_path,
            mtime=mtime,
            xmp_mtime=xmp_mtime,
            sha256="hash123",
            phash=None,
            ratio=1.5,
            timestamp=datetime.datetime.now(),
            metrics={"overall_score": 85.0, "xmp_rating": 4, "xmp_label": "Blue"}
        )
        
        # Check cache hit
        cached = cache_engine.get_cached_item(raw_path, mtime, xmp_mtime)
        self.assertIsNotNone(cached)
        self.assertEqual(cached["metrics"]["xmp_rating"], 4)
        
        # Invalidate cache by modifying XMP file
        time.sleep(0.1) # Ensure time difference
        xmp_path = xmp_engine.get_xmp_path(raw_path)
        with open(xmp_path, "a") as f:
            f.write("\n")
        new_xmp_mtime = os.path.getmtime(xmp_path)
        
        # Query cache with new XMP mtime -> should miss
        cached_miss = cache_engine.get_cached_item(raw_path, mtime, new_xmp_mtime)
        self.assertIsNone(cached_miss)
        
        # Verify recovery checkpointing
        mgr = recovery.RecoveryManager()
        mgr.save_checkpoint("job_id_123", ["p1", "p2"], ["p3"], 80, 5, self.test_dir)
        chk = mgr.load_checkpoint()
        self.assertIsNotNone(chk)
        self.assertEqual(chk["target_path"], self.test_dir)
        self.assertEqual(chk["processed_count"], 2)
        
        mgr.clear_checkpoint()
        self.assertIsNone(mgr.load_checkpoint())

if __name__ == '__main__':
    unittest.main()
