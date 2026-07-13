import os
import rawpy
import cv2
from io import BytesIO
from PIL import Image
import numpy as np

def extract_raw_preview(path: str) -> bytes:
    """
    Extracts the embedded JPEG preview from a RAW file.
    Falls back to a fast draft decode if no embedded thumbnail exists.
    Returns raw JPEG bytes.
    """
    if not os.path.exists(path):
        return None
    try:
        with rawpy.imread(path) as raw:
            try:
                thumb = raw.extract_thumb()
                if thumb.format == rawpy.ThumbFormat.JPEG:
                    return thumb.data
                elif thumb.format == rawpy.ThumbFormat.BITMAP:
                    # Convert BITMAP array to JPEG bytes
                    img = Image.fromarray(thumb.data)
                    out = BytesIO()
                    img.save(out, format="JPEG", quality=90)
                    return out.getvalue()
            except rawpy.LibRawNoThumbnailError:
                pass
            
            # Fallback to fast draft raw decode
            rgb = raw.postprocess(
                half_size=True,
                use_camera_wb=True,
                fast_pct=True,
                no_auto_bright=True
            )
            bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            success, encoded_img = cv2.imencode('.jpg', bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            if success:
                return encoded_img.tobytes()
    except Exception as e:
        print(f"[preview_engine] Failed to extract raw preview from {os.path.basename(path)}: {e}")
    return None

def generate_raw_thumbnail(path: str, max_dim: int = 400) -> bytes:
    """
    Generates a downscaled thumbnail (default 400px max dimension) from a RAW file.
    Optimized for grid rendering. Returns raw JPEG bytes.
    """
    preview_bytes = extract_raw_preview(path)
    if not preview_bytes:
        return None
    try:
        # Load from bytes and downscale
        nparr = np.frombuffer(preview_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            h, w = img.shape[:2]
            if max(h, w) > max_dim:
                scale = max_dim / max(h, w)
                img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            success, encoded_img = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
            if success:
                return encoded_img.tobytes()
    except Exception as e:
        print(f"[preview_engine] Failed to generate raw thumbnail for {os.path.basename(path)}: {e}")
    return None
