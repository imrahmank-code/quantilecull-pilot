import os
import rawpy
import numpy as np
import cv2

RAW_EXTENSIONS = {'.cr2', '.cr3', '.nef', '.nrw', '.arw', '.orf', '.raf', '.rw2', '.dng', '.pef', '.x3f'}

def is_raw_file(path: str) -> bool:
    """Checks if the file extension corresponds to a supported camera RAW format."""
    ext = os.path.splitext(path)[1].lower()
    return ext in RAW_EXTENSIONS

def load_raw_image(path: str, max_dim: int = None, half_size: bool = True) -> np.ndarray:
    """
    Decodes the raw sensor data of a RAW image using rawpy and returns a BGR cv2 image.
    Uses half_size=True by default for fast draft rendering (ideal for quality analysis).
    Handles exceptions and returns None if the RAW file is corrupted.
    """
    if not os.path.exists(path):
        return None
    try:
        with rawpy.imread(path) as raw:
            # postprocess yields RGB, convert to BGR for OpenCV
            rgb = raw.postprocess(
                half_size=half_size,
                use_camera_wb=True,
                fast_pct=True,
                no_auto_bright=True
            )
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            
            # Apply downscaling if required
            if bgr is not None and max_dim and max(bgr.shape[:2]) > max_dim:
                h, w = bgr.shape[:2]
                scale = max_dim / max(h, w)
                bgr = cv2.resize(bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            return bgr
    except Exception as e:
        print(f"[raw_engine] Failed to decode raw image {os.path.basename(path)}: {e}")
        return None
