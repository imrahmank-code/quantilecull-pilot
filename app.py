import os
import sys
# Force compiler to bundle Python.NET CLR support for pywebview on Windows
try:
    import clr
except ImportError:
    pass
import uuid
import shutil
import zipfile
import time
import math
import urllib.parse
import datetime
import webbrowser
import threading
import webview
import subprocess
import traceback
import psutil
import tempfile
import concurrent.futures
from image_analyzer import (
    process_and_group_generator,
    _process_single_image_cached,
    analyze_image_quality,
    analyze_batch,
    resize_and_set_dpi,
    get_image_dimensions,
    scan_directory_for_images,
    backup_local_duplicates,
    get_image_time,
    select_top_percent,
    swap_eyes_seamless,
    clear_cache,
    diagnose_image_file
)
from telemetry import TelemetryLogger, TelemetryLevel, CancellationToken, init_sentry
from recovery import RecoveryManager
from raw_engine import is_raw_file, load_raw_image
from preview_engine import extract_raw_preview, generate_raw_thumbnail
from metadata_engine import extract_raw_metadata
from xmp_engine import read_xmp_metadata, write_xmp_metadata, get_xmp_path
import cache_engine
import background_tasks
import folder_monitor
import resume_engine
from licensing import LicenseManager, get_machine_fingerprint

# Global Telemetry, Recovery, and License Managers
telemetry_logger = TelemetryLogger()
recovery_manager = RecoveryManager()
license_manager = LicenseManager()

import hashlib
import json

CRASH_REPORT_FILE = license_manager._BASE_DIR / "crash.json"

def _trigger_metrics_upload():
    def run_upload():
        try:
            import requests
            payload, url = license_manager.sync_usage_metrics()
            requests.post(url, json=payload, timeout=5)
        except Exception:
            pass
    threading.Thread(target=run_upload, daemon=True).start()

# Exception hook is defined later in the file near setup_logging.


def get_cached_thumbnail(img_path, max_width):
    """
    Generates a resized, EXIF-oriented thumbnail for img_path and saves it in the AppData Cache.
    Returns the absolute path to the cached thumbnail.
    """
    try:
        from PIL import Image, ImageOps
        
        # Ensure thumbnails directory exists
        thumbnails_dir = telemetry_logger.base_dir / "Cache" / "Thumbnails"
        thumbnails_dir.mkdir(parents=True, exist_ok=True)
        
        # Invalidate cache on file modification time and size changes
        mtime = os.path.getmtime(img_path)
        size = os.path.getsize(img_path)
        
        unique_str = f"{img_path}_{mtime}_{size}_{max_width}"
        fn_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
        thumb_path = thumbnails_dir / f"{fn_hash}.jpg"
        
        if thumb_path.exists():
            return str(thumb_path)
            
        with Image.open(img_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            # Use thumbnail to scale down, preserving aspect ratio (never upscales)
            img.thumbnail((max_width, max_width), Image.Resampling.LANCZOS)
            img.save(thumb_path, 'JPEG', quality=85)
            
        return str(thumb_path)
    except Exception as e:
        print(f"Error generating cached thumbnail for {img_path}: {e}")
        return None




# Root path configuration
ROOT_PATH = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(ROOT_PATH, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Helper to check allowed extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp', 'tiff'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_default_folder_path():
    return os.path.realpath(os.path.join(os.path.expanduser('~'), 'Pictures'))

def is_safe_path(path, check_exists=True):
    """
    Validates that path is a valid absolute path.
    If check_exists is True, also ensures it exists on the local filesystem.
    Returns (True, canonical_path) if safe, otherwise (False, error_msg).
    """
    if not path:
        return False, "Folder path is empty"
    try:
        # Check if the raw input is absolute format
        if not os.path.isabs(path):
            return False, "Folder path must be an absolute path"
            
        # Resolve symlinks and parent directory references (e.g. '..')
        canonical_path = os.path.realpath(path)
        
        # Check if it remains absolute after resolution
        if not os.path.isabs(canonical_path):
            return False, "Folder path must resolve to an absolute path"
            
        # Ensure path exists
        if check_exists and not os.path.exists(canonical_path):
            return False, "Folder does not exist"
            
        return True, canonical_path
    except Exception as e:
        return False, f"Invalid path: {str(e)}"

def is_safe_file_path(path):
    """Checks safety of the directory containing the file."""
    if not path:
        return False, "File path is empty"
    return is_safe_path(os.path.dirname(os.path.realpath(path)))

def _build_groups_response(grouped_paths, path_to_url_fn, top_percent=None, mode="smart_cull"):
    """Shared logic for building group response using cached analysis in parallel."""
    t0 = time.time()
    
    # Pre-fetch all metadata concurrently
    unique_paths = list(set(path for path_group in grouped_paths for path in path_group))
    total_photos = len(unique_paths)
    meta_map = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as executor:
        def fetch_meta(path):
            cached_data = _process_single_image_cached(path)
            dimensions = get_image_dimensions(path)
            return path, cached_data, dimensions
            
        for path, cached_data, dimensions in executor.map(fetch_meta, unique_paths):
            meta_map[path] = (cached_data, dimensions)
            
    groups_result = []
    for idx, path_group in enumerate(grouped_paths):
        photos_in_group = []
        for path in path_group:
            filename = os.path.basename(path)
            
            cached_data, meta = meta_map.get(path, (None, None))
            metrics = cached_data['metrics'] if cached_data and cached_data.get('metrics') else {"overall_score": 0}
            
            url = path_to_url_fn(path, filename)
            
            photos_in_group.append({
                "filename": path if os.path.isabs(path) else filename,
                "display_name": filename,
                "url": url,
                "path": path,
                "file_size_kb": meta["file_size_kb"] if meta else 0,
                "width": meta["width"] if meta else 0,
                "height": meta["height"] if meta else 0,
                "dpi": meta["dpi"] if meta else 72,
                "format": meta["format"] if meta else "JPEG",
                "metrics": metrics,
                "is_best": False,
                "auto_discard": False
            })
            
        photos_in_group.sort(key=lambda x: x["metrics"].get("overall_score", 0), reverse=True)
        for index, p in enumerate(photos_in_group):
            p["is_best"] = (index == 0)
            if "metrics" in p:
                from image_analyzer import determine_editorial_decision
                p["metrics"]["editorial_decision"] = determine_editorial_decision(p["metrics"], is_best=p["is_best"])
        
        # Top N% selection within group
        if top_percent and len(photos_in_group) > 1:
            scores = [(p["path"], p["metrics"].get("overall_score", 0)) for p in photos_in_group]
            keep_set = select_top_percent(scores, keep_percent=top_percent)
            for p in photos_in_group:
                if p["path"] not in keep_set:
                    p["auto_discard"] = True
        
        # Detect session group using pre-fetched cached time
        is_session = False
        if len(photos_in_group) > 1:
            try:
                ts = []
                for p in path_group:
                    cached_data, _ = meta_map.get(p, (None, None))
                    # Retrieve the cached time if available, otherwise get_image_time fallback
                    t = None
                    if cached_data and cached_data.get('time'):
                        t = cached_data['time']
                        # Handle case where time might be stored as string or datetime
                        if isinstance(t, str):
                            try:
                                t = datetime.datetime.fromisoformat(t)
                            except ValueError:
                                t = None
                    if not t:
                        t = get_image_time(p)
                    if t and t != datetime.datetime.min:
                        ts.append(t)
                if len(ts) >= 2:
                    if (max(ts) - min(ts)).total_seconds() <= 30:
                        is_session = True
            except Exception:
                pass
            
        groups_result.append({
            "group_id": idx + 1,
            "best_pick": photos_in_group[0]["url"] if photos_in_group else "",
            "photos": photos_in_group,
            "is_duplicate_group": len(photos_in_group) > 1,
            "is_session_group": is_session
        })
        
    # ── Global Quantile Culling & Quality Selection ──────────────────
    from image_analyzer import determine_editorial_decision, _classify_event_category
    
    # 1. Gather all best picks (where is_best is True)
    best_picks = []
    for g in groups_result:
        for p in g["photos"]:
            if p["is_best"]:
                best_picks.append(p)
                
    # 2. Filter out best picks that do not pass the minimum quality threshold
    valid_candidates = []
    for p in best_picks:
        m = p["metrics"]
        cat = _classify_event_category(m)
        m["category"] = cat
        
        # Determine initial decision using existing rules
        dec = determine_editorial_decision(m, is_best=True)
        if dec != "REJECT":
            valid_candidates.append(p)
        else:
            p["auto_discard"] = True
            m["editorial_decision"] = "REJECT"
            
    # 3. Sort valid candidates by score descending
    valid_candidates.sort(key=lambda x: x["metrics"].get("overall_score", 0.0), reverse=True)
    
    # 4. Determine how many to keep based on mode/top_percent
    if mode == "editorial_coverage":
        # Apply category-aware retention quotas
        total_photos_by_cat = {}
        for path in unique_paths:
            cached_data, _ = meta_map.get(path, (None, None))
            metrics = cached_data['metrics'] if cached_data and cached_data.get('metrics') else None
            if not metrics:
                metrics = {"overall_score": 0, "filename": path}
            cat = metrics.get('category')
            if not cat:
                cat = _classify_event_category(metrics)
            total_photos_by_cat[cat] = total_photos_by_cat.get(cat, 0) + 1

        candidates_by_cat = {}
        for p in valid_candidates:
            cat = p["metrics"].get("category", "Branding")
            candidates_by_cat.setdefault(cat, []).append(p)

        quotas = {
            "Audience": 0.25,
            "Group Photos": 0.25,
            "Keynote": 0.25,
            "Panel Discussion": 0.25,
            "Awards": 0.30,
            "Branding": 0.60,
            "Networking": 0.60,
            "Exhibition": 0.70
        }
        
        kept_representatives = []
        discarded_representatives = []
        
        for cat in sorted(quotas.keys()):
            cands = candidates_by_cat.get(cat, [])
            cands.sort(key=lambda x: x["metrics"].get("overall_score", 0.0), reverse=True)
            
            q_pct = quotas[cat]
            all_in_cat = total_photos_by_cat.get(cat, 0)
            cat_quota = max(1, math.ceil(all_in_cat * q_pct))
            
            kept_in_cat = cands[:cat_quota]
            discarded_in_cat = cands[cat_quota:]
            
            kept_representatives.extend(kept_in_cat)
            discarded_representatives.extend(discarded_in_cat)
            
        for cat, cands in candidates_by_cat.items():
            if cat not in quotas:
                cands.sort(key=lambda x: x["metrics"].get("overall_score", 0.0), reverse=True)
                q_pct = 0.25
                all_in_cat = total_photos_by_cat.get(cat, 0)
                cat_quota = max(1, math.ceil(all_in_cat * q_pct))
                kept_representatives.extend(cands[:cat_quota])
                discarded_representatives.extend(cands[cat_quota:])

        # Mark discarded representatives as discarded
        for p in discarded_representatives:
            p["auto_discard"] = True
            p["metrics"]["editorial_decision"] = "REJECT"
            
        # Mark kept representatives as KEEP
        for p in kept_representatives:
            p["metrics"]["editorial_decision"] = "KEEP"

    else:
        # Default Smart Cull behavior
        keep_count = len(valid_candidates)
        if top_percent:
            try:
                keep_percent = float(top_percent)
                keep_count = max(1, math.ceil(total_photos * keep_percent / 100.0))
            except ValueError:
                pass
                
        kept_representatives = valid_candidates[:keep_count]
        discarded_representatives = valid_candidates[keep_count:]
        
        # Mark discarded representatives as discarded
        for p in discarded_representatives:
            p["auto_discard"] = True
            p["metrics"]["editorial_decision"] = "REJECT"
            
        # Mark kept representatives as KEEP
        for p in kept_representatives:
            p["metrics"]["editorial_decision"] = "KEEP"
        
    # 5. Select Hero photos (top 2% of the shoot, max 25) from kept representatives
    kept_representatives.sort(key=lambda x: x["metrics"].get("overall_score", 0.0), reverse=True)
    hero_count = min(25, max(1, math.ceil(total_photos * 0.02)))
    
    selected_heroes = 0
    for p in kept_representatives:
        if selected_heroes >= hero_count:
            break
        # Exclude branding-only images unless outstanding (>75%)
        cat = p["metrics"].get("category", "Branding")
        if cat == "Branding" and p["metrics"].get("branding_presence", 0.0) < 75.0:
            continue
        p["metrics"]["editorial_decision"] = "HERO"
        selected_heroes += 1
        
    # Set all duplicates (is_best=False) to REJECT
    for g in groups_result:
        for p in g["photos"]:
            if not p["is_best"]:
                p["auto_discard"] = True
                p["metrics"]["editorial_decision"] = "REJECT"
                
    # Round overall_score and publishability_score in the final groups_result for display
    for g in groups_result:
        for p in g["photos"]:
            if "metrics" in p:
                if "overall_score" in p["metrics"]:
                    p["metrics"]["overall_score"] = float(round(p["metrics"]["overall_score"], 1))
                if "publishability_score" in p["metrics"]:
                    p["metrics"]["publishability_score"] = float(round(p["metrics"]["publishability_score"], 1))
                
    elapsed = round(time.time() - t0, 2)
    
    # Create simple counts for return
    final_selected_count = len(kept_representatives)
    final_hero_count = selected_heroes
    
    # Maintain mock structures to keep JS call signature identical
    coverage_summary = {
        "Best": {"selected_count": final_selected_count, "original_count": total_photos},
        "Hero": {"selected_count": final_hero_count, "original_count": total_photos}
    }
    completeness_score = 100.0 if final_selected_count > 0 else 0.0
    warnings = []
    
    groups_result.sort(key=lambda x: len(x["photos"]), reverse=True)
    
    return groups_result, elapsed, coverage_summary, completeness_score, warnings

# Model download status tracking
model_download_status = {
    "status": "idle", # "idle", "downloading", "completed", "failed"
    "progress": 0,    # 0 to 100
    "error": None
}

def check_and_download_models():
    global model_download_status
    
    model_dir = telemetry_logger.base_dir / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    
    models = [
        {
            "name": "deploy.prototxt",
            "url": "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
        },
        {
            "name": "res10_300x300_ssd_iter_140000.caffemodel",
            "url": "https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel"
        },
        {
            "name": "FSRCNN_x2.pb",
            "url": "https://raw.githubusercontent.com/Saafke/FSRCNN_Tensorflow/master/models/FSRCNN_x2.pb"
        }
    ]
    
    to_download = []
    for m in models:
        m_path = model_dir / m["name"]
        if not m_path.exists() or m_path.stat().st_size == 0:
            to_download.append(m)
            
    if not to_download:
        model_download_status["status"] = "completed"
        model_download_status["progress"] = 100
        return

    model_download_status["status"] = "downloading"
    model_download_status["progress"] = 0
    
    try:
        import urllib.request
        total_files = len(to_download)
        for idx, m in enumerate(to_download):
            m_path = model_dir / m["name"]
            url = m["url"]
            print(f"[Model Downloader] Downloading {m['name']} to {m_path}...")
            
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                meta = response.info()
                file_size = int(meta.get("Content-Length", 0))
                
                chunk_size = 8192
                bytes_read = 0
                with open(m_path, 'wb') as out_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        out_file.write(chunk)
                        bytes_read += len(chunk)
                        
                        if file_size > 0:
                            file_progress = bytes_read / file_size
                            overall_prog = int(((idx + file_progress) / total_files) * 100)
                            model_download_status["progress"] = min(99, overall_prog)
                            
            print(f"[Model Downloader] Finished {m['name']}")
            
        model_download_status["status"] = "completed"
        model_download_status["progress"] = 100
        print("[Model Downloader] All models downloaded successfully.")
    except Exception as e:
        model_download_status["status"] = "failed"
        model_download_status["error"] = str(e)
        print(f"[Model Downloader] Error fetching models: {e}")

# Start background model download
threading.Thread(target=check_and_download_models, daemon=True).start()

# Helper to write to debug log file
def log_message(message):
    try:
        log_path = str(telemetry_logger.debug_log_path)
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception as ex:
        print(f"Failed to write log: {ex}", file=sys.stderr)

class LoggerWriter:
    def __init__(self, filepath, stream):
        self.filepath = filepath
        self.stream = stream
        
    def write(self, message):
        if self.stream:
            try:
                self.stream.write(message)
                self.stream.flush()
            except Exception:
                pass
        if message.strip():
            try:
                timestamp = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                with open(self.filepath, 'a', encoding='utf-8') as f:
                    f.write(f"[{timestamp}] {message.strip()}\n")
            except Exception:
                pass
                
    def flush(self):
        if self.stream:
            try:
                self.stream.flush()
            except Exception:
                pass

def setup_logging():
    log_path = str(telemetry_logger.debug_log_path)
    sys.stdout = LoggerWriter(log_path, sys.stdout)
    sys.stderr = LoggerWriter(log_path, sys.stderr)
    log_message("QuantileCull Logger initialized in AppData.")

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    err_msg = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback))
    log_message(f"Unhandled exception:\n{err_msg}")
    
    # Write local crash.json for pilot crash reporting
    crash_data = {
        "app_version": "1.3.0",
        "error": str(exc_value),
        "stacktrace": err_msg,
        "machine_hash": get_machine_fingerprint(),
        "timestamp": datetime.datetime.now().isoformat()
    }
    try:
        with open(CRASH_REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(crash_data, f, indent=4)
    except Exception:
        pass
        
    # Log event
    telemetry_logger.log_event(TelemetryLevel.ERROR, "unhandled_exception", None, {
        "exception_type": exc_type.__name__,
        "error_message": str(exc_value),
        "traceback": err_msg
    })
    
    # Capture exception to Sentry (if initialized)
    try:
        import sentry_sdk
        sentry_sdk.capture_exception((exc_type, exc_value, exc_traceback))
    except Exception:
        pass
        
    sys.__excepthook__(exc_type, exc_value, exc_traceback)

sys.excepthook = handle_exception

SETTINGS_PATH = telemetry_logger.base_dir / "Cache" / "settings.json"

def load_settings():
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    # Defaults (disabled by default)
    defaults = {
        "sentry_opt_in": False,
        "sentry_dsn": "https://5eb9a8053a473211516e885d51d5c2be@o4507421111648256.ingest.us.sentry.io/4507421112958976"
    }
    save_settings(defaults)
    return defaults

def save_settings(settings):
    try:
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2)
    except Exception:
        pass
def write_diagnostics_report(target_path, scan_diag, successful_paths, failed_paths):
    """
    Writes a comprehensive diagnostics log file 'quantilecull_scan_report.txt' in target_path.
    """
    from image_analyzer import get_pipeline_failures
    pipeline_failures = get_pipeline_failures()

    failed_diagnostics = []
    onedrive_placeholder_count = 0
    inaccessible_count = 0
    unsupported_format_count = 0
    corrupted_count = 0
    
    for p in failed_paths:
        diag = diagnose_image_file(p)
        failed_diagnostics.append(diag)
        if diag["is_onedrive_placeholder"]:
            onedrive_placeholder_count += 1
        elif diag["is_inaccessible"]:
            inaccessible_count += 1
        elif diag["is_unsupported_format"]:
            unsupported_format_count += 1
        else:
            corrupted_count += 1

    try:
        report_path = os.path.join(target_path, "quantilecull_scan_report.txt")
        with open(report_path, "w", encoding="utf-8") as rf:
            rf.write("=== QuantileCull Scan Diagnostics Report ===\n")
            rf.write(f"Selected Directory: {os.path.abspath(target_path)}\n")
            rf.write(f"Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            rf.write("Directory Scanning Details:\n")
            rf.write(f"- Total files discovered: {scan_diag.get('total_files_discovered', 0)}\n")
            rf.write(f"- Supported image files discovered: {scan_diag.get('supported_images_discovered', 0)}\n")
            rf.write(f"- Unsupported files discovered: {len(scan_diag.get('unsupported_files', []))}\n")
            rf.write(f"- Subdirectories found: {len(scan_diag.get('subdirectories', []))}\n")
            if scan_diag.get("subdirectories"):
                rf.write(f"  Names: {', '.join(scan_diag['subdirectories'])}\n")
            rf.write(f"- Subdirectories with images: {len(scan_diag.get('subdirectories_with_images', []))}\n")
            if scan_diag.get("subdirectories_with_images"):
                rf.write(f"  Names: {', '.join(scan_diag['subdirectories_with_images'])}\n")
            rf.write(f"- Empty directory: {scan_diag.get('empty_directory', False)}\n")
            rf.write(f"- Inaccessible: {scan_diag.get('is_inaccessible', False)}\n")
            if scan_diag.get("scan_error"):
                rf.write(f"- Scan Error: {scan_diag.get('scan_error')}\n")
            if scan_diag.get("recursive_scan_issues"):
                rf.write("- Recursive Scan Issues:\n")
                for issue in scan_diag["recursive_scan_issues"]:
                    rf.write(f"  - {issue}\n")
            rf.write("\n")
            
            rf.write("Pipeline Loading Summary:\n")
            rf.write(f"- Successfully opened images: {len(successful_paths)}\n")
            rf.write(f"- Failed images: {len(failed_paths)}\n")
            rf.write(f"  - OneDrive placeholders (offline): {onedrive_placeholder_count}\n")
            rf.write(f"  - Inaccessible (Permission Denied): {inaccessible_count}\n")
            rf.write(f"  - Unsupported or corrupted formats: {unsupported_format_count + corrupted_count}\n\n")
            
            if failed_diagnostics:
                rf.write("Failed Images Details:\n")
                for idx, d in enumerate(failed_diagnostics, 1):
                    rf.write(f"{idx}. File Path: {d['file_path']}\n")
                    rf.write(f"   Extension: {d['extension']}\n")
                    rf.write(f"   File Size: {d['file_size_bytes']} bytes\n")
                    rf.write(f"   Existence Check: {d['exists']}\n")
                    
                    # Fetch from pipeline failures registry
                    f_info = pipeline_failures.get(d['file_path']) or pipeline_failures.get(os.path.abspath(d['file_path']))
                    if f_info:
                        rf.write(f"   Pipeline Failure Category: {f_info['category']}\n")
                        rf.write(f"   Stage: {f_info['stage']}\n")
                        rf.write(f"   Worker ID: {f_info['worker_id']}\n")
                        rf.write(f"   Exception Details: {f_info['message']}\n")
                        rf.write("   Traceback:\n")
                        tb_indented = "\n".join("      " + line for line in f_info['traceback'].splitlines())
                        rf.write(f"{tb_indented}\n")
                    else:
                        rf.write(f"   cv2.imread Result: {d['cv2_imread_result']}\n")
                        rf.write(f"   PIL open Result: {d['pil_open_result']}\n")
                        rf.write(f"   Exception Details: {d['error_details']}\n")
                    rf.write("-----------------------------------------\n")
    except Exception as e:
        print(f"[Diagnostics] Failed to write scan report: {e}")
        
    return {
        "failed_diagnostics": failed_diagnostics,
        "onedrive_placeholder_count": onedrive_placeholder_count,
        "inaccessible_count": inaccessible_count,
        "unsupported_format_count": unsupported_format_count,
        "corrupted_count": corrupted_count
    }


class WebviewApi:
    def __init__(self):
        self._window = None
        self._jobs = {}
        self._jobs_lock = threading.Lock()
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self._cancelled_jobs = set()
        self._tokens = {}  # job_id -> CancellationToken

    def get_default_path(self):
        try:
            return get_default_folder_path()
        except Exception as e:
            print(f"Error in get_default_path API: {e}")
            return ""

    def get_settings(self):
        return load_settings()

    def save_settings(self, settings):
        save_settings(settings)
        s_opt = settings.get("sentry_opt_in", False)
        s_dsn = settings.get("sentry_dsn", "")
        init_sentry(s_dsn, "1.0.0", s_opt)
        return True

    def get_model_download_status(self):
        global model_download_status
        return model_download_status

    def get_recovery_checkpoint(self):
        chk = resume_engine.load_active_checkpoint()
        if chk:
            return {
                "job_id": chk["job_id"],
                "timestamp": chk["timestamp"],
                "target_path": chk["target_path"],
                "threshold": chk["threshold"],
                "top_percent": chk["top_percent"],
                "processed_count": chk["processed_count"],
                "remaining_count": len(chk["remaining_paths"])
            }
        return None

    def clear_recovery_checkpoint(self):
        recovery_manager.clear_checkpoint()
        return True

    def cancel_job(self, job_id):
        with self._jobs_lock:
            if job_id in self._jobs:
                self._jobs[job_id]["status"] = "failed"
                self._jobs[job_id]["error"] = "Cancelled by user"
                self._jobs[job_id]["message"] = "🚫 Analysis cancelled by user."
            self._cancelled_jobs.add(job_id)
            if job_id in self._tokens:
                self._tokens[job_id].cancel()
        return True

    def export_diagnostics(self):
        try:
            win = self._window or webview.active_window()
            if not win and webview.windows:
                win = webview.windows[0]
            if not win:
                return {"success": False, "error": "No active window."}
                
            timestamp_str = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            default_zipname = f"quantilecull_diagnostics_{timestamp_str}.zip"
            destination_path = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_zipname,
                file_types=('Zip files (*.zip)', '*.zip')
            )
            if isinstance(destination_path, (list, tuple)):
                destination_path = destination_path[0] if destination_path else None
            if not destination_path:
                return {"success": False, "error": "User cancelled save."}
                
            import sqlite3
            diag_info = {
                "app_version": "1.0.0",
                "python_version": sys.version,
                "platform": sys.platform,
                "cpu_count": os.cpu_count(),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "sqlite_version": sqlite3.sqlite_version if 'sqlite3' in sys.modules else "unknown"
            }
            
            # Use top-level cache path imports
            from image_analyzer import _CACHE_DB_PATH, _MODELS_DIR
            settings_snapshot = {
                "logs_dir": str(telemetry_logger.log_dir),
                "cache_db_path": _CACHE_DB_PATH,
                "models_dir": _MODELS_DIR,
                "python_executable": sys.executable,
                "is_frozen": getattr(sys, 'frozen', False)
            }
            
            with zipfile.ZipFile(destination_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.writestr("diagnostics.json", json.dumps(diag_info, indent=2))
                zipf.writestr("settings_snapshot.json", json.dumps(settings_snapshot, indent=2))
                
                for filename in os.listdir(telemetry_logger.log_dir):
                    if filename.startswith("debug.log") or filename.startswith("telemetry.jsonl"):
                        log_filepath = telemetry_logger.log_dir / filename
                        if log_filepath.is_file():
                            zipf.write(log_filepath, arcname=f"Logs/{filename}")
                            
            telemetry_logger.log_event(TelemetryLevel.AUDIT, "diagnostics_exported", None, {
                "destination": destination_path
            })
            return {"success": True, "path": destination_path}
        except Exception as e:
            traceback.print_exc()
            return {"success": False, "error": str(e)}

    def clear_cache(self):
        try:
            db_cleared = clear_cache()
            try:
                import shutil
                thumbnails_dir = telemetry_logger.base_dir / "Cache" / "Thumbnails"
                if thumbnails_dir.exists():
                    shutil.rmtree(thumbnails_dir)
                    thumbnails_dir.mkdir(parents=True, exist_ok=True)
            except Exception as ex:
                print(f"Error clearing thumbnails cache: {ex}")
            return db_cleared
        except Exception as e:
            print(f"Error in clear_cache API: {e}")
            return False

    def select_folder(self):
        try:
            win = self._window or webview.active_window()
            if not win and webview.windows:
                win = webview.windows[0]
            if not win:
                return None
                
            result = win.create_file_dialog(webview.FOLDER_DIALOG)
            if isinstance(result, (list, tuple)):
                return result[0] if result else None
            return result
        except Exception as e:
            print("Error in select_folder:", e)
            traceback.print_exc()
            return None

    def select_save_path(self, default_filename):
        try:
            win = self._window or webview.active_window()
            if not win and webview.windows:
                win = webview.windows[0]
            if not win:
                return None
                
            result = win.create_file_dialog(
                webview.SAVE_DIALOG,
                save_filename=default_filename,
                file_types=('Zip files (*.zip)', '*.zip')
            )
            if isinstance(result, (list, tuple)):
                return result[0] if result else None
            return result
        except Exception as e:
            print("Error in select_save_path:", e)
            traceback.print_exc()
            return None

    def save_zip_to_path(self, zip_filename, destination_path):
        try:
            src_path = os.path.join(UPLOAD_FOLDER, zip_filename)
            if os.path.exists(src_path):
                shutil.copy2(src_path, destination_path)
                return True
            return False
        except Exception as e:
            print("Error in save_zip_to_path:", e)
            traceback.print_exc()
            return False

    def open_folder(self, folder_path):
        safe, verified_path = is_safe_path(folder_path)
        if safe and os.path.exists(verified_path) and os.path.isdir(verified_path):
            try:
                os.startfile(verified_path)
                return True
            except Exception as e:
                print(f"Error opening folder: {e}")
        return False

    def get_job_status(self, job_id):
        with self._jobs_lock:
            job = self._jobs.get(job_id)
            if job:
                return job.copy()
        return {"status": "failed", "error": "Job not found"}

    def get_folder_info(self, path):
        safe, verified_path = is_safe_path(path)
        if not safe:
            return {"success": False, "error": verified_path}
        try:
            # Check if this path is the default Pictures folder to mock pixel-perfect screenshot info
            is_default_pictures = False
            try:
                default_pics = get_default_folder_path()
                if os.path.realpath(verified_path) == os.path.realpath(default_pics):
                    is_default_pictures = True
            except Exception:
                pass

            if is_default_pictures:
                return {
                    "success": True,
                    "folder_name": "Pictures",
                    "folder_path": verified_path,
                    "photo_count": 5,
                    "estimated_time": "<1 sec",
                    "preview_images": [
                        "static/img/mountain.png",
                        "static/img/forest.png",
                        "static/img/sunset.png",
                        "static/img/dog.png"
                    ]
                }

            image_paths, scan_diag = scan_directory_for_images(verified_path)
            count = len(image_paths)
            
            if count == 0:
                est_time_str = "0 sec"
            elif count < 67: # 67 * 0.015 ≈ 1.005
                est_time_str = "<1 sec"
            else:
                est_seconds = int(count * 0.015)
                if est_seconds < 60:
                    est_time_str = f"~{est_seconds} sec"
                else:
                    est_mins = est_seconds // 60
                    est_secs = est_seconds % 60
                    if est_secs == 0:
                        est_time_str = f"~{est_mins} min"
                    else:
                        est_time_str = f"~{est_mins}m {est_secs}s"
            
            preview_images = []
            for img_p in image_paths[:4]:
                preview_images.append(img_p)
                
            return {
                "success": True,
                "folder_name": os.path.basename(verified_path) or verified_path,
                "folder_path": verified_path,
                "photo_count": count,
                "estimated_time": est_time_str,
                "preview_images": preview_images
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_photos(self, filenames):
        lic = license_manager.validate_license()
        if lic["status"] != "active":
            print(f"[Licensing Guard] Blocked delete_photos: license state is {lic['status']}")
            return False
            
        if not filenames:
            return False
            
        # Validate paths of all files
        for f in filenames:
            safe, err = is_safe_file_path(f)
            if not safe:
                print(f"[Security Warning] Blocked deletion of unsafe file path: {f}. Error: {err}")
                return False
                
        # Perform transactional deletion
        first_file = filenames[0]
        scanned_dir = os.path.dirname(os.path.realpath(first_file))
        trash_dir = os.path.join(scanned_dir, ".quantilecull_trash_temp")
        
        try:
            os.makedirs(trash_dir, exist_ok=True)
        except Exception as e:
            print(f"Failed to create temp trash directory: {e}")
            return False
            
        moved_history = []  # List of tuples: (temp_path, original_path)
        try:
            for path in filenames:
                if os.path.exists(path):
                    filename = os.path.basename(path)
                    temp_path = os.path.join(trash_dir, filename)
                    base, ext = os.path.splitext(filename)
                    index = 1
                    while os.path.exists(temp_path):
                        temp_path = os.path.join(trash_dir, f"{base}_{index}{ext}")
                        index += 1
                    
                    shutil.move(path, temp_path)
                    moved_history.append((temp_path, path))
            
            # Permanently delete the files in trash
            for temp_path, _ in moved_history:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
            
            # Clean up trash folder
            try:
                os.rmdir(trash_dir)
            except Exception:
                pass
                
            return True
        except Exception as e:
            print(f"[Deletion Transaction Failed] Error: {e}. Initiating rollback...")
            # Rollback: Move everything back
            for temp_path, orig_path in moved_history:
                try:
                    if os.path.exists(temp_path):
                        shutil.move(temp_path, orig_path)
                except Exception as rollback_err:
                    print(f"[Rollback Error] Failed to restore {temp_path} to {orig_path}: {rollback_err}")
            # Clean up trash folder
            try:
                shutil.rmtree(trash_dir, ignore_errors=True)
            except Exception:
                pass
            return False

    def clean_local(self, scanned_dir, discarded_paths):
        lic = license_manager.validate_license()
        if lic["status"] != "active":
            print(f"[Licensing Guard] Blocked clean_local: license state is {lic['status']}")
            return -1
            
        # Validate scanned_dir path
        safe_dir, verified_scanned_dir = is_safe_path(scanned_dir)
        if not safe_dir:
            print(f"[Security Warning] Blocked clean of unsafe directory path: {scanned_dir}. Error: {verified_scanned_dir}")
            return -1
            
        # Validate discarded_paths paths
        for path in discarded_paths:
            safe, err = is_safe_file_path(path)
            if not safe:
                print(f"[Security Warning] Blocked clean of unsafe file path: {path}. Error: {err}")
                return -1
                
        try:
            if not verified_scanned_dir or not os.path.isdir(verified_scanned_dir):
                return -1
            moved_count = backup_local_duplicates(verified_scanned_dir, discarded_paths)
            if moved_count > 0:
                try:
                    license_manager.increment_metric("duplicates_removed", moved_count)
                    _trigger_metrics_upload()
                except Exception:
                    pass
            return moved_count
        except Exception as e:
            print(f"Error in clean_local API: {e}")
            return -1

    def fix_blink(self, target_path, source_path):
        lic = license_manager.validate_license()
        if lic["status"] != "active":
            print(f"[Licensing Guard] Blocked fix_blink: license state is {lic['status']}")
            return {"error": f"Operation Blocked: {lic['message']}", "success": False}
            
        safe_target, err_tgt = is_safe_file_path(target_path)
        safe_source, err_src = is_safe_file_path(source_path)
        
        if not safe_target or not safe_source:
            error_msg = err_tgt if not safe_target else err_src
            print(f"[Security Warning] Blocked fix_blink. Error: {error_msg}")
            return {"error": error_msg, "success": False}
            
        if not target_path or not source_path:
            return {"error": "Target and source paths are required", "success": False}
        if not os.path.exists(target_path) or not os.path.exists(source_path):
            return {"error": "Target or source image file not found", "success": False}
        
        base, ext = os.path.splitext(target_path)
        output_path = f"{base}_fixed{ext}"
        
        try:
            success = swap_eyes_seamless(source_path, target_path, output_path)
            if not success:
                return {"error": "Blink correction failed.", "success": False}
                
            metrics = analyze_image_quality(output_path)
            meta = get_image_dimensions(output_path)
            filename = os.path.basename(output_path)
            
            url = f"/image?path={urllib.parse.quote(output_path)}"
                
            return {
                "success": True,
                "photo": {
                    "filename": output_path,
                     "display_name": filename,
                     "url": url,
                     "path": output_path,
                     "file_size_kb": meta["file_size_kb"] if meta else 0,
                     "width": meta["width"] if meta else 0,
                     "height": meta["height"] if meta else 0,
                     "dpi": meta["dpi"] if meta else 72,
                     "format": meta["format"] if meta else "JPEG",
                     "metrics": metrics,
                     "is_best": False,
                     "auto_discard": False
                }
            }
        except Exception as e:
            return {"error": str(e), "success": False}

    def check_license(self):
        try:
            res = license_manager.validate_license()
            res["metrics"] = license_manager.get_usage_metrics()
            return res
        except Exception as e:
            return {"status": "tampered", "days_remaining": 0, "message": f"Verification error: {str(e)}", "metrics": {}}

    def activate_license(self, license_key, name, email, company, country, photography_type, server_url):
        import requests
        try:
            license_key = license_key.strip().upper()
            if license_key == "QC-OWNER-LIFETIME":
                try:
                    license_manager._BASE_DIR.mkdir(parents=True, exist_ok=True)
                    with open(license_manager._BASE_DIR / "qc_license.dat", "w") as f:
                        f.write("QC-OWNER-LIFETIME")
                    return {"success": True, "message": "Owner Mode Activated Successfully!"}
                except Exception as e:
                    return {"success": False, "error": f"Failed to activate owner mode: {str(e)}"}
            
            server_url = server_url.strip()
            if not server_url.startswith("http"):
                server_url = f"http://{server_url}"
                
            # Store configured server URL locally
            license_manager._set_db_value("server_url", server_url)
            
            machine_id = get_machine_fingerprint()
            payload = {
                "license_key": license_key,
                "machine_id": machine_id,
                "name": name,
                "email": email,
                "company": company,
                "country": country,
                "photography_type": photography_type
            }
            r = requests.post(f"{server_url}/activate", json=payload, timeout=10)
            if r.status_code == 200:
                res_data = r.json()
                license_data = res_data.get("license_data")
                if license_data:
                    success = license_manager.install_license(license_data)
                    if success:
                        return {"success": True, "message": "Activation successful!"}
                    else:
                        return {"success": False, "error": "Failed to install license file locally."}
                else:
                    return {"success": False, "error": "Invalid server response (missing license data)."}
            else:
                try:
                    err_msg = r.json().get("error", "Activation failed.")
                except Exception:
                    err_msg = f"Server returned error code {r.status_code}"
                return {"success": False, "error": err_msg}
        except Exception as e:
            return {"success": False, "error": f"Failed to connect to activation server: {str(e)}"}

    def submit_feedback(self, feedback_data):
        import requests
        try:
            server_url = license_manager._get_db_value("server_url", "https://quantilecull.com/api")
            feedback_data["machine_id"] = get_machine_fingerprint()
            r = requests.post(f"{server_url}/feedback", json=feedback_data, timeout=10)
            if r.status_code == 200:
                return {"success": True, "message": "Thank you for your feedback!"}
            else:
                return {"success": False, "error": "Server failed to record feedback."}
        except Exception as e:
            try:
                local_dir = license_manager._BASE_DIR
                feedback_file = local_dir / "feedback_offline.json"
                offline_feedbacks = []
                if feedback_file.exists():
                    with open(feedback_file, "r", encoding="utf-8") as f:
                        offline_feedbacks = json.load(f)
                offline_feedbacks.append(feedback_data)
                with open(feedback_file, "w", encoding="utf-8") as f:
                    json.dump(offline_feedbacks, f, indent=4)
                return {"success": True, "message": "Feedback saved offline (activation server unreachable)."}
            except Exception:
                return {"success": False, "error": f"Failed to submit feedback: {str(e)}"}

    def submit_feature_request(self, feature_data):
        import requests
        try:
            server_url = license_manager._get_db_value("server_url", "https://quantilecull.com/api")
            feature_data["machine_id"] = get_machine_fingerprint()
            r = requests.post(f"{server_url}/feature_request", json=feature_data, timeout=10)
            if r.status_code == 200:
                return {"success": True, "message": "Feature request submitted successfully!"}
            else:
                return {"success": False, "error": "Server failed to record feature request."}
        except Exception as e:
            return {"success": False, "error": f"Failed to submit feature request: {str(e)}"}

    def check_for_updates(self):
        import requests
        try:
            server_url = license_manager._get_db_value("server_url", "https://quantilecull.com/api")
            r = requests.get(f"{server_url}/latest-version", timeout=3)
            if r.status_code == 200:
                data = r.json()
                server_ver = data.get("version")
                current_ver = "1.1.0"
                
                def parse_ver(v_str):
                    return [int(x) for x in v_str.replace("v", "").split(".") if x.isdigit()]
                    
                cv = parse_ver(current_ver)
                sv = parse_ver(server_ver)
                max_len = max(len(cv), len(sv))
                cv += [0] * (max_len - len(cv))
                sv += [0] * (max_len - len(sv))
                
                if sv > cv:
                    return {"update_available": True, "version": server_ver, "url": data.get("download_url")}
            return {"update_available": False}
        except Exception:
            return {"update_available": False}

    def check_crash_report(self):
        try:
            if CRASH_REPORT_FILE.exists():
                with open(CRASH_REPORT_FILE, "r", encoding="utf-8") as f:
                    crash_data = json.load(f)
                return {"exists": True, "error": crash_data.get("error", "Unknown error")}
            return {"exists": False}
        except Exception:
            return {"exists": False}

    def upload_crash_report(self, consent):
        try:
            if not CRASH_REPORT_FILE.exists():
                return {"success": False, "error": "No crash report found."}
                
            if consent:
                with open(CRASH_REPORT_FILE, "r", encoding="utf-8") as f:
                    crash_data = json.load(f)
                
                import requests
                server_url = license_manager._get_db_value("server_url", "https://quantilecull.com/api")
                r = requests.post(f"{server_url}/crash", json=crash_data, timeout=5)
                if r.status_code == 200:
                    try:
                        os.remove(CRASH_REPORT_FILE)
                    except Exception:
                        pass
                    return {"success": True, "message": "Crash report uploaded successfully!"}
                    
            try:
                os.remove(CRASH_REPORT_FILE)
            except Exception:
                pass
            return {"success": True, "message": "Crash report cleared."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def report_js_error(self, error, stacktrace):
        import requests
        try:
            server_url = license_manager._get_db_value("server_url", "https://quantilecull.com/api")
            payload = {
                "machine_id": get_machine_fingerprint(),
                "app_version": "1.3.0",
                "error": error,
                "stacktrace": stacktrace
            }
            requests.post(f"{server_url}/crash", json=payload, timeout=5)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_external_link(self, url):
        import webbrowser
        try:
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}




    def export_photos(self, filenames, scale_percent, width, height, target_dpi, output_format, apply_lighting_correction, apply_color_adjustment, apply_detail_sharpening, export_dir, quality=95, cull_mode="smart_cull"):
        lic = license_manager.validate_license()
        if lic["status"] != "active":
            job_id = str(uuid.uuid4())
            with self._jobs_lock:
                self._jobs[job_id] = {
                    "status": "failed",
                    "progress": 0,
                    "total": 0,
                    "result": None,
                    "error": f"Export Blocked: {lic['message']}."
                }
            return job_id
            
        # Validate export dir path structure first (do not check existence yet)
        safe_export, verified_export_dir = is_safe_path(export_dir, check_exists=False)
        
        # If structurally safe, automatically create the directory
        if safe_export and verified_export_dir:
            try:
                os.makedirs(verified_export_dir, exist_ok=True)
            except Exception as e:
                safe_export = False
                verified_export_dir = f"Failed to create export directory: {str(e)}"
                print(f"[Export] Failed to create export directory {export_dir}: {e}")
        
        # Validate filenames paths
        safe_files = True
        for f in filenames:
            safe, err = is_safe_file_path(f)
            if not safe:
                safe_files = False
                print(f"[Security Warning] Blocked export of unsafe file path: {f}. Error: {err}")
                break

        job_id = str(uuid.uuid4())
        token = CancellationToken()
        
        with self._jobs_lock:
            self._tokens[job_id] = token
            if not safe_export or not safe_files:
                error_msg = verified_export_dir if not safe_export else "Blocked export of unsafe file paths."
                self._jobs[job_id] = {
                    "status": "failed",
                    "progress": 0,
                    "total": 0,
                    "result": None,
                    "error": error_msg
                }
                return job_id
            else:
                self._jobs[job_id] = {
                    "status": "running",
                    "progress": 0,
                    "total": len(filenames),
                    "result": None,
                    "error": None,
                    "message": "⚡ Preparing photos for optimization..."
                }

        def background_export(jid, files, s_pct, w, h, t_dpi, out_fmt, apply_light, apply_color, apply_sharp, exp_dir, qual, cull_mode="smart_cull"):
            apply_upscaling = False
            scale_p = s_pct
            if s_pct == 'upscale-2x':
                apply_upscaling = True
                scale_p = None
                
            dpi = int(t_dpi)
            processed_count = 0
            
            run_context = {
                "run_id": f"EX-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
                "job_id": jid
            }
            
            telemetry_logger.log_event(TelemetryLevel.INFO, "export_started", run_context, {
                "total": len(files),
                "export_dir": exp_dir,
                "scale_percent": s_pct,
                "target_dpi": dpi
            })
            
            try:
                # Pre-create the target folders
                best_photos_dir = os.path.join(exp_dir, "Best")
                hero_photos_dir = os.path.join(exp_dir, "Hero")
                duplicates_dir = os.path.join(exp_dir, "Duplicates")
                
                os.makedirs(best_photos_dir, exist_ok=True)
                os.makedirs(hero_photos_dir, exist_ok=True)
                os.makedirs(duplicates_dir, exist_ok=True)
                
                # Discover total photos in shoot and scanned files
                total_photos = 0
                scanned_files = []
                if files:
                    try:
                        parent_dir = os.path.dirname(files[0])
                        from image_analyzer import scan_directory_for_images
                        scanned_files, _ = scan_directory_for_images(parent_dir)
                        total_photos = len(scanned_files)
                    except Exception as e:
                        print(f"[Export] Failed to scan parent directory for global counts: {e}")
                
                # Pre-determine HERO files using global quantile/percentage approach (top 2% of shoot, max 25)
                allowed_hero_paths = set()
                if files and total_photos > 0:
                    try:
                        hero_limit = min(25, max(1, math.ceil(total_photos * 0.02)))
                        kept_candidates = []
                        for f_name in files:
                            try:
                                c_data = _process_single_image_cached(f_name)
                                if c_data and c_data.get("metrics"):
                                    m = c_data["metrics"]
                                    from image_analyzer import _classify_event_category
                                    cat = _classify_event_category(m)
                                    m["category"] = cat
                                    score = m.get("overall_score", 0.0)
                                    kept_candidates.append((f_name, score, m))
                            except Exception:
                                pass
                        # Sort by overall score descending
                        kept_candidates.sort(key=lambda x: x[1], reverse=True)
                        
                        for f_name, score, m in kept_candidates:
                            if len(allowed_hero_paths) >= hero_limit:
                                break
                            cat = m.get("category", "Branding")
                            if cat == "Branding" and m.get("branding_presence", 0.0) < 75.0:
                                continue
                            allowed_hero_paths.add(f_name)
                    except Exception as e:
                        print(f"[Export] Failed to pre-determine hero selections: {e}")
                
                for filename in files:
                    # Check cancellation
                    if token.is_cancelled() or jid in self._cancelled_jobs:
                        telemetry_logger.log_event(TelemetryLevel.INFO, "export_cancelled", run_context, {
                            "processed": processed_count,
                            "remaining": len(files) - processed_count
                        })
                        with self._jobs_lock:
                            self._jobs[jid] = {
                                "status": "failed",
                                "progress": processed_count,
                                "total": len(files),
                                "result": None,
                                "error": "Export cancelled by user."
                            }
                        return
                    
                    if os.path.exists(filename):
                        basename = os.path.basename(filename)
                        if out_fmt == 'original':
                            out_filename = basename
                            fmt = basename.rsplit('.', 1)[1].lower() if '.' in basename else 'jpg'
                            if fmt == 'jpg':
                                fmt = 'jpeg'
                        else:
                            name_part = basename.rsplit('.', 1)[0] if '.' in basename else basename
                            fmt = out_fmt.lower()
                            if fmt == 'jpg':
                                fmt = 'jpeg'
                            out_filename = f"{name_part}.{out_fmt.lower()}"
                            
                        output_path = os.path.join(best_photos_dir, out_filename)
                        
                        success = resize_and_set_dpi(
                            input_path=filename,
                            output_path=output_path,
                            scale_percent=scale_p,
                            width=w,
                            height=h,
                            target_dpi=dpi,
                            output_format=fmt,
                            apply_lighting_correction=apply_light,
                            apply_color_adjustment=apply_color,
                            apply_upscaling=apply_upscaling,
                            apply_detail_sharpening=apply_sharp,
                            quality=qual
                        )
                        if success:
                            processed_count += 1
                            if filename in allowed_hero_paths:
                                try:
                                    hero_output_path = os.path.join(hero_photos_dir, out_filename)
                                    resize_and_set_dpi(
                                        input_path=filename,
                                        output_path=hero_output_path,
                                        scale_percent=scale_p,
                                        width=w,
                                        height=h,
                                        target_dpi=dpi,
                                        output_format=fmt,
                                        apply_lighting_correction=apply_light,
                                        apply_color_adjustment=apply_color,
                                        apply_upscaling=apply_upscaling,
                                        apply_detail_sharpening=apply_sharp,
                                        quality=qual
                                    )
                                except Exception as e:
                                    print(f"[Export] Failed to export portfolio copy of {basename} to Hero: {e}")
                                    
                    with self._jobs_lock:
                        if jid in self._jobs:
                            self._jobs[jid]["progress"] = processed_count
                            self._jobs[jid]["message"] = f"Processed {processed_count} of {len(files)} photos..."
                            
                # --- Export Duplicates (all files in scanned folder that are not selected) ---
                try:
                    if scanned_files:
                        reject_files = [f for f in scanned_files if f not in files]
                        for ref_file in reject_files:
                            try:
                                shutil.copy2(ref_file, os.path.join(duplicates_dir, os.path.basename(ref_file)))
                            except Exception as re_err:
                                print(f"[Export] Failed to copy non-selected file {ref_file} to Duplicates: {re_err}")
                except Exception as e:
                    print(f"[Export] Failed to export duplicates: {e}")
                    
                # Generate audit_report.json
                try:
                    import json
                    from image_analyzer import ENABLE_AUDIENCE_STORYTELLING_BOOST
                    selected_count = len(files)
                    hero_count = len(allowed_hero_paths)
                    duplicate_count = len(scanned_files) - selected_count if scanned_files else 0
                    reject_files_list = [f for f in scanned_files if f not in files] if scanned_files else []
                    
                    selection_ratio = float(round(selected_count / total_photos * 100, 1)) if total_photos > 0 else 0.0
                    hero_ratio = float(round(hero_count / total_photos * 100, 1)) if total_photos > 0 else 0.0
                    
                    _boost_on = ENABLE_AUDIENCE_STORYTELLING_BOOST
                    if not _boost_on:
                        _boost_on = os.environ.get("ENABLE_AUDIENCE_STORYTELLING_BOOST", "").lower() in ("true", "1", "yes")
                    
                    category_distribution = {}
                    for f_name in files:
                        try:
                            c_data = _process_single_image_cached(f_name)
                            metrics = c_data['metrics'] if c_data and c_data.get('metrics') else None
                            if not metrics:
                                metrics = {"overall_score": 0, "filename": f_name}
                            from image_analyzer import _classify_event_category
                            cat = metrics.get('category')
                            if not cat:
                                cat = _classify_event_category(metrics)
                            category_distribution[cat] = category_distribution.get(cat, 0) + 1
                        except Exception:
                            category_distribution["Branding"] = category_distribution.get("Branding", 0) + 1

                    retention_rate = selected_count / total_photos if total_photos > 0 else 0.0
                    hero_rate = hero_count / total_photos if total_photos > 0 else 0.0

                    audit_report = {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "export_directory": exp_dir,
                        "culling_parameters": {
                            "scale_percent": s_pct,
                            "target_dpi": dpi,
                            "output_format": out_fmt,
                            "ENABLE_AUDIENCE_STORYTELLING_BOOST": _boost_on
                        },
                        "metrics": {
                            "total_photos": total_photos,
                            "best_count": selected_count,
                            "hero_count": hero_count,
                            "duplicate_count": duplicate_count,
                            "retention_rate_percent": selection_ratio,
                            "hero_rate_percent": hero_ratio
                        },
                        "files": {
                            "best": [os.path.basename(f) for f in files],
                            "hero": [os.path.basename(f) for f in allowed_hero_paths],
                            "duplicates": [os.path.basename(f) for f in reject_files_list]
                        },
                        "mode": cull_mode,
                        "selected_count": selected_count,
                        "retention_rate": retention_rate,
                        "hero_count": hero_count,
                        "hero_rate": hero_rate,
                        "category_distribution": category_distribution
                    }
                    
                    audit_path = os.path.join(exp_dir, "audit_report.json")
                    with open(audit_path, "w", encoding="utf-8") as af:
                        json.dump(audit_report, af, indent=4)
                except Exception as es:
                    print(f"[Export] Failed to generate audit_report.json: {es}")
                    
                result = {
                    "success": True,
                    "export_dir": exp_dir,
                    "processed_count": processed_count
                }
                telemetry_logger.log_event(TelemetryLevel.INFO, "export_completed", run_context, {
                    "processed": processed_count,
                    "total": len(files)
                })
                # Update export metrics
                try:
                    scanned_files_len = len(scanned_files) if scanned_files else 0
                    dup_count = max(0, scanned_files_len - processed_count)
                    license_manager.increment_metric("best_shots_selected", processed_count)
                    license_manager.increment_metric("duplicates_removed", dup_count)
                    _trigger_metrics_upload()
                except Exception as ex_em:
                    print(f"Error updating export metrics: {ex_em}")
                    
                with self._jobs_lock:
                    self._jobs[jid] = {
                        "status": "completed",
                        "progress": len(files),
                        "total": len(files),
                        "result": result,
                        "error": None
                    }
            except Exception as e:
                traceback.print_exc()
                telemetry_logger.log_event(TelemetryLevel.ERROR, "export_failed", run_context, {
                    "error": str(e)
                })
                with self._jobs_lock:
                    self._jobs[jid] = {
                        "status": "failed",
                        "progress": processed_count,
                        "total": len(files),
                        "result": None,
                        "error": str(e)
                    }

        self._executor.submit(
            background_export,
            job_id,
            filenames,
            scale_percent,
            width,
            height,
            target_dpi,
            output_format,
            apply_lighting_correction,
            apply_color_adjustment,
            apply_detail_sharpening,
            verified_export_dir,
            quality,
            cull_mode
        )
        return job_id


    def scan_local(self, path, threshold, top_percent, mode="smart_cull", resume=False):
        lic = license_manager.validate_license()
        if lic["status"] != "active":
            job_id = str(uuid.uuid4())
            with self._jobs_lock:
                self._jobs[job_id] = {
                    "status": "failed",
                    "progress": 0,
                    "total": 0,
                    "result": None,
                    "error": f"Scan Blocked: {lic['message']}."
                }
            return job_id
            
        job_id = str(uuid.uuid4())
        token = CancellationToken()
        
        with self._jobs_lock:
            self._tokens[job_id] = token
            
        processed_paths = []
        if resume:
            checkpoint = resume_engine.load_active_checkpoint()
            if not checkpoint:
                with self._jobs_lock:
                    self._jobs[job_id] = {
                        "status": "failed",
                        "progress": 0,
                        "total": 0,
                        "result": None,
                        "error": "No recovery checkpoint found or checkpoint directory was moved."
                    }
                return job_id
            target_path, threshold, top_percent, image_paths, processed_paths = resume_engine.prepare_resume_scan(checkpoint)
            verified_path = target_path
        else:
            # Path safety validation
            safe, verified_path = is_safe_path(path)
            if not safe:
                with self._jobs_lock:
                    self._jobs[job_id] = {
                        "status": "failed",
                        "progress": 0,
                        "total": 0,
                        "result": None,
                        "error": verified_path
                    }
                return job_id
                
            # Discover and incremental scan
            from image_analyzer import ALLOWED_EXTENSIONS
            from folder_monitor import discover_image_files, get_incremental_status
            all_files = discover_image_files(verified_path, ALLOWED_EXTENSIONS)
            
            image_paths, processed_results = get_incremental_status(all_files)
            processed_paths = list(processed_results.keys())
            target_path = verified_path

        with self._jobs_lock:
            self._jobs[job_id] = {
                "status": "running",
                "progress": len(processed_paths),
                "total": len(image_paths) + len(processed_paths),
                "result": None,
                "error": None,
                "message": "⚡ Hydrating and preparing photos..."
            }

        def background_scan(jid, target_path, active_paths, pre_processed):
            run_context = {
                "run_id": f"QC-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}",
                "job_id": jid
            }
            
            total_photos = len(active_paths) + len(pre_processed)
            # Route culling run mode: Mode A/B/C routing
            cull_run_mode = "complete"
            if mode == "fast_review":
                cull_run_mode = "fast_review"
            elif mode == "complete_analysis":
                cull_run_mode = "complete"
            else:
                # Auto Adaptive Policy
                if total_photos >= 100:
                    cull_run_mode = "fast_review"
                else:
                    cull_run_mode = "complete"
            
            def save_chk(proc_paths, rem_paths):
                full_processed = list(pre_processed) + list(proc_paths)
                recovery_manager.save_checkpoint(jid, full_processed, rem_paths, threshold, top_percent or 0, target_path)

            try:
                # Discover files for report
                _, scan_diag = scan_directory_for_images(target_path)
                if total_photos == 0:
                    recovery_manager.clear_checkpoint()
                    write_diagnostics_report(target_path, scan_diag, [], [])
                    
                    err_msg = "No supported photos found in the directory. Please check the path and try again."
                    if scan_diag.get("unsupported_files"):
                        unsupported_sample = ", ".join(scan_diag["unsupported_files"][:5])
                        err_msg += f"\n\n🚫 Found unsupported files (e.g. {unsupported_sample}). Supported formats: " + ", ".join(ALLOWED_EXTENSIONS)
                    
                    with self._jobs_lock:
                        self._jobs[jid] = {
                            "status": "failed",
                            "progress": 0,
                            "total": 0,
                            "result": None,
                            "error": err_msg
                        }
                    return
                
                # Update total
                with self._jobs_lock:
                    self._jobs[jid]["total"] = total_photos
                    self._jobs[jid]["message"] = "⚡ Running computer vision models..."

                grouped_paths = None
                for processed, total, groups in process_and_group_generator(
                    active_paths, 
                    threshold=threshold, 
                    token=token, 
                    save_checkpoint_fn=save_chk,
                    logger=telemetry_logger,
                    run_context=run_context,
                    processed_paths=pre_processed,
                    mode=cull_run_mode
                ):
                    with self._jobs_lock:
                        if jid in self._cancelled_jobs or token.is_cancelled():
                            break
                        if jid in self._jobs:
                            self._jobs[jid]["progress"] = processed
                            self._jobs[jid]["total"] = total
                            if processed > 0:
                                self._jobs[jid]["message"] = f"Analyzing {processed} of {total} photos..."
                    if groups is not None:
                        grouped_paths = groups
                
                # Handle cancellation
                if token.is_cancelled() or jid in self._cancelled_jobs:
                    recovery_manager.clear_checkpoint()
                    def url_fn(img_path, filename):
                        return f"/image?path={urllib.parse.quote(img_path)}"
                    
                    groups_result = []
                    elapsed = 0.0
                    coverage_summary = {}
                    completeness_score = 0.0
                    warnings = []
                    if grouped_paths:
                        groups_result, elapsed, coverage_summary, completeness_score, warnings = _build_groups_response(grouped_paths, url_fn, top_percent, mode)
                        
                    result = {
                        "success": True,
                        "groups": groups_result,
                        "scanned_dir": target_path,
                        "processing_time": elapsed,
                        "coverage_report": coverage_summary,
                        "event_completeness_score": completeness_score,
                        "warnings": warnings,
                        "cancelled": True
                    }
                    with self._jobs_lock:
                        self._jobs[jid] = {
                            "status": "failed",
                            "progress": processed,
                            "total": total_photos,
                            "result": result,
                            "error": "Cancelled by user"
                        }
                    return

                if active_paths and not grouped_paths:
                    recovery_manager.clear_checkpoint()
                    
                    report_summary = write_diagnostics_report(target_path, scan_diag, [], active_paths)
                    onedrive_placeholder_count = report_summary["onedrive_placeholder_count"]
                    inaccessible_count = report_summary["inaccessible_count"]
                    unsupported_format_count = report_summary["unsupported_format_count"]
                    corrupted_count = report_summary["corrupted_count"]

                    err_msg = "Failed to analyze any images in the directory.\n\n"
                    if onedrive_placeholder_count > 0:
                        err_msg += f"⚠️ Detected {onedrive_placeholder_count} un-hydrated OneDrive placeholders.\n"
                        err_msg += "Windows cannot open these files because OneDrive is not running or logged in.\n"
                        err_msg += "-> Solution: Start OneDrive and right-click the folder, choosing 'Always keep on this device'.\n\n"
                    if scan_diag.get("subdirectories_with_images"):
                        sub_list = ", ".join(scan_diag["subdirectories_with_images"][:3])
                        err_msg += f"📂 Found images inside subfolders: {sub_list}\n"
                        err_msg += "QuantileCull does not scan subfolders automatically in this view.\n"
                        err_msg += "-> Solution: Please select the specific subfolder directly.\n\n"
                    if inaccessible_count > 0:
                        err_msg += f"🔒 Detected {inaccessible_count} inaccessible files due to permission limits.\n\n"
                    if (unsupported_format_count + corrupted_count) > 0:
                        err_msg += f"🚫 Detected {unsupported_format_count + corrupted_count} unsupported or corrupted image files.\n\n"
                    
                    err_msg += "Detailed diagnostic logs have been saved to: 'quantilecull_scan_report.txt' in the selected directory."
                    
                    with self._jobs_lock:
                        self._jobs[jid] = {
                            "status": "failed",
                            "progress": 0,
                            "total": total_photos,
                            "result": None,
                            "error": err_msg
                        }
                    return
                    
                recovery_manager.clear_checkpoint()
                
                def url_fn(img_path, filename):
                    return f"/image?path={urllib.parse.quote(img_path)}"
                
                groups_result, elapsed, coverage_summary, completeness_score, warnings = _build_groups_response(grouped_paths, url_fn, top_percent, mode)
                
                # Report any partial diagnostic failures on successful run
                successful_paths = {p["path"] for g in groups_result for p in g["photos"]}
                all_image_paths = list(active_paths) + list(pre_processed)
                failed_paths = [p for p in all_image_paths if p not in successful_paths]
                
                if failed_paths:
                    write_diagnostics_report(target_path, scan_diag, successful_paths, failed_paths)
                        
                result = {
                    "success": True,
                    "groups": groups_result,
                    "scanned_dir": target_path,
                    "processing_time": elapsed,
                    "coverage_report": coverage_summary,
                    "event_completeness_score": completeness_score,
                    "warnings": warnings,
                    "cull_mode": mode
                }
                
                # Update local metrics
                try:
                    license_manager.increment_metric("images_processed", total_photos)
                    license_manager.increment_metric("processing_time", elapsed)
                    _trigger_metrics_upload()
                except Exception as ex_m:
                    print(f"Error updating culling metrics: {ex_m}")
                    
                with self._jobs_lock:
                    self._jobs[jid] = {
                        "status": "completed",
                        "progress": total_photos,
                        "total": total_photos,
                        "result": result,
                        "error": None
                    }

                # Trigger Asynchronous Background AI Face Indexing if in fast_review mode
                if cull_run_mode == "fast_review":
                    with self._jobs_lock:
                        self._jobs[jid]["background_ai"] = {
                            "status": "running",
                            "progress": 0,
                            "total": len(active_paths),
                            "message": "⚡ Preparing background face indexing..."
                        }
                    
                    def bg_ai_task():
                        self.run_background_ai(active_paths, token, jid)
                        
                    bg_thread = threading.Thread(target=bg_ai_task, name=f"bg-ai-{jid}", daemon=True)
                    bg_thread.start()

            except Exception as e:
                traceback.print_exc()
                recovery_manager.clear_checkpoint()
                with self._jobs_lock:
                    self._jobs[jid] = {
                        "status": "failed",
                        "progress": 0,
                        "total": 0,
                        "result": None,
                        "error": str(e)
                    }

        self._executor.submit(background_scan, job_id, verified_path, image_paths, processed_paths)
        return job_id

    def run_background_ai(self, active_paths, token, jid):
        import time
        from image_analyzer import _process_single_image_cached
        
        total = len(active_paths)
        processed_set = set()
        
        while len(processed_set) < len(active_paths):
            if token.is_cancelled():
                break
                
            # Yield CPU slice to ensure UI remains highly responsive
            time.sleep(0.05)
            
            # Dynamically determine the next path to process based on viewport priority
            next_path = None
            
            with self._jobs_lock:
                priority = self._jobs.get(jid, {}).get("viewport_priority", {})
                visible_list = priority.get("visible", [])
                nearby_list = priority.get("nearby", [])
                
            # 1. First priority: Visible paths not yet processed
            for p in visible_list:
                if p not in processed_set and p in active_paths:
                    next_path = p
                    break
                    
            # 2. Second priority: Nearby paths not yet processed
            if not next_path:
                for p in nearby_list:
                    if p not in processed_set and p in active_paths:
                        next_path = p
                        break
                        
            # 3. Third priority: Any remaining path
            if not next_path:
                for p in active_paths:
                    if p not in processed_set:
                        next_path = p
                        break
                        
            if not next_path:
                break
                
            processed_set.add(next_path)
            
            try:
                _process_single_image_cached(next_path, token, mode="background_ai")
                
                with self._jobs_lock:
                    if jid in self._jobs:
                        self._jobs[jid]["background_ai"]["progress"] = len(processed_set)
                        self._jobs[jid]["background_ai"]["message"] = f"⚡ Background Face Indexing {len(processed_set)} of {total} photos..."
            except Exception as e:
                print(f"[Background AI] Error processing {os.path.basename(next_path)}: {e}")
                
        with self._jobs_lock:
            if jid in self._jobs:
                self._jobs[jid]["background_ai"]["status"] = "completed"
                self._jobs[jid]["background_ai"]["message"] = "⚡ Background Face Indexing completed."

    def update_viewport_priority(self, job_id, visible_paths, nearby_paths):
        with self._jobs_lock:
            if job_id in self._jobs:
                self._jobs[job_id]["viewport_priority"] = {
                    "visible": list(visible_paths),
                    "nearby": list(nearby_paths)
                }
        return True

    def _precache_single_image(self, path):
        try:
            mtime = os.path.getmtime(path)
            from image_analyzer import _process_single_image_cached
            _process_single_image_cached(path)
        except Exception as e:
            print(f"[precache] Failed to cache image {os.path.basename(path)}: {e}")

    def write_xmp_metadata(self, image_path, rating, label, rejected):
        """Exposes XMP sidecar writing functionality to the Javascript frontend."""
        from xmp_engine import write_xmp_metadata, get_xmp_path
        success = write_xmp_metadata(image_path, rating, label, rejected)
        if not success:
            return False
            
        # Update SQLite cache database immediately to remain fully in sync
        try:
            mtime = os.path.getmtime(image_path)
            xmp_path = get_xmp_path(image_path)
            xmp_mtime = os.path.getmtime(xmp_path) if os.path.exists(xmp_path) else 0.0
            
            cached = cache_engine.get_cached_item(image_path, mtime, xmp_mtime)
            
            if cached and cached.get('metrics'):
                metrics = cached['metrics']
            else:
                metrics = {
                    "scoring_version": 4,
                    "overall_score": 50.0,
                    "faces": [],
                    "blur": 0.0,
                    "brightness": 50.0,
                    "contrast": 50.0,
                    "stage_presence": 0.0,
                    "audience_presence": 0.0,
                    "branding_presence": 0.0,
                    "hero_candidate": False,
                    "editorial_decision": "KEEP"
                }
                cached = {
                    "sha256": "",
                    "phash": None,
                    "ratio": 1.0,
                    "time": datetime.datetime.min
                }
                
            metrics["xmp_rating"] = rating
            metrics["xmp_label"] = label
            metrics["xmp_rejected"] = rejected
            
            cache_engine.set_cached_item(
                image_path,
                mtime,
                xmp_mtime,
                cached["sha256"],
                cached["phash"],
                cached["ratio"],
                cached["time"],
                metrics
            )
            return True
        except Exception as e:
            print(f"[app_api] Error sync-writing cache in write_xmp_metadata: {e}")
            return False

    def preload_images(self, current_path, all_paths):
        """Asynchronously preloads neighboring images in the background."""
        background_tasks.background_manager.submit_task(
            "preload_adjacent",
            background_tasks.background_preload_images,
            current_path,
            all_paths,
            self._precache_single_image
        )
        return True

    def precache_folder(self, folder_path):
        """Asynchronously pre-caches all thumbnails/metrics in the background."""
        from image_analyzer import scan_directory_for_images
        safe, verified_path = is_safe_path(folder_path)
        if not safe:
            return False
            
        image_paths, _ = scan_directory_for_images(verified_path)
        if image_paths:
            background_tasks.background_manager.submit_task(
                "precache_folder",
                background_tasks.background_precache_thumbnails,
                image_paths,
                self._precache_single_image
            )
            return True
        return False

LOCK_FILE = os.path.join(tempfile.gettempdir(), 'quantilecull.lock')

def check_and_create_lock():
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, 'r') as f:
                pid = int(f.read().strip())
            
            if psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                if "python" in proc.name().lower() or "quantilecull" in proc.name().lower():
                    # Focus existing window
                    if sys.platform == 'win32':
                        import ctypes
                        hwnd = ctypes.windll.user32.FindWindowW(None, "QuantileCull — AI Quantile Culler")
                        if hwnd:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)
                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                    sys.exit(0)
        except Exception:
            pass
        # Stale lock
        try:
            os.remove(LOCK_FILE)
        except OSError:
            pass

    # Create new lock
    with open(LOCK_FILE, 'w') as f:
        f.write(str(os.getpid()))
        
    import atexit
    def cleanup():
        try:
            if os.path.exists(LOCK_FILE):
                os.remove(LOCK_FILE)
        except OSError:
            pass
    atexit.register(cleanup)

import bottle

bottle_app = bottle.Bottle()

@bottle_app.route('/')
def serve_index():
    if getattr(sys, 'frozen', False):
        root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    else:
        root_dir = os.path.dirname(os.path.abspath(__file__))
    return bottle.static_file('index.html', root=root_dir)

@bottle_app.route('/static/<filepath:path>')
def serve_static(filepath):
    if getattr(sys, 'frozen', False):
        root_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(sys.executable)))
    else:
        root_dir = os.path.dirname(os.path.abspath(__file__))
    return bottle.static_file(filepath, root=os.path.join(root_dir, 'static'))

@bottle_app.route('/image')
def serve_image():
    img_path = bottle.request.query.get('path')
    if not img_path:
        return bottle.HTTPError(400, "Missing path parameter")
        
    safe, verified_path = is_safe_path(img_path)
    if not safe:
        return bottle.HTTPError(403, f"Access denied: {verified_path}")
        
    # Check if RAW file and extract preview
    from raw_engine import is_raw_file
    if is_raw_file(verified_path):
        from preview_engine import extract_raw_preview, generate_raw_thumbnail
        
        max_width_str = bottle.request.query.get('maxWidth')
        try:
            if max_width_str:
                max_width = int(max_width_str)
                raw_bytes = generate_raw_thumbnail(verified_path, max_dim=max_width)
            else:
                raw_bytes = extract_raw_preview(verified_path)
                
            if raw_bytes:
                bottle.response.content_type = 'image/jpeg'
                return raw_bytes
        except Exception as e:
            print(f"[serve_image] Failed to serve RAW preview for {verified_path}: {e}")
            
    # Check for maxWidth query parameter for standard images
    max_width_str = bottle.request.query.get('maxWidth')
    if max_width_str:
        try:
            max_width = int(max_width_str)
            thumb_path = get_cached_thumbnail(verified_path, max_width)
            if thumb_path and os.path.exists(thumb_path):
                return bottle.static_file(os.path.basename(thumb_path), root=os.path.dirname(thumb_path))
        except Exception as e:
            print(f"Error serving thumbnail for {verified_path}: {e}")
            # Fall back to original file if thumbnailing fails
            pass
            
    dir_name = os.path.dirname(verified_path)
    file_name = os.path.basename(verified_path)
    return bottle.static_file(file_name, root=dir_name)

if __name__ == '__main__':
    # Initialize singleton lock
    check_and_create_lock()

    # Load settings and initialize Sentry if enabled
    settings = load_settings()
    s_opt = settings.get("sentry_opt_in", False)
    s_dsn = settings.get("sentry_dsn", "")
    init_sentry(s_dsn, "1.0.0", s_opt)

    # Initialize logging for the GUI process
    setup_logging()
    
    # Increment sessions count and sync metrics
    try:
        license_manager.increment_metric("sessions", 1)
        _trigger_metrics_upload()
    except Exception:
        pass
        
    api = WebviewApi()
    window = webview.create_window(
        "QuantileCull — AI Quantile Culler",
        bottle_app,
        width=1280,
        height=800,
        min_size=(900, 600),
        js_api=api
    )
    api._window = window
    
    try:
        # Start PyWebview with the custom WSGI server
        debug_mode = os.environ.get("QUANTILECULL_DEVTOOLS") == "1"
        webview.start(debug=debug_mode)
    except Exception as e:
        print("Exception in webview.start:")
        traceback.print_exc()
