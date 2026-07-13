import unittest
import os
import sys
import tempfile
import shutil

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine
from identity_graph import IdentityGraph

class TestIdentityGraph(unittest.TestCase):
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

    def test_add_face_creates_new_cluster(self):
        graph = IdentityGraph()
        face = {
            "bbox": [0, 0, 50, 50],
            "confidence": 0.95,
            "embedding": [1.0] * 512
        }
        cid = graph.add_face("/path/to/img.jpg", face)
        self.assertEqual(cid, 0)
        self.assertIn(0, graph.clusters)
        self.assertEqual(len(graph.clusters[0]["faces"]), 1)

    def test_add_face_joins_existing_cluster(self):
        graph = IdentityGraph()
        face1 = {
            "bbox": [0, 0, 50, 50],
            "confidence": 0.95,
            "embedding": [1.0] + [0.0]*511
        }
        graph.add_face("/path/to/img.jpg", face1)
        
        # Add similar face (cosine similarity = 1.0)
        face2 = {
            "bbox": [10, 10, 50, 50],
            "confidence": 0.96,
            "embedding": [1.0] + [0.0]*511
        }
        cid = graph.add_face("/path/to/img2.jpg", face2)
        self.assertEqual(cid, 0)
        self.assertEqual(len(graph.clusters[0]["faces"]), 2)

    def test_merge_identities(self):
        graph = IdentityGraph()
        # Add two dissimilar faces to create two clusters
        face1 = {
            "face_id": 1,
            "bbox": [0, 0, 50, 50],
            "confidence": 0.95,
            "embedding": [1.0] + [0.0]*511
        }
        face2 = {
            "face_id": 2,
            "bbox": [0, 0, 50, 50],
            "confidence": 0.95,
            "embedding": [0.0, 1.0] + [0.0]*510
        }
        cid1 = graph.add_face("/path/to/img1.jpg", face1)
        cid2 = graph.add_face("/path/to/img2.jpg", face2)
        self.assertEqual(cid1, 0)
        self.assertEqual(cid2, 1)

        graph.merge_identities(0, 1, "Testing merge")
        self.assertEqual(graph.clusters[1]["status"], "merged")
        self.assertEqual(len(graph.clusters[0]["faces"]), 2)

        # Check DB history log
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        cursor = conn.execute("SELECT action_type, details FROM cluster_history")
        rows = cursor.fetchall()
        conn.close()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], "merge")

if __name__ == '__main__':
    unittest.main()
