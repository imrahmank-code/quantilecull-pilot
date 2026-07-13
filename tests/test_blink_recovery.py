import unittest
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import blink_recovery

class TestBlinkRecovery(unittest.TestCase):
    def test_recover_blink_pose_mismatch_rejected(self):
        target_img = np.zeros((200, 200, 3), dtype=np.uint8)
        cand_img = np.zeros((200, 200, 3), dtype=np.uint8)
        
        target_face = {
            "bbox": [50, 50, 100, 100],
            "orientation": {"yaw": 0.0, "pitch": 0.0, "roll": 0.0},
            "smile_confidence": 40.0,
            "lighting_quality": 80.0,
            "landmarks": {"left_eye": [80, 80], "right_eye": [120, 80]}
        }
        # Candidate has matching person but 20 degree yaw difference (> 12 degrees limit)
        cand_face = {
            "bbox": [50, 50, 100, 100],
            "orientation": {"yaw": 20.0, "pitch": 0.0, "roll": 0.0},
            "smile_confidence": 40.0,
            "lighting_quality": 80.0,
            "landmarks": {"left_eye": [80, 80], "right_eye": [120, 80]}
        }
        
        out, success = blink_recovery.recover_blink(target_img, target_face, cand_img, cand_face)
        self.assertFalse(success)
        # Should return unmodified target image
        np.testing.assert_array_equal(out, target_img)

    def test_recover_blink_success(self):
        target_img = np.zeros((200, 200, 3), dtype=np.uint8)
        cand_img = np.zeros((200, 200, 3), dtype=np.uint8)
        cand_img[75:85, 75:85, :] = 255
        
        target_face = {
            "bbox": [50, 50, 100, 100],
            "orientation": {"yaw": 1.0, "pitch": 1.0, "roll": 0.0},
            "smile_confidence": 40.0,
            "lighting_quality": 80.0,
            "landmarks": {"left_eye": [80, 80], "right_eye": [120, 80]}
        }
        cand_face = {
            "bbox": [50, 50, 100, 100],
            "orientation": {"yaw": 1.5, "pitch": 1.0, "roll": 0.0},
            "smile_confidence": 41.0,
            "lighting_quality": 81.0,
            "landmarks": {"left_eye": [80, 80], "right_eye": [120, 80]}
        }
        
        out, success = blink_recovery.recover_blink(target_img, target_face, cand_img, cand_face)
        self.assertTrue(success)
        self.assertFalse(np.array_equal(out, target_img))

if __name__ == '__main__':
    unittest.main()
