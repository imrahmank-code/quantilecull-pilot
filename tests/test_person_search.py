import unittest
import os
import sys
import tempfile
import shutil

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine
import identity_resolution

class TestPersonSearch(unittest.TestCase):
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

    def test_search_photos_by_person(self):
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/path/img1.jpg", 1.0))
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/path/img2.jpg", 1.0))
        conn.execute("INSERT INTO identity_clusters (cluster_id) VALUES (?)", (10,))
        conn.execute("""
            INSERT INTO identity_faces (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (10, "/path/img1.jpg", 0, 0, 50, 50, 0.9))
        conn.commit()
        conn.close()

        pid = identity_resolution.create_person("Alice")
        identity_resolution.associate_cluster_to_person(10, pid)

        photos = identity_resolution.search_photos_by_person(pid)
        self.assertEqual(photos, ["/path/img1.jpg"])

if __name__ == '__main__':
    unittest.main()
