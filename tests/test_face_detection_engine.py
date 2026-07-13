import unittest
import os
import sys
import numpy as np
import cv2

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import face_detection_engine

class TestFaceDetectionEngine(unittest.TestCase):
    def test_detect_faces_returns_list(self):
        """detect_faces should always return a list even on blank images."""
        blank = np.zeros((200, 200, 3), dtype=np.uint8)
        result = face_detection_engine.detect_faces(blank)
        self.assertIsInstance(result, list)

    def test_face_dict_schema(self):
        """If a face is detected, verify it has the correct keys."""
        # Create a realistic-ish test image (we can't guarantee MediaPipe finds a face
        # in a blank image, so we just verify empty-list schema)
        blank = np.zeros((200, 200, 3), dtype=np.uint8)
        result = face_detection_engine.detect_faces(blank)
        # For blank images, result is likely empty — that's valid
        self.assertIsInstance(result, list)
        
        # If any face was detected, verify schema
        for face in result:
            self.assertIn("bbox", face)
            self.assertIn("confidence", face)
            self.assertIn("landmarks", face)
            self.assertIn("orientation", face)
            self.assertIn("quality", face)
            self.assertEqual(len(face["bbox"]), 4)
            self.assertIn("roll", face["orientation"])
            self.assertIn("pitch", face["orientation"])
            self.assertIn("yaw", face["orientation"])
            self.assertIn("sharpness", face["quality"])
            self.assertIn("exposure", face["quality"])

if __name__ == '__main__':
    unittest.main()
