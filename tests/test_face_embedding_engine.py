import unittest
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import face_embedding_engine

class TestFaceEmbeddingEngine(unittest.TestCase):
    def test_generate_face_embedding_returns_512d(self):
        """Face embeddings must be exactly 512 dimensions."""
        mock_crop = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8)
        emb = face_embedding_engine.generate_face_embedding(mock_crop)
        self.assertEqual(emb.shape, (512,))

    def test_generate_face_embedding_normalized(self):
        """Face embeddings must be L2-normalized (unit vector)."""
        mock_crop = np.random.randint(0, 256, (112, 112, 3), dtype=np.uint8)
        emb = face_embedding_engine.generate_face_embedding(mock_crop)
        self.assertAlmostEqual(np.linalg.norm(emb), 1.0, places=4)

    def test_deterministic_same_input(self):
        """Same input image should produce the same embedding."""
        mock_crop = np.ones((50, 50, 3), dtype=np.uint8) * 128
        emb1 = face_embedding_engine.generate_face_embedding(mock_crop)
        emb2 = face_embedding_engine.generate_face_embedding(mock_crop)
        np.testing.assert_array_almost_equal(emb1, emb2)

    def test_different_inputs_differ(self):
        """Different input images should produce different embeddings."""
        crop_a = np.zeros((50, 50, 3), dtype=np.uint8)
        crop_b = np.ones((50, 50, 3), dtype=np.uint8) * 255
        emb_a = face_embedding_engine.generate_face_embedding(crop_a)
        emb_b = face_embedding_engine.generate_face_embedding(crop_b)
        # They should not be identical
        self.assertFalse(np.allclose(emb_a, emb_b))

if __name__ == '__main__':
    unittest.main()
