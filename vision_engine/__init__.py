from typing import Dict, List, Optional
from analysis_pipeline import run_pipeline

def process_image(image_path: str, enabled_features: Optional[List[str]] = None) -> dict:
    """Convenience public API wrapper mapping image paths to analysis results."""
    return run_pipeline(image_path, enabled_features)
