import unittest
import numpy as np
import sys
import os

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)
import image_analyzer

class TestQuantileCullV3(unittest.TestCase):
    
    def test_clamp_score(self):
        self.assertEqual(image_analyzer.clamp_score(105.5), 100.0)
        self.assertEqual(image_analyzer.clamp_score(-5.0), 0.0)
        self.assertEqual(image_analyzer.clamp_score(75.5), 75.5)
        
    def test_calculate_subject_completeness_no_faces(self):
        score = image_analyzer._calculate_subject_completeness(1000, 1000, [])
        self.assertEqual(score, 100.0)
        
    def test_calculate_subject_completeness_cropped_head(self):
        # Face touching top boundary (y=1.0)
        faces = [{"x": 100, "y": 1, "w": 50, "h": 50}]
        score = image_analyzer._calculate_subject_completeness(1000, 1000, faces)
        # 100.0 base - 30.0 top cutoff = 70.0
        self.assertEqual(score, 70.0)
        
    def test_calculate_subject_completeness_cropped_sides(self):
        # Face touching left boundary (x=1.0), y=50 (no top margin reward, no top penalty)
        faces = [{"x": 1, "y": 50, "w": 50, "h": 50}]
        score = image_analyzer._calculate_subject_completeness(1000, 1000, faces)
        # 100.0 base - 25.0 side cutoff = 75.0
        self.assertEqual(score, 75.0)
        
    def test_calculate_subject_completeness_rewards(self):
        # Faces centered with proper headroom (y=150, top margin = 15%)
        # Face is centered (x=475, left_margin=0.475, right_margin=0.475)
        faces = [{"x": 475, "y": 150, "w": 50, "h": 50}]
        score = image_analyzer._calculate_subject_completeness(1000, 1000, faces)
        # 100.0 base (no penalties) + 5.0 balanced sides + 5.0 proper headroom = 110.0 -> clamped to 100.0
        self.assertEqual(score, 100.0)

        # Let's test a case where base score is slightly penalized but gets rewards
        # Face is close to bottom (y=850, y+h=900, bottom margin = 10%) -> soft bottom penalty (-10)
        # Side margins balanced (left=30%, right=30%) -> reward (+5)
        # Top headroom ideal (min_top=150, top margin = 15%) -> reward (+5)
        faces = [{"x": 300, "y": 150, "w": 400, "h": 750}]
        score = image_analyzer._calculate_subject_completeness(1000, 1000, faces)
        # 100.0 base - 10.0 bottom proximity + 5.0 balanced sides + 5.0 headroom = 100.0
        self.assertEqual(score, 100.0)
        
    def test_publishability_score_group(self):
        # Good group photo: 3 faces, no blinks, sharp faces, good exposure
        metrics = {
            "overall_score": 90.0,
            "composition": 90.0,
            "subject_completeness": 95.0,
            "brightness": 80.0,
            "face_exposure": 85.0,
            "sharpness": 80.0,
            "contrast": 80.0,
            "faces": [
                {"x": 100, "y": 100, "w": 50, "h": 50, "sharpness": 80.0},
                {"x": 300, "y": 100, "w": 50, "h": 50, "sharpness": 85.0},
                {"x": 500, "y": 100, "w": 50, "h": 50, "sharpness": 75.0}
            ],
            "eyes_open_score": 95.0,
            "camera_facing": 90.0,
            "face_size_factor": 15.0,
            "image_width": 1000.0,
            "image_height": 1000.0,
            "has_blink": False,
            "has_motion_blur": False,
            "scoring_profile": "group"
        }
        score = image_analyzer.calculate_publishability_score(metrics)
        self.assertAlmostEqual(score, 98.8, places=1)
        
    def test_publishability_score_penalties(self):
        # Portrait photo with blink and motion blur
        metrics = {
            "overall_score": 50.0,
            "composition": 70.0,
            "subject_completeness": 90.0,
            "brightness": 70.0,
            "face_exposure": 70.0,
            "sharpness": 40.0,
            "contrast": 60.0,
            "faces": [
                {"x": 100, "y": 100, "w": 200, "h": 200, "sharpness": 40.0, "eye_openness": 20.0, "camera_facing": 80.0}
            ],
            "eyes_open_score": 20.0,
            "camera_facing": 80.0,
            "face_size_factor": 40.0,
            "image_width": 1000.0,
            "image_height": 1000.0,
            "has_blink": True,
            "has_motion_blur": True,
            "scoring_profile": "portrait"
        }
        score = image_analyzer.calculate_publishability_score(metrics)
        self.assertEqual(score, 0.0)

    def test_explainability_engine(self):
        metrics = {
            "sharpness": 90.0,
            "brightness": 85.0,
            "contrast": 75.0,
            "composition": 90.0,
            "motion_blur": 100.0,
            "subject_completeness": 95.0,
            "faces": [],
            "scoring_profile": "scene"
        }
        image_analyzer.generate_selection_reasons(metrics)
        self.assertIn("primary_strength", metrics)
        self.assertIn("selection_reasons", metrics)
        self.assertEqual(metrics["primary_strength"], "sharpness")
        self.assertIn("Excellent composition", metrics["selection_reasons"])
        self.assertIn("Excellent sharpness", metrics["selection_reasons"])
        
    def test_cache_recalculation_upgrade(self):
        # Mock V2 cache entry
        metrics = {
            "sharpness": 80.0,
            "brightness": 80.0,
            "contrast": 70.0,
            "saturation": 70.0,
            "faces_detected": 1,
            "faces": [{"x": 100, "y": 100, "w": 100, "h": 100, "sharpness": 80.0}],
            "composition": 85.0,
            "laplacian_variance": 120.0,
            "motion_blur": 100.0,
            "eyes_open_score": 90.0,
            "camera_facing": 85.0,
            "has_blink": False,
            "has_motion_blur": False,
            "is_blurry": False,
            "face_exposure": 80.0,
            "face_size_factor": 15.0,
            "image_width": 1000.0,
            "image_height": 1000.0,
            "scoring_version": 2
        }
        
        # Calculate overall score dynamically (simulating cache read upgrade)
        score = image_analyzer.calculate_overall_score(metrics)
        
        # Assertions
        self.assertEqual(metrics["scoring_version"], 4)
        self.assertIn("scoring_profile", metrics)
        self.assertIn("publishability_score", metrics)
        self.assertIn("subject_completeness", metrics)
        self.assertIn("primary_strength", metrics)
        self.assertIn("selection_reasons", metrics)
        self.assertTrue(metrics["publishability_score"] > 0)
        self.assertEqual(metrics["subject_completeness"], 100.0)
        print(f"[Recalculation Test] Overall Score: {score}, Publishability: {metrics['publishability_score']}, Reasons: {metrics['selection_reasons']}")

    def test_event_classification(self):
        # 1. Portrait check: 1 face off-stage -> Networking
        metrics_portrait = {
            "image_width": 1000.0, "image_height": 1000.0,
            "faces": [{"x": 400, "y": 200, "w": 200, "h": 200, "camera_facing": 80.0}],
            "stage_presence": 10.0
        }
        category = image_analyzer._classify_event_category(metrics_portrait)
        self.assertEqual(category, "Networking")
        
        # 2. Keynote check: 1 speaker on stage (small face ratio)
        metrics_keynote = {
            "image_width": 1000.0, "image_height": 1000.0,
            "faces": [{"x": 450, "y": 200, "w": 80, "h": 80, "camera_facing": 80.0}],
            "stage_presence": 25.0
        }
        category = image_analyzer._classify_event_category(metrics_keynote)
        self.assertEqual(category, "Keynote")
        
        # 3. Panel check: 3 speakers on stage horizontally aligned
        metrics_panel = {
            "image_width": 1000.0, "image_height": 1000.0,
            "faces": [
                {"x": 100, "y": 200, "w": 80, "h": 80, "camera_facing": 50.0},
                {"x": 400, "y": 205, "w": 80, "h": 80, "camera_facing": 60.0},
                {"x": 700, "y": 195, "w": 80, "h": 80, "camera_facing": 55.0}
            ],
            "stage_presence": 25.0
        }
        category = image_analyzer._classify_event_category(metrics_panel)
        self.assertEqual(category, "Panel Discussion")
        
        # 4. Group Photo check: Posed group (>= 5 faces, camera facing >= 55)
        metrics_group = {
            "image_width": 1000.0, "image_height": 1000.0,
            "faces": [
                {"x": 100, "y": 200, "w": 80, "h": 80, "camera_facing": 80.0},
                {"x": 250, "y": 200, "w": 80, "h": 80, "camera_facing": 70.0},
                {"x": 400, "y": 200, "w": 80, "h": 80, "camera_facing": 90.0},
                {"x": 550, "y": 200, "w": 80, "h": 80, "camera_facing": 85.0},
                {"x": 700, "y": 200, "w": 80, "h": 80, "camera_facing": 80.0}
            ],
            "audience_presence": 10.0
        }
        category = image_analyzer._classify_event_category(metrics_group)
        self.assertEqual(category, "Group Photos")
        
        # 5. Networking check: 3 faces, not looking at camera (camera facing < 40)
        metrics_net = {
            "image_width": 1000.0, "image_height": 1000.0,
            "faces": [
                {"x": 200, "y": 200, "w": 80, "h": 80, "camera_facing": 10.0},
                {"x": 400, "y": 200, "w": 80, "h": 80, "camera_facing": 15.0},
                {"x": 600, "y": 200, "w": 80, "h": 80, "camera_facing": 20.0}
            ],
            "stage_presence": 10.0
        }
        category = image_analyzer._classify_event_category(metrics_net)
        self.assertEqual(category, "Networking")

    def test_exif_independent_grouping(self):
        import datetime
        import imagehash
        hash_results = {
            "img1.jpg": {
                "sha256": "sha1",
                "time": datetime.datetime.min,
                "phash": imagehash.hex_to_hash("a1b2c3d4e5f60708"),
                "ratio": 1.5
            },
            "img2.jpg": {
                "sha256": "sha2",
                "time": datetime.datetime.min,
                "phash": imagehash.hex_to_hash("a1b2c3d4e5f60709"), # Ham dist = 1
                "ratio": 1.5
            }
        }
        orig_hist = image_analyzer._compute_hsv_histogram
        image_analyzer._compute_hsv_histogram = lambda path: {
            "hue_hist": np.ones((180, 1), dtype=np.float32),
            "sat_hist": np.ones((256, 1), dtype=np.float32),
            "val_hist": np.ones((256, 1), dtype=np.float32),
            "mean_saturation": 50.0,
            "mean_brightness": 128.0,
            "std_brightness": 30.0
        }
        try:
            groups = image_analyzer._group_duplicates(hash_results, threshold=12)
        finally:
            image_analyzer._compute_hsv_histogram = orig_hist
        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 2)

    def test_phase2_scene_heuristics(self):
        # Create mock BGR/HSV/Gray matrices
        import numpy as np
        hsv_mock = np.zeros((128, 128, 3), dtype=np.uint8)
        hsv_mock[:40, :, 0] = 110 # Hue
        hsv_mock[:40, :, 1] = 200 # Saturation
        hsv_mock[:40, :, 2] = 150 # Value
        
        hsv_mock[10:30, 20:60, 0] = 30
        hsv_mock[10:30, 20:60, 1] = 40
        hsv_mock[10:30, 20:60, 2] = 220
        
        faces_mock = [{"x": 100, "y": 100, "w": 50, "h": 50, "face_exposure": 90.0}]
        
        stage_score = image_analyzer.calculate_stage_presence(hsv_mock, faces_mock, brightness=60.0, contrast=70.0)
        self.assertTrue(stage_score > 0.0)
        self.assertTrue(stage_score <= 100.0)

        gray_mock = np.zeros((128, 128), dtype=np.uint8)
        gray_mock[50:120:10, :] = 255
        
        audience_score = image_analyzer.calculate_audience_presence(gray_mock, faces_mock)
        self.assertTrue(audience_score > 0.0)
        self.assertTrue(audience_score <= 100.0)

        branding_score = image_analyzer.calculate_branding_presence(hsv_mock, gray_mock)
        self.assertTrue(branding_score >= 0.0)
        self.assertTrue(branding_score <= 100.0)

    def test_phase2_editorial_decision_and_hero(self):
        # 1. Hero Candidate & HERO Editorial Decision
        metrics_hero = {
            "overall_score": 105.0,
            "publishability_score": 99.5,
            "composition": 85.0,
            "subject_completeness": 90.0,
            "brightness": 120.0,
            "faces": [{"x": 100, "y": 100, "w": 50, "h": 50, "sharpness": 80.0}],
            "has_blink": False,
            "has_motion_blur": False,
            "is_blurry": False,
            "hero_candidate": True,
            "has_storytelling_bonus": True,
            "category": "Keynote"
        }
        self.assertTrue(image_analyzer.is_hero_candidate(metrics_hero))
        decision = image_analyzer.determine_editorial_decision(metrics_hero, is_best=True)
        self.assertEqual(decision, "HERO")
        
        decision_not_best = image_analyzer.determine_editorial_decision(metrics_hero, is_best=False)
        self.assertEqual(decision_not_best, "MAYBE")

        # 2. KEEP Editorial Decision
        metrics_keep = {
            "overall_score": 65.0,
            "publishability_score": 55.0,
            "composition": 65.0,
            "subject_completeness": 80.0,
            "brightness": 100.0,
            "faces": [{"x": 100, "y": 100, "w": 50, "h": 50, "sharpness": 70.0}],
            "has_blink": False,
            "has_motion_blur": False,
            "is_blurry": False,
            "hero_candidate": False
        }
        self.assertFalse(image_analyzer.is_hero_candidate(metrics_keep))
        decision = image_analyzer.determine_editorial_decision(metrics_keep, is_best=True)
        self.assertEqual(decision, "KEEP")

        # 3. REJECT Editorial Decision (Severe Blur)
        metrics_reject = {
            "overall_score": 35.0,
            "publishability_score": 30.0,
            "composition": 40.0,
            "subject_completeness": 90.0,
            "brightness": 100.0,
            "faces": [{"x": 100, "y": 100, "w": 50, "h": 50, "sharpness": 30.0}],
            "has_blink": False,
            "has_motion_blur": True,
            "is_blurry": True,
            "hero_candidate": False
        }
        decision = image_analyzer.determine_editorial_decision(metrics_reject, is_best=True)
        self.assertEqual(decision, "REJECT")

    def test_diagnostics_and_hardening(self):
        # Test scan_directory_for_images returns tuple and contains expected keys
        image_paths, scan_diag = image_analyzer.scan_directory_for_images(".")
        self.assertIsInstance(image_paths, list)
        self.assertIsInstance(scan_diag, dict)
        self.assertIn("selected_directory", scan_diag)
        self.assertIn("total_files_discovered", scan_diag)
        self.assertIn("supported_images_discovered", scan_diag)
        self.assertIn("unsupported_files", scan_diag)
        self.assertIn("subdirectories", scan_diag)
        self.assertIn("subdirectories_with_images", scan_diag)
        self.assertIn("empty_directory", scan_diag)
        self.assertIn("is_inaccessible", scan_diag)
        self.assertIn("scan_error", scan_diag)
        self.assertIn("recursive_scan_issues", scan_diag)
        
        # Test diagnose_image_file on a mock non-existent file
        diag = image_analyzer.diagnose_image_file("non_existent_file_xyz.jpg")
        self.assertFalse(diag["exists"])
        self.assertEqual(diag["error_details"], "File does not exist.")
        
        # Test diagnose_image_file on unsupported format
        diag_unsupported = image_analyzer.diagnose_image_file("unsupported.txt")
        self.assertTrue(diag_unsupported["is_unsupported_format"])
        self.assertIn("allowed formats", diag_unsupported["error_details"])

        # Test diagnose_image_file on a zero-byte file
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            temp_name = f.name
        try:
            diag_zero = image_analyzer.diagnose_image_file(temp_name)
            self.assertTrue(diag_zero["exists"])
            self.assertEqual(diag_zero["file_size_bytes"], 0)
            self.assertTrue(diag_zero["is_unsupported_format"])
            self.assertIn("empty", diag_zero["error_details"])
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)

    def test_is_safe_path(self):
        import app
        from unittest.mock import patch

        # 1. C:\ folder (should succeed if it exists)
        if os.path.exists("C:\\"):
            safe, verified = app.is_safe_path("C:\\")
            self.assertTrue(safe)
            self.assertTrue(os.path.isabs(verified))

        # 2. Nonexistent path (should fail)
        nonexistent = "C:\\nonexistent_dir_abc_123"
        if not os.path.exists(nonexistent):
            safe, err = app.is_safe_path(nonexistent)
            self.assertFalse(safe)
            self.assertIn("does not exist", err)
            
            # 2b. Nonexistent path with check_exists=False (should succeed)
            safe_no_exists, verified_no_exists = app.is_safe_path(nonexistent, check_exists=False)
            self.assertTrue(safe_no_exists)
            self.assertEqual(verified_no_exists, os.path.realpath(nonexistent))

        # 3. Path traversal / relative paths check
        safe, err = app.is_safe_path("relative/path/to/folder")
        self.assertFalse(safe)
        self.assertIn("must be an absolute path", err)

        # 4. Mocked C:\, D:\ and external drive path validation
        with patch("os.path.exists", return_value=True), \
             patch("os.path.isabs", return_value=True), \
             patch("os.path.realpath", side_effect=lambda p: p):
            
            # C:\ path succeeds
            safe, verified = app.is_safe_path("C:\\AllowedFolder")
            self.assertTrue(safe)
            self.assertEqual(verified, "C:\\AllowedFolder")
            
            # D:\ path succeeds
            safe, verified = app.is_safe_path("D:\\AlgoShare Backup")
            self.assertTrue(safe)
            self.assertEqual(verified, "D:\\AlgoShare Backup")
            
            # E:\ path succeeds
            safe, verified = app.is_safe_path("E:\\ExternalPhotos")
            self.assertTrue(safe)
            self.assertEqual(verified, "E:\\ExternalPhotos")

if __name__ == "__main__":
    print("Running QuantileCull V3 Regression Tests...")
    unittest.main()
