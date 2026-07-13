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
import identity_resolution

class TestPersonDb(unittest.TestCase):
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

    def test_schema_migration_applied(self):
        """Verify that the person_id foreign key column exists in identity_clusters."""
        conn = sqlite3.connect(self._test_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(identity_clusters)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        self.assertIn("person_id", columns)

    def test_associate_cluster_to_person(self):
        # Insert parents
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        conn.execute("INSERT INTO image_cache (file_path, mtime) VALUES (?, ?)", ("/path/img.jpg", 1.0))
        conn.execute("INSERT INTO identity_clusters (cluster_id) VALUES (?)", (10,))
        # Insert face
        conn.execute("""
            INSERT INTO identity_faces (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (10, "/path/img.jpg", 10, 20, 100, 120, 0.98))
        conn.commit()
        conn.close()

        pid = identity_resolution.create_person("Alice")
        identity_resolution.associate_cluster_to_person(10, pid)

        # Check mapping and statistics
        person = identity_resolution.get_person(pid)
        self.assertEqual(person["face_count"], 1)
        self.assertEqual(person["key_face_path"], "/path/img.jpg")
        self.assertEqual(person["key_face_bbox"], [10, 20, 100, 120])

    def test_timeline_mapping(self):
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        # Enable timestamp
        conn.execute("INSERT INTO image_cache (file_path, mtime, timestamp) VALUES (?, ?, ?)", ("/path/img1.jpg", 1.0, 1000.0))
        conn.execute("INSERT INTO image_cache (file_path, mtime, timestamp) VALUES (?, ?, ?)", ("/path/img2.jpg", 1.0, 2000.0))
        conn.execute("INSERT INTO identity_clusters (cluster_id) VALUES (?)", (10,))
        # Faces
        conn.execute("""
            INSERT INTO identity_faces (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (10, "/path/img1.jpg", 0, 0, 50, 50, 0.9))
        conn.execute("""
            INSERT INTO identity_faces (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (10, "/path/img2.jpg", 0, 0, 50, 50, 0.95))
        conn.commit()
        conn.close()

        pid = identity_resolution.create_person("Alice")
        identity_resolution.associate_cluster_to_person(10, pid)

        timeline = identity_resolution.get_identity_timeline(pid)
        self.assertEqual(len(timeline), 2)
        # Should be sorted chronologically by timestamp
        self.assertEqual(timeline[0]["file_path"], "/path/img1.jpg")
        self.assertEqual(timeline[1]["file_path"], "/path/img2.jpg")

if __name__ == '__main__':
    unittest.main()
