import unittest
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import face_cluster_engine

class TestFaceClusterEngine(unittest.TestCase):
    def test_cluster_faces_dbscan(self):
        embeddings = [
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.99, 0.01], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
            np.array([0.01, 0.99], dtype=np.float32)
        ]
        labels = face_cluster_engine.cluster_faces(embeddings, method="dbscan", threshold=0.1, min_samples=2)
        self.assertEqual(len(labels), 4)
        self.assertEqual(labels[0], labels[1])
        self.assertEqual(labels[2], labels[3])
        self.assertNotEqual(labels[0], labels[2])

    def test_cluster_faces_hierarchical(self):
        embeddings = [
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.99, 0.01], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32),
            np.array([0.01, 0.99], dtype=np.float32)
        ]
        labels = face_cluster_engine.cluster_faces(embeddings, method="hierarchical", threshold=0.1)
        self.assertEqual(len(labels), 4)
        self.assertEqual(labels[0], labels[1])
        self.assertEqual(labels[2], labels[3])
        self.assertNotEqual(labels[0], labels[2])

    def test_update_clusters(self):
        existing = {
            0: {
                "cluster_id": 0,
                "average_embedding": [1.0, 0.0],
                "confidence": 1.0,
                "status": "active",
                "faces": [{"embedding": [1.0, 0.0]}]
            }
        }
        new_emb = [np.array([0.98, 0.02], dtype=np.float32)]
        assigned, updated = face_cluster_engine.update_clusters(new_emb, existing, threshold=0.75)
        self.assertEqual(assigned, [0])
        # Centroid is L2 normalized, so it should be near 1.0
        self.assertAlmostEqual(updated[0]["average_embedding"][0], 1.0, places=2)

    def test_merge_clusters(self):
        existing = {
            0: {
                "cluster_id": 0,
                "average_embedding": [1.0, 0.0],
                "faces": [{"embedding": [1.0, 0.0]}]
            },
            1: {
                "cluster_id": 1,
                "average_embedding": [0.0, 1.0],
                "faces": [{"embedding": [0.0, 1.0]}]
            }
        }
        updated = face_cluster_engine.merge_clusters(0, 1, existing)
        self.assertEqual(len(updated[0]["faces"]), 2)
        self.assertEqual(updated[1]["status"], "merged")

    def test_split_cluster(self):
        existing = {
            0: {
                "cluster_id": 0,
                "average_embedding": [1.0, 0.0],
                "faces": [
                    {"face_id": 1, "embedding": [1.0, 0.0]},
                    {"face_id": 2, "embedding": [0.0, 1.0]}
                ]
            }
        }
        updated = face_cluster_engine.split_cluster(0, [2], existing)
        self.assertEqual(len(updated[0]["faces"]), 1)
        self.assertEqual(updated[0]["faces"][0]["face_id"], 1)
        # New cluster created
        self.assertIn(1, updated)
        self.assertEqual(updated[1]["faces"][0]["face_id"], 2)

if __name__ == '__main__':
    unittest.main()
