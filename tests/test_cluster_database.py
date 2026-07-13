import unittest
import os
import sys
import tempfile
import shutil
import sqlite3

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine

class TestClusterDatabase(unittest.TestCase):
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

    def test_tables_creation(self):
        """Verify that all new SQLite clustering tables are created correctly."""
        conn = sqlite3.connect(self._test_db)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        self.assertIn("identity_clusters", tables)
        self.assertIn("identity_faces", tables)
        self.assertIn("cluster_history", tables)
        self.assertIn("cluster_statistics", tables)

    def test_cascade_delete_image(self):
        """Deleting a parent record in image_cache should delete rows in identity_faces via ON DELETE CASCADE."""
        conn = sqlite3.connect(self._test_db)
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON;")
        
        # Insert parent image
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/path/img.jpg", 1.0))
        # Insert cluster
        conn.execute("INSERT INTO identity_clusters (cluster_id) VALUES (?)", (10,))
        # Insert identity face
        conn.execute("""
            INSERT INTO identity_faces (cluster_id, file_path, bbox_x) 
            VALUES (?, ?, ?)
        """, (10, "/path/img.jpg", 100))
        conn.commit()

        # Delete image
        conn.execute("DELETE FROM image_cache WHERE file_path=?", ("/path/img.jpg",))
        conn.commit()

        cursor = conn.execute("SELECT count(*) FROM identity_faces")
        count = cursor.fetchone()[0]
        conn.close()
        
        self.assertEqual(count, 0)

if __name__ == '__main__':
    unittest.main()
