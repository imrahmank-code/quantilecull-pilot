import unittest
import os
import sys
import tempfile
import json
import xml.etree.ElementTree as ET

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import export_pipeline

class TestExportPipeline(unittest.TestCase):
    def test_write_xmp_sidecar_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = os.path.join(tmpdir, "photo.jpg")
            xmp_path = os.path.join(tmpdir, "photo.xmp")
            
            # Write new XMP
            success = export_pipeline.write_xmp_sidecar(img_path, 5, "Red", ["Highlights", "Wedding"])
            self.assertTrue(success)
            self.assertTrue(os.path.exists(xmp_path))
            
            # Verify parsed content
            with open(xmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('xmp:Rating="5"', content)
            self.assertIn('xmp:Label="Red"', content)
            self.assertIn('<rdf:li>Highlights</rdf:li>', content)

    def test_write_xmp_sidecar_update(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = os.path.join(tmpdir, "photo.jpg")
            xmp_path = os.path.join(tmpdir, "photo.xmp")
            
            # Populate basic XMP
            with open(xmp_path, "w", encoding="utf-8") as f:
                f.write('<rdf:Description xmp:Rating="2" xmp:Label="Green" />')
                
            success = export_pipeline.write_xmp_sidecar(img_path, 4, "Blue", [])
            self.assertTrue(success)
            
            with open(xmp_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('xmp:Rating="4"', content)
            self.assertIn('xmp:Label="Blue"', content)

    def test_apply_preset_wedding(self):
        photos = [
            {"scene": "Portraits", "is_highlight": False},
            {"scene": "Ceremony", "is_highlight": True}
        ]
        res = export_pipeline.apply_preset(photos, "Wedding")
        self.assertEqual(res[0]["rating"], 4)
        self.assertEqual(res[0]["label"], "Blue")
        self.assertEqual(res[1]["rating"], 5)
        self.assertEqual(res[1]["label"], "Red")

    def test_generate_report_html(self):
        summary = {"analyzed": 50, "kept": 25, "blink_recoveries": 3, "highlights_count": 5}
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = os.path.join(tmpdir, "summary.html")
            success = export_pipeline.generate_report(summary, report_path, "html")
            self.assertTrue(success)
            self.assertTrue(os.path.exists(report_path))
            
            with open(report_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("50", content)
            self.assertIn("Highlights Selected", content)

    def test_prepare_delivery_folders(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_dir = os.path.join(tmpdir, "src")
            dest_dir = os.path.join(tmpdir, "dest")
            os.makedirs(src_dir, exist_ok=True)
            
            photo_file = os.path.join(src_dir, "img1.jpg")
            with open(photo_file, "w") as f:
                f.write("data")
                
            photos = [
                {"file_path": photo_file, "scene": "Ceremony"}
            ]
            
            success = export_pipeline.prepare_delivery_folders(photos, dest_dir, "scenes")
            self.assertTrue(success)
            self.assertTrue(os.path.exists(os.path.join(dest_dir, "Ceremony", "img1.jpg")))

    def test_batch_workflow_engine(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = os.path.join(tmpdir, "batch.json")
            engine = export_pipeline.BatchWorkflowEngine(state_file)
            
            engine.add_to_queue("/folders/event1")
            engine.add_to_queue("/folders/event2")
            progress = engine.get_progress()
            
            self.assertEqual(progress["queue_size"], 2)
            self.assertEqual(progress["next_in_queue"], "/folders/event1")
            
            engine.mark_completed("/folders/event1")
            progress2 = engine.get_progress()
            self.assertEqual(progress2["queue_size"], 1)
            self.assertEqual(progress2["completed_size"], 1)

if __name__ == '__main__':
    unittest.main()
