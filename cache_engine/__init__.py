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
_thread_local = threading.local()

def _get_db_connection():
    if not hasattr(_thread_local, "conn"):
        conn = sqlite3.connect(DB_FILE, timeout=15.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA cache_size=-4000;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        _thread_local.conn = conn
    return _thread_local.conn

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
                
                conn.execute('''CREATE TABLE IF NOT EXISTS persons (
                                person_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                name TEXT UNIQUE,
                                notes TEXT,
                                creation_timestamp REAL,
                                face_count INTEGER DEFAULT 0,
                                key_face_path TEXT,
                                key_face_bbox TEXT)''')

                conn.execute('''CREATE TABLE IF NOT EXISTS identity_clusters (
                                cluster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                average_embedding BLOB,
                                confidence REAL,
                                creation_timestamp REAL,
                                last_updated REAL,
                                status TEXT DEFAULT 'active')''')
                                
                conn.execute('''CREATE TABLE IF NOT EXISTS identity_faces (
                                face_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                cluster_id INTEGER,
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
                                FOREIGN KEY(cluster_id) REFERENCES identity_clusters(cluster_id) ON DELETE SET NULL,
                                FOREIGN KEY(file_path) REFERENCES image_cache(file_path) ON DELETE CASCADE)''')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_identity_faces_cluster ON identity_faces(cluster_id)')
                conn.execute('CREATE INDEX IF NOT EXISTS idx_identity_faces_filepath ON identity_faces(file_path)')
                
                conn.execute('''CREATE TABLE IF NOT EXISTS cluster_history (
                                history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                                action_type TEXT,
                                cluster_id_1 INTEGER,
                                cluster_id_2 INTEGER,
                                timestamp REAL,
                                details TEXT)''')
                                
                conn.execute('''CREATE TABLE IF NOT EXISTS cluster_statistics (
                                cluster_id INTEGER PRIMARY KEY,
                                face_count INTEGER,
                                average_confidence REAL,
                                max_similarity REAL,
                                min_similarity REAL,
                                FOREIGN KEY(cluster_id) REFERENCES identity_clusters(cluster_id) ON DELETE CASCADE)''')
                                
                # 2. Schema migration: Add xmp_mtime if not exists
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(image_cache)")
                columns = [row[1] for row in cursor.fetchall()]
                if "xmp_mtime" not in columns:
                    conn.execute("ALTER TABLE image_cache ADD COLUMN xmp_mtime REAL DEFAULT NULL")
                    conn.commit()
                    print("[cache_engine] Successfully migrated cache schema: added xmp_mtime")

                # 3. Schema migration: Add person_id to identity_clusters if not exists
                cursor.execute("PRAGMA table_info(identity_clusters)")
                c_columns = [row[1] for row in cursor.fetchall()]
                if "person_id" not in c_columns:
                    conn.execute("ALTER TABLE identity_clusters ADD COLUMN person_id INTEGER REFERENCES persons(person_id) ON DELETE SET NULL")
                    conn.commit()
                    print("[cache_engine] Successfully migrated cache schema: added person_id to identity_clusters")
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
                conn.execute("DELETE FROM persons")
                conn.execute("DELETE FROM cluster_statistics")
                conn.execute("DELETE FROM cluster_history")
                conn.execute("DELETE FROM identity_faces")
                conn.execute("DELETE FROM identity_clusters")
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


def get_clusters() -> list:
    """Retrieves all clusters, their centroids, statistics, and face associations."""
    import numpy as np
    clusters = []
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT c.cluster_id, c.average_embedding, c.confidence, 
                           c.creation_timestamp, c.last_updated, c.status,
                           s.face_count, s.average_confidence, s.max_similarity, s.min_similarity
                    FROM identity_clusters c
                    LEFT JOIN cluster_statistics s ON c.cluster_id = s.cluster_id
                """)
                cluster_rows = cursor.fetchall()
                
                for crow in cluster_rows:
                    cid, emb_blob, conf, created, updated, status, f_count, avg_conf, max_sim, min_sim = crow
                    avg_embedding = None
                    if emb_blob:
                        avg_embedding = np.frombuffer(emb_blob, dtype=np.float32).tolist()
                        
                    cursor.execute("""
                        SELECT face_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence,
                               sharpness, exposure, landmarks, orientation, embedding
                        FROM identity_faces WHERE cluster_id = ?
                    """, (cid,))
                    face_rows = cursor.fetchall()
                    faces = []
                    for frow in face_rows:
                        fid, path, bx, by, bw, bh, fconf, sharp, exp, lm_json, orient_json, femb_blob = frow
                        femb = None
                        if femb_blob:
                            femb = np.frombuffer(femb_blob, dtype=np.float32).tolist()
                        faces.append({
                            "face_id": fid,
                            "file_path": path,
                            "bbox": [bx, by, bw, bh],
                            "confidence": fconf,
                            "quality": {"sharpness": sharp, "exposure": exp},
                            "landmarks": json.loads(lm_json) if lm_json else {},
                            "orientation": json.loads(orient_json) if orient_json else {},
                            "embedding": femb
                        })
                        
                    clusters.append({
                        "cluster_id": cid,
                        "average_embedding": avg_embedding,
                        "confidence": conf,
                        "creation_timestamp": created,
                        "last_updated": updated,
                        "status": status,
                        "statistics": {
                            "face_count": f_count or 0,
                            "average_confidence": avg_conf or 0.0,
                            "max_similarity": max_sim or 0.0,
                            "min_similarity": min_sim or 0.0
                        },
                        "faces": faces
                    })
    except Exception as e:
        print(f"[cache_engine] Error reading clusters: {e}")
    return clusters


def save_clusters(clusters: list):
    """Saves all clusters and face assignments, updating average embeddings and stats."""
    import numpy as np
    import time
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                conn.execute("DELETE FROM cluster_statistics")
                conn.execute("DELETE FROM identity_faces")
                conn.execute("DELETE FROM identity_clusters")
                
                for c in clusters:
                    cid = c.get("cluster_id")
                    avg_emb = c.get("average_embedding")
                    conf = c.get("confidence", 1.0)
                    created = c.get("creation_timestamp", time.time())
                    updated = c.get("last_updated", time.time())
                    status = c.get("status", "active")
                    
                    emb_blob = None
                    if avg_emb:
                        emb_blob = np.array(avg_emb, dtype=np.float32).tobytes()
                        
                    cursor = conn.cursor()
                    if cid is not None:
                        cursor.execute("""
                            INSERT INTO identity_clusters 
                            (cluster_id, average_embedding, confidence, creation_timestamp, last_updated, status)
                            VALUES (?, ?, ?, ?, ?, ?)
                        """, (cid, emb_blob, conf, created, updated, status))
                        actual_cid = cid
                    else:
                        cursor.execute("""
                            INSERT INTO identity_clusters 
                            (average_embedding, confidence, creation_timestamp, last_updated, status)
                            VALUES (?, ?, ?, ?, ?)
                        """, (emb_blob, conf, created, updated, status))
                        actual_cid = cursor.lastrowid
                        
                    faces = c.get("faces", [])
                    for face in faces:
                        path = face.get("file_path")
                        bbox = face.get("bbox", [0, 0, 0, 0])
                        fconf = face.get("confidence", 1.0)
                        q = face.get("quality", {})
                        sharp = q.get("sharpness", 0.0)
                        exp = q.get("exposure", 0.0)
                        lm = face.get("landmarks", {})
                        orient = face.get("orientation", {})
                        femb = face.get("embedding")
                        
                        femb_blob = None
                        if femb:
                            femb_blob = np.array(femb, dtype=np.float32).tobytes()
                            
                        conn.execute("""
                            INSERT INTO identity_faces
                            (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence,
                             sharpness, exposure, landmarks, orientation, embedding)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (actual_cid, path, bbox[0], bbox[1], bbox[2], bbox[3], fconf,
                              sharp, exp, json.dumps(lm), json.dumps(orient), femb_blob))
                              
                    stats = c.get("statistics", {})
                    conn.execute("""
                        INSERT INTO cluster_statistics
                        (cluster_id, face_count, average_confidence, max_similarity, min_similarity)
                        VALUES (?, ?, ?, ?, ?)
                    """, (actual_cid, stats.get("face_count", len(faces)), stats.get("average_confidence", 0.0),
                          stats.get("max_similarity", 0.0), stats.get("min_similarity", 0.0)))
                conn.commit()
    except Exception as e:
        print(f"[cache_engine] Error saving clusters: {e}")


def invalidate_clusters():
    """Clears all clustering tables."""
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                conn.execute("DELETE FROM cluster_statistics")
                conn.execute("DELETE FROM cluster_history")
                conn.execute("DELETE FROM identity_faces")
                conn.execute("DELETE FROM identity_clusters")
                conn.commit()
    except Exception as e:
        print(f"[cache_engine] Error invalidating clusters: {e}")


def incremental_cluster_update(file_path: str, faces: list):
    """
    Saves face details for a single photo and maps each face to existing or new identity clusters.
    If the face embedding matches an existing cluster above similarity threshold, it joins that cluster.
    """
    import numpy as np
    import time
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                conn.execute("DELETE FROM identity_faces WHERE file_path=?", (file_path,))
                
                cursor = conn.cursor()
                cursor.execute("SELECT cluster_id, average_embedding FROM identity_clusters WHERE status='active'")
                cluster_rows = cursor.fetchall()
                
                centroids = {}
                for cid, emb_blob in cluster_rows:
                    if emb_blob:
                        centroids[cid] = np.frombuffer(emb_blob, dtype=np.float32)
                        
                for face in faces:
                    femb = face.get("embedding")
                    if not femb:
                        continue
                    femb_arr = np.array(femb, dtype=np.float32)
                    
                    best_cid = None
                    best_sim = -1.0
                    norm1 = np.linalg.norm(femb_arr)
                    if norm1 > 0:
                        for cid, cent in centroids.items():
                            sim = float(np.dot(femb_arr, cent) / norm1)
                            if sim > best_sim:
                                best_sim = sim
                                best_cid = cid
                            
                    if best_cid is not None and best_sim >= 0.75:
                        assigned_cid = best_cid
                        face["cluster_id"] = assigned_cid
                        face["matching_score"] = best_sim
                        face["identity_state"] = "stable"
                        
                        old_cent = centroids[assigned_cid]
                        cursor.execute("SELECT face_count FROM cluster_statistics WHERE cluster_id=?", (assigned_cid,))
                        row = cursor.fetchone()
                        count = row[0] if row else 1
                        
                        new_cent = (old_cent * count + femb_arr) / (count + 1)
                        norm = np.linalg.norm(new_cent)
                        if norm > 0:
                            new_cent /= norm
                        centroids[assigned_cid] = new_cent
                        
                        new_emb_blob = new_cent.tobytes()
                        conn.execute("""
                            UPDATE identity_clusters 
                            SET average_embedding=?, last_updated=? 
                            WHERE cluster_id=?
                        """, (new_emb_blob, time.time(), assigned_cid))
                        
                        conn.execute("""
                            UPDATE cluster_statistics 
                            SET face_count=face_count+1 
                            WHERE cluster_id=?
                        """, (assigned_cid,))
                    else:
                        cursor.execute("""
                            INSERT INTO identity_clusters 
                            (average_embedding, confidence, creation_timestamp, last_updated)
                            VALUES (?, ?, ?, ?)
                        """, (femb_arr.tobytes(), face.get("confidence", 1.0), time.time(), time.time()))
                        assigned_cid = cursor.lastrowid
                        face["cluster_id"] = assigned_cid
                        face["matching_score"] = 1.0
                        face["identity_state"] = "unclustered"
                        centroids[assigned_cid] = femb_arr
                        
                        conn.execute("""
                            INSERT INTO cluster_statistics 
                            (cluster_id, face_count, average_confidence, max_similarity, min_similarity)
                            VALUES (?, 1, ?, 1.0, 1.0)
                        """, (assigned_cid, face.get("confidence", 1.0)))
                        
                    bbox = face.get("bbox", [0, 0, 0, 0])
                    fconf = face.get("confidence", 1.0)
                    q = face.get("quality", {})
                    sharp = q.get("sharpness", 0.0)
                    exp = q.get("exposure", 0.0)
                    lm = face.get("landmarks", {})
                    orient = face.get("orientation", {})
                    femb_blob = femb_arr.tobytes()
                    
                    conn.execute("""
                        INSERT INTO identity_faces
                        (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence,
                         sharpness, exposure, landmarks, orientation, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (assigned_cid, file_path, bbox[0], bbox[1], bbox[2], bbox[3], fconf,
                          sharp, exp, json.dumps(lm), json.dumps(orient), femb_blob))
                conn.commit()
    except Exception as e:
        print(f"[cache_engine] Error doing incremental cluster update: {e}")


def get_face_embeddings(path: str) -> list:
    """Queries face metadata and deserializes binary BLOB face embeddings from SQLite, resolving cluster and person info."""
    import numpy as np
    faces = []
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, f.confidence, 
                           f.sharpness, f.exposure, f.landmarks, f.orientation, f.embedding,
                           f.cluster_id, s.face_count, c.person_id, p.name
                    FROM identity_faces f
                    LEFT JOIN cluster_statistics s ON f.cluster_id = s.cluster_id
                    LEFT JOIN identity_clusters c ON f.cluster_id = c.cluster_id
                    LEFT JOIN persons p ON c.person_id = p.person_id
                    WHERE f.file_path=?
                """, (path,))
                rows = cursor.fetchall()
                
                if not rows:
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
                            "embedding": embedding,
                            "cluster_id": None,
                            "cluster_confidence": 0.0,
                            "identity_state": "unclustered",
                            "cluster_size": 0,
                            "matching_score": 0.0,
                            "person_id": None,
                            "person_name": None
                        })
                    return faces
                    
                for row in rows:
                    bx, by, bw, bh, conf, sharp, exp, lm_json, orient_json, emb_blob, cid, csize, pid, pname = row
                    embedding = None
                    if emb_blob:
                        embedding = np.frombuffer(emb_blob, dtype=np.float32).tolist()
                    
                    matching_score = 1.0
                    if cid is not None:
                        cursor.execute("SELECT average_embedding FROM identity_clusters WHERE cluster_id=?", (cid,))
                        crow = cursor.fetchone()
                        if crow and crow[0] and emb_blob:
                            cent = np.frombuffer(crow[0], dtype=np.float32)
                            femb = np.frombuffer(emb_blob, dtype=np.float32)
                            dot = np.dot(femb, cent)
                            norm1 = np.linalg.norm(femb)
                            norm2 = np.linalg.norm(cent)
                            matching_score = float(dot / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0
                            
                    faces.append({
                        "bbox": [bx, by, bw, bh],
                        "confidence": conf,
                        "quality": {"sharpness": sharp, "exposure": exp},
                        "landmarks": json.loads(lm_json) if lm_json else {},
                        "orientation": json.loads(orient_json) if orient_json else {},
                        "embedding": embedding,
                        "cluster_id": cid,
                        "cluster_confidence": conf,
                        "identity_state": "stable" if cid is not None else "unclustered",
                        "cluster_size": csize or 0,
                        "matching_score": matching_score,
                        "person_id": pid,
                        "person_name": pname
                    })
            with _get_db_connection() as conn:
                conn.execute("DELETE FROM cluster_statistics")
                conn.execute("DELETE FROM cluster_history")
                conn.execute("DELETE FROM identity_faces")
                conn.execute("DELETE FROM identity_clusters")
                conn.commit()
    except Exception as e:
        print(f"[cache_engine] Error invalidating clusters: {e}")


def incremental_cluster_update(file_path: str, faces: list):
    """
    Saves face details for a single photo and maps each face to existing or new identity clusters.
    If the face embedding matches an existing cluster above similarity threshold, it joins that cluster.
    """
    import numpy as np
    import time
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                conn.execute("DELETE FROM identity_faces WHERE file_path=?", (file_path,))
                
                cursor = conn.cursor()
                cursor.execute("SELECT cluster_id, average_embedding FROM identity_clusters WHERE status='active'")
                cluster_rows = cursor.fetchall()
                
                centroids = {}
                for cid, emb_blob in cluster_rows:
                    if emb_blob:
                        centroids[cid] = np.frombuffer(emb_blob, dtype=np.float32)
                        
                for face in faces:
                    femb = face.get("embedding")
                    if not femb:
                        continue
                    femb_arr = np.array(femb, dtype=np.float32)
                    
                    best_cid = None
                    best_sim = -1.0
                    norm1 = np.linalg.norm(femb_arr)
                    if norm1 > 0:
                        for cid, cent in centroids.items():
                            sim = float(np.dot(femb_arr, cent) / norm1)
                            if sim > best_sim:
                                best_sim = sim
                                best_cid = cid
                            
                    if best_cid is not None and best_sim >= 0.75:
                        assigned_cid = best_cid
                        face["cluster_id"] = assigned_cid
                        face["matching_score"] = best_sim
                        face["identity_state"] = "stable"
                        
                        old_cent = centroids[assigned_cid]
                        cursor.execute("SELECT face_count FROM cluster_statistics WHERE cluster_id=?", (assigned_cid,))
                        row = cursor.fetchone()
                        count = row[0] if row else 1
                        
                        new_cent = (old_cent * count + femb_arr) / (count + 1)
                        norm = np.linalg.norm(new_cent)
                        if norm > 0:
                            new_cent /= norm
                        centroids[assigned_cid] = new_cent
                        
                        new_emb_blob = new_cent.tobytes()
                        conn.execute("""
                            UPDATE identity_clusters 
                            SET average_embedding=?, last_updated=? 
                            WHERE cluster_id=?
                        """, (new_emb_blob, time.time(), assigned_cid))
                        
                        conn.execute("""
                            UPDATE cluster_statistics 
                            SET face_count=face_count+1 
                            WHERE cluster_id=?
                        """, (assigned_cid,))
                    else:
                        cursor.execute("""
                            INSERT INTO identity_clusters 
                            (average_embedding, confidence, creation_timestamp, last_updated)
                            VALUES (?, ?, ?, ?)
                        """, (femb_arr.tobytes(), face.get("confidence", 1.0), time.time(), time.time()))
                        assigned_cid = cursor.lastrowid
                        face["cluster_id"] = assigned_cid
                        face["matching_score"] = 1.0
                        face["identity_state"] = "unclustered"
                        centroids[assigned_cid] = femb_arr
                        
                        conn.execute("""
                            INSERT INTO cluster_statistics 
                            (cluster_id, face_count, average_confidence, max_similarity, min_similarity)
                            VALUES (?, 1, ?, 1.0, 1.0)
                        """, (assigned_cid, face.get("confidence", 1.0)))
                        
                    bbox = face.get("bbox", [0, 0, 0, 0])
                    fconf = face.get("confidence", 1.0)
                    q = face.get("quality", {})
                    sharp = q.get("sharpness", 0.0)
                    exp = q.get("exposure", 0.0)
                    lm = face.get("landmarks", {})
                    orient = face.get("orientation", {})
                    femb_blob = femb_arr.tobytes()
                    
                    conn.execute("""
                        INSERT INTO identity_faces
                        (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence,
                         sharpness, exposure, landmarks, orientation, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (assigned_cid, file_path, bbox[0], bbox[1], bbox[2], bbox[3], fconf,
                          sharp, exp, json.dumps(lm), json.dumps(orient), femb_blob))
                conn.commit()
    except Exception as e:
        print(f"[cache_engine] Error doing incremental cluster update: {e}")


def get_face_embeddings(path: str) -> list:
    """Queries face metadata and deserializes binary BLOB face embeddings from SQLite, resolving cluster and person info."""
    import numpy as np
    faces = []
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, f.confidence, 
                           f.sharpness, f.exposure, f.landmarks, f.orientation, f.embedding,
                           f.cluster_id, s.face_count, c.person_id, p.name
                    FROM identity_faces f
                    LEFT JOIN cluster_statistics s ON f.cluster_id = s.cluster_id
                    LEFT JOIN identity_clusters c ON f.cluster_id = c.cluster_id
                    LEFT JOIN persons p ON c.person_id = p.person_id
                    WHERE f.file_path=?
                """, (path,))
                rows = cursor.fetchall()
                
                if not rows:
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
                            "embedding": embedding,
                            "cluster_id": None,
                            "cluster_confidence": 0.0,
                            "identity_state": "unclustered",
                            "cluster_size": 0,
                            "matching_score": 0.0,
                            "person_id": None,
                            "person_name": None
                        })
                    return faces
                    
                for row in rows:
                    bx, by, bw, bh, conf, sharp, exp, lm_json, orient_json, emb_blob, cid, csize, pid, pname = row
                    embedding = None
                    if emb_blob:
                        embedding = np.frombuffer(emb_blob, dtype=np.float32).tolist()
                    
                    matching_score = 1.0
                    if cid is not None:
                        cursor.execute("SELECT average_embedding FROM identity_clusters WHERE cluster_id=?", (cid,))
                        crow = cursor.fetchone()
                        if crow and crow[0] and emb_blob:
                            cent = np.frombuffer(crow[0], dtype=np.float32)
                            femb = np.frombuffer(emb_blob, dtype=np.float32)
                            dot = np.dot(femb, cent)
                            norm1 = np.linalg.norm(femb)
                            norm2 = np.linalg.norm(cent)
                            matching_score = float(dot / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0
                            
                    faces.append({
                        "bbox": [bx, by, bw, bh],
                        "confidence": conf,
                        "quality": {"sharpness": sharp, "exposure": exp},
                        "landmarks": json.loads(lm_json) if lm_json else {},
                        "orientation": json.loads(orient_json) if orient_json else {},
                        "embedding": embedding,
                        "cluster_id": cid,
                        "cluster_confidence": conf,
                        "identity_state": "stable" if cid is not None else "unclustered",
                        "cluster_size": csize or 0,
                        "matching_score": matching_score,
                        "person_id": pid,
                        "person_name": pname
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
    except Exception as e:
        print(f"[cache_engine] Error writing face embeddings for {path}: {e}")

def save_analysis_transaction(path: str, mtime: float, xmp_mtime: float, sha256: str, phash: str, ratio: float, timestamp: float, metrics: dict, faces: list):
    """Saves cache item, face embeddings, and performs incremental cluster update in a single transaction."""
    import numpy as np
    import time
    try:
        with _db_lock:
            with _get_db_connection() as conn:
                # 1. set_cached_item logic
                phash_str = str(phash) if phash is not None else None
                ts = timestamp.timestamp() if timestamp != datetime.datetime.min else 0.0
                metrics_json = json.dumps(metrics) if metrics else None
                conn.execute('''INSERT OR REPLACE INTO image_cache 
                                (file_path, mtime, xmp_mtime, sha256, phash, ratio, timestamp, metrics) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                             (path, mtime, xmp_mtime, sha256, phash_str, ratio, ts, metrics_json))
                             
                # 2. set_face_embeddings logic
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
                                  
                # 3. incremental_cluster_update logic
                conn.execute("DELETE FROM identity_faces WHERE file_path=?", (path,))
                
                cursor = conn.cursor()
                cursor.execute("SELECT cluster_id, average_embedding FROM identity_clusters WHERE status='active'")
                cluster_rows = cursor.fetchall()
                
                centroids = {}
                for cid, emb_blob in cluster_rows:
                    if emb_blob:
                        centroids[cid] = np.frombuffer(emb_blob, dtype=np.float32)
                        
                for face in faces:
                    femb = face.get("embedding")
                    if not femb:
                        continue
                    femb_arr = np.array(femb, dtype=np.float32)
                    
                    best_cid = None
                    best_sim = -1.0
                    norm1 = np.linalg.norm(femb_arr)
                    if norm1 > 0:
                        for cid, cent in centroids.items():
                            sim = float(np.dot(femb_arr, cent) / norm1)
                            if sim > best_sim:
                                best_sim = sim
                                best_cid = cid
                                
                    if best_cid is not None and best_sim >= 0.75:
                        assigned_cid = best_cid
                        face["cluster_id"] = assigned_cid
                        face["matching_score"] = best_sim
                        face["identity_state"] = "stable"
                        
                        old_cent = centroids[assigned_cid]
                        cursor.execute("SELECT face_count FROM cluster_statistics WHERE cluster_id=?", (assigned_cid,))
                        row = cursor.fetchone()
                        count = row[0] if row else 1
                        
                        new_cent = (old_cent * count + femb_arr) / (count + 1)
                        norm = np.linalg.norm(new_cent)
                        if norm > 0:
                            new_cent /= norm
                        centroids[assigned_cid] = new_cent
                        
                        new_emb_blob = new_cent.tobytes()
                        conn.execute("""
                            UPDATE identity_clusters 
                            SET average_embedding=?, last_updated=? 
                            WHERE cluster_id=?
                        """, (new_emb_blob, time.time(), assigned_cid))
                        
                        conn.execute("""
                            UPDATE cluster_statistics 
                            SET face_count=face_count+1 
                            WHERE cluster_id=?
                        """, (assigned_cid,))
                    else:
                        cursor.execute("""
                            INSERT INTO identity_clusters 
                            (average_embedding, confidence, creation_timestamp, last_updated)
                            VALUES (?, ?, ?, ?)
                        """, (femb_arr.tobytes(), face.get("confidence", 1.0), time.time(), time.time()))
                        assigned_cid = cursor.lastrowid
                        face["cluster_id"] = assigned_cid
                        face["matching_score"] = 1.0
                        face["identity_state"] = "new"
                        
                        centroids[assigned_cid] = femb_arr
                        conn.execute("""
                            INSERT INTO cluster_statistics (cluster_id, face_count)
                            VALUES (?, 1)
                        """, (assigned_cid,))
                        
                    # Save to identity_faces
                    bbox = face.get("bbox", [0, 0, 0, 0])
                    fconf = face.get("confidence", 1.0)
                    q = face.get("quality", {})
                    sharp = q.get("sharpness", 0.0)
                    exp = q.get("exposure", 0.0)
                    lm = face.get("landmarks", {})
                    orient = face.get("orientation", {})
                    femb_blob = femb_arr.tobytes()
                    
                    conn.execute("""
                        INSERT INTO identity_faces
                        (cluster_id, file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence,
                         sharpness, exposure, landmarks, orientation, embedding)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (assigned_cid, path, bbox[0], bbox[1], bbox[2], bbox[3], fconf,
                          sharp, exp, json.dumps(lm), json.dumps(orient), femb_blob))
    except Exception as e:
        print(f"[cache_engine] save_analysis_transaction error for {path}: {e}")
