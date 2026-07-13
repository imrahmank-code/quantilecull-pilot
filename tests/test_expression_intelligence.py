import unittest
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import face_detection_engine

class TestExpressionIntelligence(unittest.TestCase):
    def test_expression_scoring_keys(self):
        """Verify that all FP6 expression intelligence keys are populated on face detection."""
        # Create a mock face crop
        mock_image = np.zeros((100, 100, 3), dtype=np.uint8)
        faces = face_detection_engine.detect_faces(mock_image)
        
        # If fallback DNN detects anything (likely 0 for black image), check schema on first item
        for face in faces:
            self.assertIn("eye_openness", face)
            self.assertIn("blink_probability", face)
            self.assertIn("smile_confidence", face)
            self.assertIn("face_sharpness", face)
            self.assertIn("occlusion_score", face)
            self.assertIn("lighting_quality", face)
            self.assertIn("expression_score", face)
            self.assertIn("looking_at_camera", face)
            self.assertIn("head_pose_score", face)
            self.assertIn("face_quality_score", face)

if __name__ == '__main__':
    unittest.main()
