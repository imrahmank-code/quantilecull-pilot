import os
import sqlite3
import json
import threading
import imagehash
import datetime
from pathlib import Path

# Thread safety lock
_db_lock = threading.Lock()
DB_FILE = ".quantilecull_cache.db"

def _get_db_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def _init_cache():
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                # 1. Create tables if missing
                conn.execute('''CREATE TABLE IF NOT EXISTS image_cache (
                                file_path TEXT PRIMARY KEY,
                                mtime REAL,
                                sha256 TEXT,
                                phash TEXT,
                                ratio REAL,
                                timestamp REAL,
                                metrics JSON)''')
                                
                conn.execute('''CREATE TABLE IF NOT EXISTS face_embeddings (
                                face_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                file_path TEXT,
                                bbox_x INTEGER,
                                bbox_y INTEGER,
                                bbox_w INTEGER,
                                bbox_h INTEGER,
                                confidence REAL,
                                sharpness REAL,
                                exposure REAL,
                                landmarks JSON,
                                orientation JSON,
                                embedding BLOB,
                                FOREIGN KEY(file_path) REFERENCES image_cache(file_path) ON DELETE CASCADE)''')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_face_embeddings_filepath ON face_embeddings(file_path)')
                                
                # 2. Schema migration: Add xmp_mtime if not exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(image_cache)")
                columns = [row[1] for row in cursor.fetchall()]
                if "xmp_mtime" not in columns:
                    conn.execute("ALTER TABLE image_cache ADD COLUMN xmp_mtime REAL DEFAULT NULL")
                    conn.commit()
                    print("[cache_engine] Successfully migrated cache schema: added xmp_mtime")
    except Exception as e:
        print(f"[cache_engine] Failed to initialize SQLite cache database: {e}")

# Automatically initialize at module load
_init_cache()

def get_cached_item(path: str, current_mtime: float, current_xmp_mtime: float) -> dict:
    """
    Checks the cache for a fresh image analysis record.
    Invalidates (returns None) if either file mtime or XMP sidecar mtime has changed.
    """
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT mtime, xmp_mtime, sha256, phash, ratio, timestamp, metrics 
                                  FROM image_cache WHERE file_path=?""", (path,))
                row = cursor.fetchone()
                if row:
                    cached_mtime, cached_xmp_mtime, sha256, phash_str, ratio, ts, metrics_json = row
                    
                    # Double mtime validation (Freshness check)
                    mtime_match = (cached_mtime == current_mtime)
                    xmp_match = (cached_xmp_mtime == current_xmp_mtime)
                    
                    if mtime_match and xmp_match:
                        metrics_data = json.loads(metrics_json) if metrics_json else None
                        if metrics_data:
                            metrics_data['filename'] = os.path.basename(path)
                        return {
                            'sha256': sha256,
                            'phash': imagehash.hex_to_hash(phash_str) if phash_str else None,
                            'ratio': ratio,
                            'time': datetime.datetime.fromtimestamp(ts) if ts > 0 else datetime.datetime.min,
                            'metrics': metrics_data
                        }
    except Exception as e:
        print(f"[cache_engine] Cache read error for {path}: {e}")
    return None

def set_cached_item(path: str, mtime: float, xmp_mtime: float, sha256: str, phash: str, ratio: float, timestamp: float, metrics: dict):
    """Inserts or replaces an image analysis cache entry."""
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                phash_str = str(phash) if phash is not None else None
                ts = timestamp.timestamp() if timestamp != datetime.datetime.min else 0.0
                metrics_json = json.dumps(metrics) if metrics else None
                conn.execute('''INSERT OR REPLACE INTO image_cache 
                                (file_path, mtime, xmp_mtime, sha256, phash, ratio, timestamp, metrics) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                             (path, mtime, xmp_mtime, sha256, phash_str, ratio, ts, metrics_json))
    except Exception as e:
        print(f"[cache_engine] Cache write error for {path}: {e}")

def clear_cache() -> bool:
    """Wipes the entire persistent cache database."""
    try:
        with _db_lock:
            conn = _get_db_connection()
            try:
                conn.execute("DELETE FROM face_embeddings")
                conn.execute("DELETE FROM image_cache")
                conn.commit()
                conn.isolation_level = None
                conn.execute("VACUUM")
            finally:
                conn.close()
        return True
    except Exception as e:
        print(f"[cache_engine] Error clearing database cache: {e}")
        return False


def get_face_embeddings(path: str) -> list:
    """Queries face metadata and deserializes binary BLOB face embeddings from SQLite."""
    import numpy as np
    faces = []
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""SELECT bbox_x, bbox_y, bbox_w, bbox_h, confidence, 
                                         sharpness, exposure, landmarks, orientation, embedding 
                                  FROM face_embeddings WHERE file_path=?""", (path,))
                rows = cursor.fetchall()
                for row in rows:
                    bx, by, bw, bh, conf, sharp, exp, lm_json, orient_json, emb_blob = row
                    embedding = None
                    if emb_blob:
                        embedding = np.frombuffer(emb_blob, dtype=np.float32).tolist()
                    faces.append({
                        "bbox": [bx, by, bw, bh],
                        "confidence": conf,
                        "quality": {"sharpness": sharp, "exposure": exp},
                        "landmarks": json.loads(lm_json) if lm_json else {},
                        "orientation": json.loads(orient_json) if orient_json else {},
                        "embedding": embedding
                    })
    except Exception as e:
        print(f"[cache_engine] Error reading face embeddings for {path}: {e}")
    return faces


def set_face_embeddings(path: str, faces: list):
    """Saves face embeddings and metadata to SQLite, serializing embedding arrays as binary BLOBs."""
    import numpy as np
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                conn.execute("DELETE FROM face_embeddings WHERE file_path=?", (path,))
                for face in faces:
                    bbox = face.get("bbox", [0, 0, 0, 0])
                    conf = face.get("confidence", 1.0)
                    q = face.get("quality", {})
                    sharp = q.get("sharpness", 0.0)
                    exp = q.get("exposure", 0.0)
                    lm = face.get("landmarks", {})
                    orient = face.get("orientation", {})
                    emb = face.get("embedding", None)
                    
                    emb_blob = None
                    if emb:
                        emb_blob = np.array(emb, dtype=np.float32).tobytes()
                        
                    conn.execute('''INSERT INTO face_embeddings 
                                    (file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence, 
                                     sharpness, exposure, landmarks, orientation, embedding) 
                                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                 (path, bbox[0], bbox[1], bbox[2], bbox[3], conf, 
                                  sharp, exp, json.dumps(lm), json.dumps(orient), emb_blob))
                conn.commit()
    except Exception as e:
        print(f"[cache_engine] Error writing face embeddings for {path}: {e}")
