import unittest
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import similarity_engine

class TestSimilarityEngine(unittest.TestCase):
    def test_cosine_similarity_identity(self):
        v = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        sim = similarity_engine.cosine_similarity(v, v)
        self.assertAlmostEqual(sim, 1.0, places=5)

    def test_cosine_similarity_orthogonal(self):
        v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        sim = similarity_engine.cosine_similarity(v1, v2)
        self.assertAlmostEqual(sim, 0.0, places=5)

    def test_compute_distance(self):
        v1 = np.array([1.0, 0.0], dtype=np.float32)
        v2 = np.array([0.0, 1.0], dtype=np.float32)
        # Cosine distance = 1 - sim = 1 - 0 = 1
        d_cos = similarity_engine.compute_distance(v1, v2, "cosine")
        self.assertAlmostEqual(d_cos, 1.0, places=5)
        # Euclidean distance = sqrt(1^2 + (-1)^2) = sqrt(2) = 1.4142
        d_eucl = similarity_engine.compute_distance(v1, v2, "euclidean")
        self.assertAlmostEqual(d_eucl, 1.41421, places=4)

    def test_find_similar_faces(self):
        query = np.array([1.0, 0.0], dtype=np.float32)
        candidates = [
            np.array([1.0, 0.0], dtype=np.float32),      # sim = 1.0
            np.array([0.707, 0.707], dtype=np.float32),  # sim = 0.707
            np.array([0.0, 1.0], dtype=np.float32)       # sim = 0.0
        ]
        matches = similarity_engine.find_similar_faces(query, candidates, threshold=0.7)
        self.assertEqual(len(matches), 2)
        self.assertEqual(matches[0][0], 0) # Index 0 is best
        self.assertAlmostEqual(matches[0][1], 1.0, places=4)
        self.assertEqual(matches[1][0], 1) # Index 1 is second best

    def test_build_similarity_matrix(self):
        embeddings = [
            np.array([1.0, 0.0], dtype=np.float32),
            np.array([0.0, 1.0], dtype=np.float32)
        ]
        matrix = similarity_engine.build_similarity_matrix(embeddings)
        self.assertEqual(matrix.shape, (2, 2))
        self.assertAlmostEqual(matrix[0, 0], 1.0, places=5)
        self.assertAlmostEqual(matrix[0, 1], 0.0, places=5)

if __name__ == '__main__':
    unittest.main()
