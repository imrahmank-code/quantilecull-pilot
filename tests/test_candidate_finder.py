import unittest
import os
import sys

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import blink_recovery

class TestCandidateFinder(unittest.TestCase):
    def test_find_recovery_candidates(self):
        target = {
            "person_id": 5,
            "orientation": {"yaw": 2.0, "pitch": 1.0, "roll": 0.0},
            "smile_confidence": 40.0,
            "lighting_quality": 80.0
        }
        candidates_db = [
            {
                "file_path": "/burst/img_open.jpg",
                "metrics": {
                    "faces": [
                        {
                            "person_id": 5,
                            "eye_openness": 90.0,
                            "orientation": {"yaw": 3.0, "pitch": 1.5, "roll": 0.0},
                            "smile_confidence": 42.0,
                            "lighting_quality": 82.0
                        }
                    ]
                }
            },
            {
                "file_path": "/burst/img_side_look.jpg",
                "metrics": {
                    "faces": [
                        {
                            "person_id": 5,
                            "eye_openness": 90.0,
                            "orientation": {"yaw": 25.0, "pitch": 1.5, "roll": 0.0}, # yaw mismatch (>12)
                            "smile_confidence": 42.0,
                            "lighting_quality": 82.0
                        }
                    ]
                }
            }
        ]

        matches = blink_recovery.find_recovery_candidates(target, candidates_db)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["file_path"], "/burst/img_open.jpg")

if __name__ == '__main__':
    unittest.main()
