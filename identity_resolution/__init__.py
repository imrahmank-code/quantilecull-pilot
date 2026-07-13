import os
import sqlite3
import json
import time
from typing import List, Dict, Tuple, Optional
import numpy as np
import cache_engine

def create_person(name: str, notes: Optional[str] = None) -> int:
    """Creates a new person profile in the database. Returns the person_id."""
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO persons (name, notes, creation_timestamp)
                    VALUES (?, ?, ?)
                """, (name, notes, time.time()))
                conn.commit()
                return cursor.lastrowid
    except Exception as e:
        print(f"[identity_resolution] Failed to create person '{name}': {e}")
        person = get_person_by_name(name)
        if person:
            return person["person_id"]
        raise

def get_person(person_id: int) -> Optional[dict]:
    """Retrieves a person profile by person_id."""
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT person_id, name, notes, creation_timestamp, face_count, key_face_path, key_face_bbox
                    FROM persons WHERE person_id=?
                """, (person_id,))
                row = cursor.fetchone()
                if row:
                    pid, name, notes, created, count, kpath, kbbox = row
                    return {
                        "person_id": pid,
                        "name": name,
                        "notes": notes,
                        "creation_timestamp": created,
                        "face_count": count,
                        "key_face_path": kpath,
                        "key_face_bbox": json.loads(kbbox) if kbbox else None
                    }
    except Exception as e:
        print(f"[identity_resolution] Failed to retrieve person {person_id}: {e}")
    return None

def get_person_by_name(name: str) -> Optional[dict]:
    """Retrieves a person profile by unique name."""
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT person_id, name, notes, creation_timestamp, face_count, key_face_path, key_face_bbox
                    FROM persons WHERE name=?
                """, (name,))
                row = cursor.fetchone()
                if row:
                    pid, pname, notes, created, count, kpath, kbbox = row
                    return {
                        "person_id": pid,
                        "name": pname,
                        "notes": notes,
                        "creation_timestamp": created,
                        "face_count": count,
                        "key_face_path": kpath,
                        "key_face_bbox": json.loads(kbbox) if kbbox else None
                    }
    except Exception as e:
        print(f"[identity_resolution] Failed to retrieve person by name '{name}': {e}")
    return None

def rename_person(person_id: int, new_name: str) -> None:
    """Updates a person's name."""
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                conn.execute("UPDATE persons SET name=? WHERE person_id=?", (new_name, person_id))
                conn.commit()
    except Exception as e:
        print(f"[identity_resolution] Failed to rename person {person_id} to '{new_name}': {e}")
        raise

def delete_person(person_id: int) -> None:
    """Deletes a person profile and unmaps any associated clusters."""
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                conn.execute("DELETE FROM persons WHERE person_id=?", (person_id,))
                conn.execute("UPDATE identity_clusters SET person_id=NULL WHERE person_id=?", (person_id,))
                conn.commit()
    except Exception as e:
        print(f"[identity_resolution] Failed to delete person {person_id}: {e}")
        raise

def associate_cluster_to_person(cluster_id: int, person_id: int) -> None:
    """Maps a face cluster to a specific person ID and updates the person's statistics."""
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                conn.execute("UPDATE identity_clusters SET person_id=? WHERE cluster_id=?", (person_id, cluster_id))
                
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT f.file_path, f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, f.confidence
                    FROM identity_faces f
                    JOIN identity_clusters c ON f.cluster_id = c.cluster_id
                    WHERE c.person_id=? AND f.confidence IS NOT NULL
                """, (person_id,))
                faces = cursor.fetchall()
                
                face_count = len(faces)
                key_face_path = None
                key_face_bbox_str = None
                
                if faces:
                    faces.sort(key=lambda x: x[5], reverse=True)
                    best_face = faces[0]
                    key_face_path = best_face[0]
                    key_face_bbox_str = json.dumps([best_face[1], best_face[2], best_face[3], best_face[4]])
                    
                conn.execute("""
                    UPDATE persons
                    SET face_count=?, key_face_path=?, key_face_bbox=?
                    WHERE person_id=?
                """, (face_count, key_face_path, key_face_bbox_str, person_id))
                conn.commit()
    except Exception as e:
        print(f"[identity_resolution] Failed to map cluster {cluster_id} to person {person_id}: {e}")
        raise

def list_persons() -> List[dict]:
    """Lists all registered persons."""
    persons = []
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT person_id, name, notes, creation_timestamp, face_count, key_face_path, key_face_bbox
                    FROM persons ORDER BY name ASC
                """)
                rows = cursor.fetchall()
                for row in rows:
                    pid, name, notes, created, count, kpath, kbbox = row
                    persons.append({
                        "person_id": pid,
                        "name": name,
                        "notes": notes,
                        "creation_timestamp": created,
                        "face_count": count,
                        "key_face_path": kpath,
                        "key_face_bbox": json.loads(kbbox) if kbbox else None
                    })
    except Exception as e:
        print(f"[identity_resolution] Failed to list persons: {e}")
    return persons

def get_identity_timeline(person_id: int) -> List[dict]:
    """
    Returns a chronologically sorted list of image occurrences for a person,
    grouping appearances with timestamps.
    """
    timeline = []
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT i.file_path, i.timestamp, f.bbox_x, f.bbox_y, f.bbox_w, f.bbox_h, f.confidence
                    FROM identity_faces f
                    JOIN identity_clusters c ON f.cluster_id = c.cluster_id
                    JOIN image_cache i ON f.file_path = i.file_path
                    WHERE c.person_id=? AND i.timestamp IS NOT NULL
                    ORDER BY i.timestamp ASC
                """, (person_id,))
                rows = cursor.fetchall()
                for row in rows:
                    path, ts, bx, by, bw, bh, conf = row
                    timeline.append({
                        "file_path": path,
                        "timestamp": ts,
                        "bbox": [bx, by, bw, bh],
                        "confidence": conf
                    })
    except Exception as e:
        print(f"[identity_resolution] Failed to load timeline for person {person_id}: {e}")
    return timeline

def search_photos_by_person(person_id: int) -> List[str]:
    """Returns a list of image paths where the specified person appears."""
    paths = []
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT DISTINCT f.file_path
                    FROM identity_faces f
                    JOIN identity_clusters c ON f.cluster_id = c.cluster_id
                    WHERE c.person_id=?
                """, (person_id,))
                paths = [r[0] for r in cursor.fetchall()]
    except Exception as e:
        print(f"[identity_resolution] Failed to search photos for person {person_id}: {e}")
    return paths

def migrate_unresolved_identities() -> int:
    """
    Finds all active clusters that do not belong to any person profile,
    and automatically groups them into generic named person profiles (e.g. "Person 1").
    Returns the number of resolved clusters.
    """
    resolved_count = 0
    try:
        with cache_engine._db_lock:
            with cache_engine._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT cluster_id FROM identity_clusters WHERE person_id IS NULL AND status='active'")
                cluster_ids = [r[0] for r in cursor.fetchall()]
                
                if not cluster_ids:
                    return 0
                    
                for cid in cluster_ids:
                    cursor.execute("SELECT name FROM persons WHERE name LIKE 'Person %'")
                    names = [r[0] for r in cursor.fetchall()]
                    suffixes = []
                    for n in names:
                        try:
                            suffixes.append(int(n.split(" ")[1]))
                        except Exception:
                            pass
                    next_idx = max(suffixes) + 1 if suffixes else 1
                    generic_name = f"Person {next_idx}"
                    
                    cursor.execute("""
                        INSERT INTO persons (name, creation_timestamp)
                        VALUES (?, ?)
                    """, (generic_name, time.time()))
                    new_pid = cursor.lastrowid
                    
                    conn.execute("UPDATE identity_clusters SET person_id=? WHERE cluster_id=?", (new_pid, cid))
                    
                    cursor.execute("""
                        SELECT file_path, bbox_x, bbox_y, bbox_w, bbox_h, confidence
                        FROM identity_faces WHERE cluster_id=?
                    """, (cid,))
                    faces = cursor.fetchall()
                    
                    face_count = len(faces)
                    key_face_path = None
                    key_face_bbox_str = None
                    if faces:
                        faces.sort(key=lambda x: x[5], reverse=True)
                        best_face = faces[0]
                        key_face_path = best_face[0]
                        key_face_bbox_str = json.dumps([best_face[1], best_face[2], best_face[3], best_face[4]])
                        
                    conn.execute("""
                        UPDATE persons
                        SET face_count=?, key_face_path=?, key_face_bbox=?
                        WHERE person_id=?
                    """, (face_count, key_face_path, key_face_bbox_str, new_pid))
                    
                    resolved_count += 1
                conn.commit()
    except Exception as e:
        print(f"[identity_resolution] Failed migration: {e}")
    return resolved_count
