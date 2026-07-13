import unittest
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)

import embedding_engine

class TestEmbeddingEngine(unittest.TestCase):
    def test_generate_embedding_face(self):
        mock_image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        emb = embedding_engine.generate_embedding(mock_image, "face")
        
        self.assertEqual(emb.shape, (512,))
        # Check L2 normalized: norm should be very close to 1.0
        self.assertAlmostEqual(np.linalg.norm(emb), 1.0, places=5)

    def test_generate_embedding_general(self):
        mock_image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        emb = embedding_engine.generate_embedding(mock_image, "general")
        
        self.assertEqual(emb.shape, (128,))
        self.assertAlmostEqual(np.linalg.norm(emb), 1.0, places=5)

    def test_cosine_similarity(self):
        vec1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec2 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
        vec3 = np.array([0.0, 1.0, 0.0], dtype=np.float32)
        
        self.assertAlmostEqual(embedding_engine.cosine_similarity(vec1, vec2), 1.0, places=5)
        self.assertAlmostEqual(embedding_engine.cosine_similarity(vec1, vec3), 0.0, places=5)

    def test_serialization(self):
        vec = np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32)
        serialized = embedding_engine.serialize_embedding(vec)
        self.assertIsInstance(serialized, str)
        
        deserialized = embedding_engine.deserialize_embedding(serialized)
        np.testing.assert_array_almost_equal(vec, deserialized)

if __name__ == '__main__':
    unittest.main()
