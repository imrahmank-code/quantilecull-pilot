import unittest
import os
import sys
import tempfile
import shutil
import cv2
import numpy as np
from unittest.mock import patch

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)

import analysis_pipeline

class TestAnalysisPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch('model_manager.load_model', return_value="mock_session_obj")
    def test_run_pipeline_standard(self, mock_load):
        # Create a mock JPEG image
        img_path = os.path.join(self.test_dir, "test_image.jpg")
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        cv2.imwrite(img_path, img)
        
        # Run pipeline
        out = analysis_pipeline.run_pipeline(img_path)
        
        # Verify schema
        self.assertIn("ImageInfo", out)
        self.assertEqual(out["ImageInfo"]["width"], 100)
        self.assertEqual(out["ImageInfo"]["height"], 100)
        self.assertEqual(out["ImageInfo"]["format"], "JPG")
        
        self.assertIn("Quality", out)
        self.assertEqual(out["Quality"]["overall_score"], 85.0)
        
        self.assertIn("Faces", out)
        self.assertTrue(len(out["Faces"]) > 0)
        self.assertIn("embedding", out["Faces"][0])
        
        self.assertIn("Eyes", out)
        self.assertIn("left_eye_open", out["Eyes"])
        
        self.assertIn("Smile", out)
        self.assertIn("Scene", out)
        self.assertEqual(out["Scene"]["category"], "Portrait")

if __name__ == '__main__':
    unittest.main()
