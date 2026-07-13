import unittest
import os
import sys
import tempfile
import shutil

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine

class TestIncrementalClustering(unittest.TestCase):
    def setUp(self):
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

    def test_incremental_clustering_flow(self):
        # Insert parent image records
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/path/img1.jpg", 1.0))
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/path/img2.jpg", 1.0))
        conn.commit()
        conn.close()

        # Update img1 with a face -> creates cluster 1
        faces_img1 = [{
            "bbox": [10, 10, 50, 50],
            "confidence": 0.95,
            "quality": {"sharpness": 80.0, "exposure": 80.0},
            "embedding": [1.0] + [0.0]*511
        }]
        cache_engine.incremental_cluster_update("/path/img1.jpg", faces_img1)
        
        clusters = cache_engine.get_clusters()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["cluster_id"], 1)

        # Update img2 with a very similar face -> joins cluster 1
        faces_img2 = [{
            "bbox": [12, 12, 50, 50],
            "confidence": 0.96,
            "quality": {"sharpness": 82.0, "exposure": 82.0},
            "embedding": [1.0] + [0.0]*511
        }]
        cache_engine.incremental_cluster_update("/path/img2.jpg", faces_img2)

        clusters_updated = cache_engine.get_clusters()
        self.assertEqual(len(clusters_updated), 1)
        self.assertEqual(len(clusters_updated[0]["faces"]), 2)
        self.assertEqual(clusters_updated[0]["faces"][0]["file_path"], "/path/img1.jpg")
        self.assertEqual(clusters_updated[0]["faces"][1]["file_path"], "/path/img2.jpg")

if __name__ == '__main__':
    unittest.main()
