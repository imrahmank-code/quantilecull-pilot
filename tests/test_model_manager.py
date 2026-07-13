import unittest
import os
import sys
import tempfile
import shutil

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)

import model_manager

class TestModelManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_discover_models_empty(self):
        discovered = model_manager.discover_models(self.test_dir)
        self.assertEqual(len(discovered), 0)

    def test_discover_models_match(self):
        # Create a mock file corresponding to a registered model
        mock_file = os.path.join(self.test_dir, "eye_state.onnx")
        with open(mock_file, "w") as f:
            f.write("mock_onnx_bytes")
            
        discovered = model_manager.discover_models(self.test_dir)
        self.assertEqual(len(discovered), 1)
        self.assertEqual(discovered[0]["name"], "eye_state")

    def test_validate_checksum(self):
        mock_file = os.path.join(self.test_dir, "checksum_test.bin")
        content = b"TEST_CHECKSUM_DATA"
        with open(mock_file, "wb") as f:
            f.write(content)
            
        import hashlib
        expected_sha256 = hashlib.sha256(content).hexdigest()
        
        self.assertTrue(model_manager.validate_checksum(mock_file, expected_sha256))
        self.assertFalse(model_manager.validate_checksum(mock_file, "invalid_hash"))

    def test_get_model_info(self):
        info = model_manager.get_model_info("face_detector")
        self.assertIsNotNone(info)
        self.assertEqual(info["license"], "BSD-3-Clause")

if __name__ == '__main__':
    unittest.main()
