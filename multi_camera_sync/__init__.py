"""
MultiCameraSyncEngine - Pillar 1 of QuantileCull Next-Iteration Architecture
Automates multi-body chronological alignment, EXIF timestamp offset calibration,
and flash-burst temporal alignment for multi-camera shoots (e.g., weddings).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
import statistics
import math


@dataclass
class CameraSyncConfig:
    """Configuration and estimated drift parameters for a camera body."""
    camera_id: str
    serial_number: str = "Unknown"
    model: str = "Unknown"
    offset_seconds: float = 0.0
    confidence: float = 1.0
    calibration_method: str = "manual"  # "manual", "flash_sync", "burst_correlation", "reference"


@dataclass
class NormalizedPhotoMetadata:
    """Metadata for an image with calibrated chronological normalization applied."""
    original_path: str
    camera_id: str
    original_timestamp: datetime
    normalized_timestamp: datetime
    offset_applied: float
    flash_fired: bool = False
    serial_number: str = "Unknown"
    cluster_id: Optional[str] = None
    extra_attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FlashEvent:
    """Detected optical or EXIF flash discharge event."""
    camera_id: str
    timestamp: datetime
    photo_path: str
    brightness_peak: float = 0.0


class MultiCameraSyncEngine:
    """
    Engine for calibrating temporal drift across multiple camera bodies
    and producing a unified, normalized chronological capture stream.
    """

    def __init__(self, reference_camera_id: Optional[str] = None):
        """
        Initialize the multi-camera synchronization engine.
        
        Args:
            reference_camera_id: Optional explicit ID of the anchor camera.
                                 If None, the camera with the highest image count is chosen.
        """
        self.reference_camera_id: Optional[str] = reference_camera_id
        self.camera_configs: Dict[str, CameraSyncConfig] = {}
        self.manual_offsets: Dict[str, float] = {}

    def set_manual_offset(self, camera_id: str, offset_seconds: float) -> None:
        """
        Manually assign a clock offset for a specific camera.
        
        Args:
            camera_id: Unique identifier for the camera body.
            offset_seconds: Seconds to add to the camera's EXIF timestamp.
        """
        self.manual_offsets[camera_id] = float(offset_seconds)
        self.camera_configs[camera_id] = CameraSyncConfig(
            camera_id=camera_id,
            offset_seconds=float(offset_seconds),
            calibration_method="manual",
            confidence=1.0
        )

    def get_camera_config(self, camera_id: str) -> Optional[CameraSyncConfig]:
        """Retrieve the synchronization config for a specific camera."""
        return self.camera_configs.get(camera_id)

    @staticmethod
    def extract_camera_id(record: Dict[str, Any]) -> str:
        """
        Derives a deterministic, unique camera ID from photo metadata.
        
        Args:
            record: Dictionary containing photo EXIF and metadata.
            
        Returns:
            A unique string identifier for the camera body.
        """
        if "camera_id" in record and record["camera_id"]:
            return str(record["camera_id"]).strip()
        
        serial = (
            record.get("serial_number")
            or record.get("body_serial_number")
            or record.get("serial")
            or ""
        )
        model = record.get("camera_model") or record.get("model") or ""
        make = record.get("camera_make") or record.get("make") or ""

        parts = [p.strip() for p in [make, model, serial] if p and p.strip()]
        return "_".join(parts) if parts else "Camera_Default"


    @staticmethod
    def parse_timestamp(val: Any) -> Optional[datetime]:
        """Parses an ISO string, datetime, or POSIX timestamp into a datetime object."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, (int, float)):
            return datetime.fromtimestamp(val)
        if isinstance(val, str) and val.strip():
            # Support ISO and standard EXIF date formats
            clean_val = val.strip()
            for fmt in [
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y:%m:%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d"
            ]:
                try:
                    return datetime.strptime(clean_val, fmt)
                except ValueError:
                    continue
        return None

    def group_by_camera(self, photo_records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Groups photo records by unique camera identifier.
        
        Args:
            photo_records: List of photo metadata dictionaries.
            
        Returns:
            Dict mapping camera_id to its list of photo records.
        """
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for rec in photo_records:
            cid = self.extract_camera_id(rec)
            if cid not in groups:
                groups[cid] = []
            groups[cid].append(rec)
        return groups

    def detect_flash_events(
        self,
        photo_records: List[Dict[str, Any]],
        brightness_threshold: float = 0.8
    ) -> List[FlashEvent]:
        """
        Identifies photos where flash discharged, using EXIF tags or brightness spikes.
        
        Args:
            photo_records: List of photo metadata dictionaries.
            brightness_threshold: Threshold to qualify brightness peak as flash.
            
        Returns:
            List of detected FlashEvent instances sorted by timestamp.
        """
        events: List[FlashEvent] = []
        for rec in photo_records:
            cid = self.extract_camera_id(rec)
            ts = self.parse_timestamp(
                rec.get("date_taken") or rec.get("timestamp") or rec.get("created_at")
            )
            if not ts:
                continue

            flash_flag = False
            # Check EXIF flash indicators
            if rec.get("flash_fired") is True or rec.get("flash") in [True, 1, "Fired", "Flash fired"]:
                flash_flag = True
            elif rec.get("brightness", 0.0) >= brightness_threshold or rec.get("exposure_peak", 0.0) >= brightness_threshold:
                flash_flag = True

            if flash_flag:
                events.append(FlashEvent(
                    camera_id=cid,
                    timestamp=ts,
                    photo_path=rec.get("path") or rec.get("file_path") or "",
                    brightness_peak=float(rec.get("brightness", 1.0))
                ))

        events.sort(key=lambda e: e.timestamp)
        return events

    def estimate_drift_via_flash_sync(
        self,
        photo_records: List[Dict[str, Any]],
        max_search_window_sec: float = 30.0
    ) -> Dict[str, float]:
        """
        Calibrates clock drift by cross-matching near-simultaneous flash events across cameras.
        
        When a strobe or speedlight fires in an event space, multiple cameras shooting the scene
        register the discharge. The delta (t_ref - t_target) clusters around the true clock offset.
        
        Args:
            photo_records: List of photo records.
            max_search_window_sec: Max initial window to pair potential flash events.
            
        Returns:
            Dict mapping target camera_id to estimated offset in seconds relative to reference.
        """
        flash_events = self.detect_flash_events(photo_records)
        if not flash_events:
            return {}

        events_by_camera: Dict[str, List[FlashEvent]] = {}
        for ev in flash_events:
            if ev.camera_id not in events_by_camera:
                events_by_camera[ev.camera_id] = []
            events_by_camera[ev.camera_id].append(ev)

        # Determine reference camera
        ref_cam = self.reference_camera_id
        if not ref_cam or ref_cam not in events_by_camera:
            # Pick camera with highest flash count as reference
            ref_cam = max(events_by_camera.keys(), key=lambda c: len(events_by_camera[c]))

        ref_events = events_by_camera[ref_cam]
        estimated_offsets: Dict[str, float] = {ref_cam: 0.0}

        for target_cam, target_events in events_by_camera.items():
            if target_cam == ref_cam:
                continue

            delta_samples: List[float] = []
            for r_ev in ref_events:
                best_delta: Optional[float] = None
                min_diff = max_search_window_sec

                for t_ev in target_events:
                    # delta = t_ref - t_target
                    diff_sec = (r_ev.timestamp - t_ev.timestamp).total_seconds()
                    if abs(diff_sec) < min_diff:
                        min_diff = abs(diff_sec)
                        best_delta = diff_sec

                if best_delta is not None and min_diff <= max_search_window_sec:
                    delta_samples.append(best_delta)

            if delta_samples:
                # Use median with IQR filtering to reject accidental false flash correlations
                if len(delta_samples) >= 3:
                    delta_samples.sort()
                    q25 = delta_samples[len(delta_samples) // 4]
                    q75 = delta_samples[(3 * len(delta_samples)) // 4]
                    iqr = q75 - q25
                    inliers = [
                        d for d in delta_samples
                        if (q25 - 1.5 * iqr) <= d <= (q75 + 1.5 * iqr)
                    ]
                    estimated_offset = statistics.median(inliers if inliers else delta_samples)
                else:
                    estimated_offset = statistics.median(delta_samples)

                estimated_offsets[target_cam] = round(estimated_offset, 3)

        return estimated_offsets

    def estimate_drift_via_burst_temporal_alignment(
        self,
        photo_records: List[Dict[str, Any]],
        max_drift_sec: float = 120.0,
        bin_size_sec: float = 1.0
    ) -> Dict[str, float]:
        """
        Cross-correlates shooting activity bursts to calculate clock offset in the absence of flash.
        
        Args:
            photo_records: Photo records across cameras.
            max_drift_sec: Maximum drift range to evaluate (-max_drift to +max_drift).
            bin_size_sec: Temporal bin granularity for cross-correlation.
            
        Returns:
            Dict mapping target camera_id to estimated offset in seconds relative to reference.
        """
        groups = self.group_by_camera(photo_records)
        if len(groups) <= 1:
            return {cid: 0.0 for cid in groups}

        ref_cam = self.reference_camera_id or max(groups.keys(), key=lambda c: len(groups[c]))
        ref_records = groups[ref_cam]

        ref_timestamps = [
            self.parse_timestamp(r.get("date_taken") or r.get("timestamp"))
            for r in ref_records
        ]
        ref_timestamps = [t for t in ref_timestamps if t is not None]
        if not ref_timestamps:
            return {cid: 0.0 for cid in groups}

        min_time = min(ref_timestamps)
        ref_epoch_offsets = [(t - min_time).total_seconds() for t in ref_timestamps]

        offsets: Dict[str, float] = {ref_cam: 0.0}

        for target_cam, target_records in groups.items():
            if target_cam == ref_cam:
                continue

            target_timestamps = [
                self.parse_timestamp(r.get("date_taken") or r.get("timestamp"))
                for r in target_records
            ]
            target_timestamps = [t for t in target_timestamps if t is not None]
            if not target_timestamps:
                offsets[target_cam] = 0.0
                continue

            target_epoch_offsets = [(t - min_time).total_seconds() for t in target_timestamps]

            # Cross-correlation search over discrete shift range
            best_shift = 0.0
            max_coincidences = -1

            step = bin_size_sec
            num_steps = int(max_drift_sec / step)

            # Build a fast lookup set for reference event timestamps binned
            ref_bins = set(int(t / bin_size_sec) for t in ref_epoch_offsets)

            for step_idx in range(-num_steps, num_steps + 1):
                shift = step_idx * step
                # Count matches where shifted target hits a reference bin
                coincidences = sum(
                    1 for t in target_epoch_offsets
                    if int((t + shift) / bin_size_sec) in ref_bins
                )
                if coincidences > max_coincidences:
                    max_coincidences = coincidences
                    best_shift = shift

            offsets[target_cam] = round(best_shift, 3)

        return offsets

    def calibrate_offsets(
        self,
        photo_records: List[Dict[str, Any]],
        auto_align: bool = True
    ) -> Dict[str, CameraSyncConfig]:
        """
        Coordinates full offset calibration across all detected cameras.
        
        Priority:
        1. Explicit manual overrides
        2. Flash-sync auto-calibration
        3. Burst density temporal cross-correlation
        4. Zero offset baseline
        
        Args:
            photo_records: Input photo records.
            auto_align: Whether to compute automated drift estimation.
            
        Returns:
            Dict mapping camera_id to CameraSyncConfig.
        """
        groups = self.group_by_camera(photo_records)
        if not groups:
            return {}

        # Resolve reference camera
        if not self.reference_camera_id or self.reference_camera_id not in groups:
            candidates = [c for c in groups.keys() if c not in self.manual_offsets or self.manual_offsets[c] == 0.0]
            if not candidates:
                candidates = list(groups.keys())
            self.reference_camera_id = max(candidates, key=lambda c: len(groups[c]))

        flash_offsets: Dict[str, float] = {}
        burst_offsets: Dict[str, float] = {}

        if auto_align and len(groups) > 1:
            flash_offsets = self.estimate_drift_via_flash_sync(photo_records)
            burst_offsets = self.estimate_drift_via_burst_temporal_alignment(photo_records)

        for cid, recs in groups.items():
            sample_rec = recs[0] if recs else {}
            serial = str(
                sample_rec.get("serial_number")
                or sample_rec.get("body_serial_number")
                or "Unknown"
            )
            model = str(sample_rec.get("camera_model") or sample_rec.get("model") or "Camera")

            # Determine offset
            if cid in self.manual_offsets:
                offset = self.manual_offsets[cid]
                method = "manual"
                conf = 1.0
            elif cid == self.reference_camera_id:
                offset = 0.0
                method = "reference"
                conf = 1.0

            elif cid in flash_offsets:
                offset = flash_offsets[cid]
                method = "flash_sync"
                conf = 0.95
            elif cid in burst_offsets:
                offset = burst_offsets[cid]
                method = "burst_correlation"
                conf = 0.80
            else:
                offset = 0.0
                method = "uncalibrated"
                conf = 0.50

            self.camera_configs[cid] = CameraSyncConfig(
                camera_id=cid,
                serial_number=serial,
                model=model,
                offset_seconds=offset,
                confidence=conf,
                calibration_method=method
            )

        return self.camera_configs

    def normalize_stream(
        self,
        photo_records: List[Dict[str, Any]],
        auto_calibrate: bool = True
    ) -> List[NormalizedPhotoMetadata]:
        """
        Applies calibrated clock offsets and outputs a strictly chronological,
        normalized photo sequence.
        
        Args:
            photo_records: Raw photo metadata records.
            auto_calibrate: Whether to calibrate camera offsets if not already done.
            
        Returns:
            List of NormalizedPhotoMetadata sorted chronologically by normalized_timestamp.
        """
        if auto_calibrate or not self.camera_configs:
            self.calibrate_offsets(photo_records, auto_align=auto_calibrate)

        normalized_items: List[NormalizedPhotoMetadata] = []

        for rec in photo_records:
            cid = self.extract_camera_id(rec)
            orig_ts = self.parse_timestamp(
                rec.get("date_taken") or rec.get("timestamp") or rec.get("created_at")
            )
            if not orig_ts:
                continue

            config = self.camera_configs.get(cid)
            offset_sec = config.offset_seconds if config else self.manual_offsets.get(cid, 0.0)

            norm_ts = orig_ts + timedelta(seconds=offset_sec)

            normalized_items.append(NormalizedPhotoMetadata(
                original_path=rec.get("path") or rec.get("file_path") or "",
                camera_id=cid,
                original_timestamp=orig_ts,
                normalized_timestamp=norm_ts,
                offset_applied=offset_sec,
                flash_fired=bool(rec.get("flash_fired") or rec.get("flash")),
                serial_number=config.serial_number if config else "Unknown",
                cluster_id=rec.get("cluster_id"),
                extra_attributes={k: v for k, v in rec.items() if k not in ["path", "file_path"]}
            ))

        # Sort combined stream strictly by normalized chronological timestamp
        normalized_items.sort(key=lambda item: item.normalized_timestamp)
        return normalized_items

    @staticmethod
    def detect_interleaved_bursts(
        normalized_stream: List[NormalizedPhotoMetadata],
        max_burst_gap_sec: float = 2.0
    ) -> List[List[NormalizedPhotoMetadata]]:
        """
        Groups chronologically aligned images into burst sequences, grouping multi-camera
        shots that were taken within `max_burst_gap_sec` of each other into unified candidate clusters.
        
        Args:
            normalized_stream: Normalized, chronologically sorted photo list.
            max_burst_gap_sec: Maximum time gap (seconds) between successive shots in a burst.
            
        Returns:
            List of burst clusters (each being a list of NormalizedPhotoMetadata).
        """
        if not normalized_stream:
            return []

        bursts: List[List[NormalizedPhotoMetadata]] = []
        current_burst: List[NormalizedPhotoMetadata] = [normalized_stream[0]]

        for i in range(1, len(normalized_stream)):
            prev_item = normalized_stream[i - 1]
            curr_item = normalized_stream[i]

            gap_sec = (curr_item.normalized_timestamp - prev_item.normalized_timestamp).total_seconds()

            if gap_sec <= max_burst_gap_sec:
                current_burst.append(curr_item)
            else:
                bursts.append(current_burst)
                current_burst = [curr_item]

        if current_burst:
            bursts.append(current_burst)

        return bursts
