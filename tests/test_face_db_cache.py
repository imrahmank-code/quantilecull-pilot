import unittest
import os
import sys
import tempfile
import shutil
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine

class TestFaceDbCache(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory with a DB file inside
        self._test_dir = tempfile.mkdtemp()
        self._orig_db = cache_engine.DB_FILE
        self._test_db = os.path.join(self._test_dir, 'test_cache.db')
        cache_engine.DB_FILE = self._test_db
        cache_engine._init_cache()

    def tearDown(self):
        cache_engine.DB_FILE = self._orig_db
        try:
            shutil.rmtree(self._test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_face_embeddings_table_created(self):
        """The face_embeddings table should exist after _init_cache."""
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='face_embeddings'")
        tables = cursor.fetchall()
        conn.close()
        self.assertEqual(len(tables), 1)

    def test_set_and_get_face_embeddings(self):
        """Store and retrieve face embeddings including BLOB deserialization."""
        # First, insert a parent record into image_cache
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/test/photo.jpg", 12345.0))
        conn.commit()
        conn.close()

        emb = np.random.randn(512).astype(np.float32)
        faces = [{
            "bbox": [10, 20, 100, 120],
            "confidence": 0.97,
            "quality": {"sharpness": 85.0, "exposure": 72.5},
            "landmarks": {"left_eye": [35, 60], "right_eye": [75, 60]},
            "orientation": {"roll": 1.2, "pitch": -3.5, "yaw": 5.0},
            "embedding": emb.tolist()
        }]
        cache_engine.set_face_embeddings("/test/photo.jpg", faces)
        
        result = cache_engine.get_face_embeddings("/test/photo.jpg")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["bbox"], [10, 20, 100, 120])
        self.assertAlmostEqual(result[0]["confidence"], 0.97, places=2)
        self.assertAlmostEqual(result[0]["quality"]["sharpness"], 85.0, places=1)
        self.assertEqual(len(result[0]["embedding"]), 512)
        np.testing.assert_array_almost_equal(np.array(result[0]["embedding"]), emb, decimal=4)

    def test_clear_cache_wipes_face_embeddings(self):
        """clear_cache should remove all face_embeddings rows."""
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/test/photo.jpg", 12345.0))
        conn.commit()
        conn.close()
        
        faces = [{
            "bbox": [0, 0, 50, 50],
            "confidence": 0.99,
            "quality": {"sharpness": 90.0, "exposure": 80.0},
            "landmarks": {},
            "orientation": {},
            "embedding": [0.1] * 512
        }]
        cache_engine.set_face_embeddings("/test/photo.jpg", faces)
        
        cache_engine.clear_cache()
        result = cache_engine.get_face_embeddings("/test/photo.jpg")
        self.assertEqual(len(result), 0)

    def test_overwrite_face_embeddings(self):
        """set_face_embeddings should replace previous entries for the same path."""
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/test/photo.jpg", 12345.0))
        conn.commit()
        conn.close()

        faces_v1 = [{"bbox": [0, 0, 50, 50], "confidence": 0.8, "quality": {"sharpness": 50, "exposure": 50},
                      "landmarks": {}, "orientation": {}, "embedding": [0.5] * 512}]
        faces_v2 = [
            {"bbox": [10, 10, 60, 60], "confidence": 0.95, "quality": {"sharpness": 88, "exposure": 75},
             "landmarks": {}, "orientation": {}, "embedding": [0.9] * 512},
            {"bbox": [200, 200, 80, 80], "confidence": 0.90, "quality": {"sharpness": 70, "exposure": 60},
             "landmarks": {}, "orientation": {}, "embedding": [0.3] * 512}
        ]
        cache_engine.set_face_embeddings("/test/photo.jpg", faces_v1)
        cache_engine.set_face_embeddings("/test/photo.jpg", faces_v2)
        result = cache_engine.get_face_embeddings("/test/photo.jpg")
        self.assertEqual(len(result), 2)

if __name__ == '__main__':
    unittest.main()
