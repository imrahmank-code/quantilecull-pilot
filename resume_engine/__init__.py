import os
import json
from recovery import RecoveryManager

recovery_manager = RecoveryManager()

def load_active_checkpoint() -> dict:
    """Loads the active checkpoint if it exists and is valid."""
    chk = recovery_manager.load_checkpoint()
    if chk:
        # Validate that the target path still exists
        target_path = chk.get("target_path")
        if target_path and os.path.exists(target_path):
            return chk
    return None

def prepare_resume_scan(checkpoint: dict) -> tuple:
    """
    Prepares a resume scan execution payload.
    Returns: (target_path, threshold, top_percent, remaining_paths, processed_paths)
    """
    target_path = checkpoint["target_path"]
    threshold = checkpoint["threshold"]
    top_percent = checkpoint["top_percent"]
    
    # Filter remaining paths to ensure they still exist on disk
    remaining_paths = [p for p in checkpoint.get("remaining_paths", []) if os.path.exists(p)]
    processed_paths = [p for p in checkpoint.get("processed_paths", []) if os.path.exists(p)]
    
    return target_path, threshold, top_percent, remaining_paths, processed_paths

def clear_active_checkpoint():
    """Cleans up checkpoint state."""
    recovery_manager.clear_checkpoint()
