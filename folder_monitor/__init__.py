import os
from cache_engine import get_cached_item
from xmp_engine import get_xmp_path

def discover_image_files(dir_path: str, allowed_extensions: set) -> list:
    """Discovers all supported image files in the direct directory (non-recursive)."""
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        return []
        
    image_paths = []
    try:
        for entry in os.scandir(dir_path):
            if entry.is_file():
                ext = os.path.splitext(entry.name)[1].lower().lstrip('.')
                if ext in allowed_extensions:
                    image_paths.append(os.path.realpath(entry.path))
    except Exception as e:
        print(f"[folder_monitor] Failed to scan directory {dir_path}: {e}")
        
    # Sort files naturally
    image_paths.sort()
    return image_paths

def get_incremental_status(image_paths: list) -> tuple:
    """
    Compares file paths and modification times against the cache database.
    Returns: (unprocessed_paths, processed_results)
      - unprocessed_paths: Files that need to be analyzed (new or modified)
      - processed_results: Dictionary of path -> cached analysis metrics for fresh files
    """
    unprocessed_paths = []
    processed_results = {}
    
    for path in image_paths:
        try:
            mtime = os.path.getmtime(path)
            
            # Check corresponding XMP mtime if it exists
            xmp_path = get_xmp_path(path)
            xmp_mtime = os.path.getmtime(xmp_path) if os.path.exists(xmp_path) else 0.0
            
            # Fetch from cache database
            cached = get_cached_item(path, mtime, xmp_mtime)
            if cached and cached.get('metrics'):
                # Ensure the cache version matches current engine scoring standards (v4)
                if cached['metrics'].get("scoring_version", 0) >= 4:
                    processed_results[path] = cached
                    continue
                    
            # If not in cache or version is outdated, add to unprocessed list
            unprocessed_paths.append(path)
        except OSError:
            # Handle deleted or locked files gracefully
            unprocessed_paths.append(path)
            
    return unprocessed_paths, processed_results
