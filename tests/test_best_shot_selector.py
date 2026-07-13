import unittest
import os
import sys

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import best_shot_selector

class TestBestShotSelector(unittest.TestCase):
    def test_select_best_shots_basic(self):
        photo_details = [
            {
                "file_path": "/images/shot1.jpg",
                "metrics": {
                    "faces": [
                        {"person_id": 1, "face_quality_score": 80.5},
                        {"person_id": 2, "face_quality_score": 70.0}
                    ]
                }
            },
            {
                "file_path": "/images/shot2.jpg",
                "metrics": {
                    "faces": [
                        {"person_id": 1, "face_quality_score": 92.0},  # Better shot for Person 1
                        {"person_id": 2, "face_quality_score": 65.5}
                    ]
                }
            },
            {
                "file_path": "/images/shot3.jpg",
                "metrics": {
                    "faces": [
                        {"person_id": 1, "face_quality_score": 88.0},
                        {"person_id": 2, "face_quality_score": 85.5}   # Better shot for Person 2
                    ]
                }
            }
        ]

        best_shots = best_shot_selector.select_best_shots(photo_details)
        self.assertEqual(best_shots[1], "/images/shot2.jpg")
        self.assertEqual(best_shots[2], "/images/shot3.jpg")

if __name__ == '__main__':
    unittest.main()
