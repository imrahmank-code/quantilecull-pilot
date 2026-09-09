"""
Unit tests for MultiCameraSyncEngine (Pillar 1).
Tests multi-camera grouping, EXIF offset calibration, flash-sync drift estimation,
burst correlation, chronological stream normalization, and interleaved burst clustering.
"""

import unittest
from datetime import datetime, timedelta
import os
import sys

# Ensure repository root is on sys.path
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from multi_camera_sync import (
    MultiCameraSyncEngine,
    CameraSyncConfig,
    NormalizedPhotoMetadata,
    FlashEvent
)


class TestMultiCameraSyncEngine(unittest.TestCase):
    """Test suite for MultiCameraSyncEngine."""

    def setUp(self):
        self.engine = MultiCameraSyncEngine()
        self.base_time = datetime(2026, 9, 9, 14, 0, 0)

    def test_extract_camera_id(self):
        """Verify deterministic camera ID extraction from various metadata shapes."""
        rec1 = {"make": "Canon", "model": "EOS R5", "serial_number": "12345678"}
        self.assertEqual(MultiCameraSyncEngine.extract_camera_id(rec1), "Canon_EOS R5_12345678")

        rec2 = {"camera_id": "CustomCam_Alpha"}
        self.assertEqual(MultiCameraSyncEngine.extract_camera_id(rec2), "CustomCam_Alpha")

        rec3 = {"camera_model": "Sony A7IV"}
        self.assertEqual(MultiCameraSyncEngine.extract_camera_id(rec3), "Sony A7IV")

        rec4 = {}
        self.assertEqual(MultiCameraSyncEngine.extract_camera_id(rec4), "Camera_Default")

    def test_parse_timestamp(self):
        """Verify parsing across ISO, EXIF standard, and epoch formats."""
        iso_str = "2026-09-09T14:30:00"
        dt1 = MultiCameraSyncEngine.parse_timestamp(iso_str)
        self.assertEqual(dt1, datetime(2026, 9, 9, 14, 30, 0))

        exif_str = "2026:09:09 14:30:00"
        dt2 = MultiCameraSyncEngine.parse_timestamp(exif_str)
        self.assertEqual(dt2, datetime(2026, 9, 9, 14, 30, 0))

        now_dt = datetime(2026, 9, 9, 15, 0, 0)
        dt3 = MultiCameraSyncEngine.parse_timestamp(now_dt)
        self.assertEqual(dt3, now_dt)

        self.assertIsNone(MultiCameraSyncEngine.parse_timestamp(""))
        self.assertIsNone(MultiCameraSyncEngine.parse_timestamp(None))

    def test_group_by_camera(self):
        """Verify grouping photo records by camera body."""
        photos = [
            {"path": "/photos/cam1_001.cr3", "camera_id": "Cam_A"},
            {"path": "/photos/cam2_001.arw", "camera_id": "Cam_B"},
            {"path": "/photos/cam1_002.cr3", "camera_id": "Cam_A"},
            {"path": "/photos/cam3_001.nef", "camera_id": "Cam_C"},
        ]
        groups = self.engine.group_by_camera(photos)
        self.assertEqual(len(groups), 3)
        self.assertEqual(len(groups["Cam_A"]), 2)
        self.assertEqual(len(groups["Cam_B"]), 1)
        self.assertEqual(len(groups["Cam_C"]), 1)

    def test_manual_offset_assignment(self):
        """Verify manual offset override calibration and normalization."""
        self.engine.set_manual_offset("Cam_B", 45.0)

        records = [
            {"path": "a1.jpg", "camera_id": "Cam_A", "date_taken": self.base_time},
            {"path": "b1.jpg", "camera_id": "Cam_B", "date_taken": self.base_time},
        ]

        normalized = self.engine.normalize_stream(records, auto_calibrate=True)
        self.assertEqual(len(normalized), 2)

        # Cam_A (reference, offset=0)
        item_a = next(i for i in normalized if i.camera_id == "Cam_A")
        self.assertEqual(item_a.offset_applied, 0.0)
        self.assertEqual(item_a.normalized_timestamp, self.base_time)

        # Cam_B (manual offset=+45s)
        item_b = next(i for i in normalized if i.camera_id == "Cam_B")
        self.assertEqual(item_b.offset_applied, 45.0)
        self.assertEqual(item_b.normalized_timestamp, self.base_time + timedelta(seconds=45))

    def test_flash_sync_drift_estimation(self):
        """
        Simulate a wedding reception where Cam_B's clock is 12.0 seconds BEHIND Cam_A.
        When a strobe fires at t=100, 200, 300, Cam_A logs t=100 and Cam_B logs t=88.
        The flash sync engine should estimate an offset of +12.0s for Cam_B.
        """
        records = []
        # Strobe events at 100s, 200s, 300s, 400s relative to base_time
        strobe_seconds = [100.0, 200.0, 300.0, 400.0]
        drift_delta_sec = -12.0  # Cam B is 12 seconds behind

        for s in strobe_seconds:
            # Camera A (Reference)
            records.append({
                "path": f"camA_{s}.cr3",
                "camera_id": "Cam_A",
                "date_taken": self.base_time + timedelta(seconds=s),
                "flash_fired": True
            })
            # Camera B (Target, drifted clock)
            records.append({
                "path": f"camB_{s}.arw",
                "camera_id": "Cam_B",
                "date_taken": self.base_time + timedelta(seconds=s + drift_delta_sec),
                "flash_fired": True
            })

        self.engine.reference_camera_id = "Cam_A"
        offsets = self.engine.estimate_drift_via_flash_sync(records, max_search_window_sec=20.0)

        self.assertIn("Cam_B", offsets)
        # Cam B needs +12.0s added to match Cam A
        self.assertAlmostEqual(offsets["Cam_B"], 12.0, places=1)

    def test_burst_temporal_cross_correlation(self):
        """
        Simulate rapid burst shooting during the first dance.
        Cam_B clock is 5.0 seconds AHEAD of Cam_A (drift = +5.0s).
        Burst correlation should discover that shifting Cam_B by -5.0s aligns activity.
        """
        records = []
        burst_times = [10.0, 10.5, 11.0, 11.5, 50.0, 50.5, 51.0]

        for t in burst_times:
            records.append({
                "path": f"camA_{t}.jpg",
                "camera_id": "Cam_A",
                "date_taken": self.base_time + timedelta(seconds=t)
            })
            records.append({
                "path": f"camB_{t}.jpg",
                "camera_id": "Cam_B",
                "date_taken": self.base_time + timedelta(seconds=t + 5.0)  # Clock is 5s ahead
            })

        self.engine.reference_camera_id = "Cam_A"
        offsets = self.engine.estimate_drift_via_burst_temporal_alignment(
            records, max_drift_sec=30.0, bin_size_sec=1.0
        )

        self.assertIn("Cam_B", offsets)
        self.assertAlmostEqual(offsets["Cam_B"], -5.0, places=1)

    def test_chronological_stream_normalization(self):
        """Verify sorting and chronological alignment of an interleaved multi-camera stream."""
        self.engine.set_manual_offset("Cam_B", -10.0)  # Cam B was 10s ahead, needs -10s

        records = [
            {"path": "b1.jpg", "camera_id": "Cam_B", "date_taken": self.base_time + timedelta(seconds=15)},  # norm: +5s
            {"path": "a1.jpg", "camera_id": "Cam_A", "date_taken": self.base_time + timedelta(seconds=2)},   # norm: +2s
            {"path": "b2.jpg", "camera_id": "Cam_B", "date_taken": self.base_time + timedelta(seconds=20)},  # norm: +10s
            {"path": "a2.jpg", "camera_id": "Cam_A", "date_taken": self.base_time + timedelta(seconds=8)},   # norm: +8s
        ]

        stream = self.engine.normalize_stream(records, auto_calibrate=False)
        paths_in_order = [item.original_path for item in stream]

        # Expected normalized timeline:
        # a1 (2s), b1 (15-10 = 5s), a2 (8s), b2 (20-10 = 10s)
        self.assertEqual(paths_in_order, ["a1.jpg", "b1.jpg", "a2.jpg", "b2.jpg"])

    def test_detect_interleaved_bursts(self):
        """Verify grouping of rapid multi-camera bursts into unified comparison clusters."""
        t0 = self.base_time
        stream = [
            # Burst 1: Ring exchange (tight + wide shots simultaneously)
            NormalizedPhotoMetadata("a1.jpg", "Cam_A", t0, t0, 0.0),
            NormalizedPhotoMetadata("b1.jpg", "Cam_B", t0, t0 + timedelta(seconds=0.3), 0.0),
            NormalizedPhotoMetadata("a2.jpg", "Cam_A", t0, t0 + timedelta(seconds=0.8), 0.0),
            # Gap: 10 seconds later
            # Burst 2: First kiss
            NormalizedPhotoMetadata("a3.jpg", "Cam_A", t0, t0 + timedelta(seconds=11.0), 0.0),
            NormalizedPhotoMetadata("b2.jpg", "Cam_B", t0, t0 + timedelta(seconds=11.4), 0.0),
        ]

        bursts = MultiCameraSyncEngine.detect_interleaved_bursts(stream, max_burst_gap_sec=2.0)

        self.assertEqual(len(bursts), 2)
        self.assertEqual(len(bursts[0]), 3)  # a1, b1, a2
        self.assertEqual(len(bursts[1]), 2)  # a3, b2

        # Verify cluster composition
        self.assertEqual([i.original_path for i in bursts[0]], ["a1.jpg", "b1.jpg", "a2.jpg"])
        self.assertEqual([i.original_path for i in bursts[1]], ["a3.jpg", "b2.jpg"])


if __name__ == "__main__":
    unittest.main()
