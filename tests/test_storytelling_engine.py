import unittest
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import storytelling_engine

class TestStorytellingEngine(unittest.TestCase):
    def test_segment_timeline(self):
        photos = [
            {"timestamp": 1000},
            {"timestamp": 1200},
            {"timestamp": 3000}, # gap of 1800 (>900)
            {"timestamp": 3500}
        ]
        chapters = storytelling_engine.segment_timeline(photos, gap_seconds=900)
        self.assertEqual(len(chapters), 2)
        self.assertEqual(len(chapters[0]), 2)
        self.assertEqual(len(chapters[1]), 2)

    def test_classify_scene_details(self):
        photo = {
            "metrics": {
                "faces": []
            }
        }
        scene = storytelling_engine.classify_scene(photo)
        self.assertEqual(scene, "Details/Decor")

    def test_classify_scene_portrait(self):
        photo = {
            "metrics": {
                "faces": [
                    {"bbox": [10, 10, 200, 200]} # Portrait size (>150)
                ]
            }
        }
        scene = storytelling_engine.classify_scene(photo)
        self.assertEqual(scene, "Portraits")

    def test_classify_scene_ceremony_reception(self):
        photo_ceremony = {
            "metrics": {
                "faces": [
                    {"smile_confidence": 10.0},
                    {"smile_confidence": 15.0},
                    {"smile_confidence": 20.0}
                ]
            }
        }
        photo_reception = {
            "metrics": {
                "faces": [
                    {"smile_confidence": 80.0},
                    {"smile_confidence": 75.0},
                    {"smile_confidence": 85.0}
                ]
            }
        }
        self.assertEqual(storytelling_engine.classify_scene(photo_ceremony), "Ceremony")
        self.assertEqual(storytelling_engine.classify_scene(photo_reception), "Reception")

    def test_select_highlights(self):
        photos = [
            {"metrics": {"faces": [{"face_quality_score": 60.0}]}},
            {"metrics": {"faces": [{"face_quality_score": 95.0}]}}, # Highlight
            {"metrics": {"faces": [{"face_quality_score": 80.0}]}}
        ]
        highlights = storytelling_engine.select_highlights(photos, top_n=1)
        self.assertEqual(len(highlights), 1)
        self.assertEqual(highlights[0]["metrics"]["faces"][0]["face_quality_score"], 95.0)

    def test_detect_coverage_gaps(self):
        photos = [
            {
                "timestamp": 1000,
                "metrics": {"faces": [{"person_id": 1}, {"person_id": 2}]}
            },
            {
                "timestamp": 5000, # gap of 4000 (>3600)
                "metrics": {"faces": [{"person_id": 2}]}
            }
        ]
        # Person 1 has 1 appearance out of 3 total -> 33%
        # Person 3 has 0 appearances -> 0% (<5%)
        gaps = storytelling_engine.detect_coverage_gaps(photos, all_persons=[1, 2, 3])
        self.assertIn(3, gaps["underrepresented_people"])
        self.assertEqual(len(gaps["long_duration_gaps"]), 1)

    def test_export_dam_collection(self):
        photos = [
            {"file_path": "/test/img1.jpg"},
            {"file_path": "/test/img2.jpg"}
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            xml_path = os.path.join(tmpdir, "collection.xml")
            success = storytelling_engine.export_dam_collection(photos, xml_path)
            self.assertTrue(success)
            self.assertTrue(os.path.exists(xml_path))
            
            # Verify XML content
            tree = ET.parse(xml_path)
            root = tree.getroot()
            self.assertEqual(root.tag, "collection")
            self.assertEqual(root.attrib["name"], "QuantileCull Highlights")
            children = list(root)
            self.assertEqual(len(children), 2)
            self.assertEqual(children[0].attrib["path"], "/test/img1.jpg")

if __name__ == '__main__':
    unittest.main()
