import numpy as np
import time
from typing import Dict, List, Optional
import cache_engine
import face_cluster_engine

class IdentityGraph:
    def __init__(self):
        self.clusters = {}
        self.load_from_db()
        
    def load_from_db(self):
        """Loads the graph representation from the persistent SQLite cache database."""
        db_clusters = cache_engine.get_clusters()
        self.clusters = {c["cluster_id"]: c for c in db_clusters}
        
    def save_to_db(self):
        """Persists the graph state to the database."""
        cache_engine.save_clusters(list(self.clusters.values()))
        
    def add_face(self, file_path: str, face: dict, threshold: float = 0.75) -> int:
        """
        Dynamically adds a single face instance to the graph incrementally.
        Returns the assigned cluster ID.
        """
        femb = face.get("embedding")
        if not femb:
            return -1
            
        femb_arr = np.array(femb, dtype=np.float32)
        best_cid = None
        best_sim = -1.0
        
        for cid, c in self.clusters.items():
            if c.get("status") == "active" and c.get("average_embedding"):
                cent = np.array(c["average_embedding"], dtype=np.float32)
                dot = np.dot(femb_arr, cent)
                norm1 = np.linalg.norm(femb_arr)
                norm2 = np.linalg.norm(cent)
                sim = float(dot / (norm1 * norm2)) if norm1 > 0 and norm2 > 0 else 0.0
                if sim > best_sim:
                    best_sim = sim
                    best_cid = cid
                    
        if best_cid is not None and best_sim >= threshold:
            assigned_cid = best_cid
            face["cluster_id"] = assigned_cid
            face["matching_score"] = best_sim
            face["identity_state"] = "stable"
            
            c = self.clusters[assigned_cid]
            faces_count = len(c["faces"])
            old_cent = np.array(c["average_embedding"], dtype=np.float32)
            new_cent = (old_cent * faces_count + femb_arr) / (faces_count + 1)
            norm = np.linalg.norm(new_cent)
            if norm > 0:
                new_cent /= norm
            c["average_embedding"] = new_cent.tolist()
            c["last_updated"] = time.time()
            c["faces"].append(face)
            
            c["statistics"]["face_count"] = faces_count + 1
            sims = [best_sim]
            for f in c["faces"]:
                if f.get("matching_score") is not None:
                    sims.append(f["matching_score"])
            c["statistics"]["max_similarity"] = float(max(sims))
            c["statistics"]["min_similarity"] = float(min(sims))
            c["statistics"]["average_confidence"] = float(np.mean([f.get("confidence", 1.0) for f in c["faces"]]))
        else:
            assigned_cid = max(self.clusters.keys()) + 1 if self.clusters else 0
            face["cluster_id"] = assigned_cid
            face["matching_score"] = 1.0
            face["identity_state"] = "unclustered"
            
            self.clusters[assigned_cid] = {
                "cluster_id": assigned_cid,
                "average_embedding": femb,
                "confidence": face.get("confidence", 1.0),
                "creation_timestamp": time.time(),
                "last_updated": time.time(),
                "status": "active",
                "statistics": {
                    "face_count": 1,
                    "average_confidence": face.get("confidence", 1.0),
                    "max_similarity": 1.0,
                    "min_similarity": 1.0
                },
                "faces": [face]
            }
            
        return assigned_cid

    def merge_identities(self, cid1: int, cid2: int, details: str = ""):
        """Merges cluster cid2 into cid1, recording it in history."""
        self.clusters = face_cluster_engine.merge_clusters(cid1, cid2, self.clusters)
        self.log_history("merge", cid1, cid2, details)
        self.save_to_db()
        
    def split_identity(self, cid: int, face_ids: List[int], details: str = ""):
        """Splits specific face IDs out of a cluster, creating a new identity."""
        self.clusters = face_cluster_engine.split_cluster(cid, face_ids, self.clusters)
        new_cid = max(self.clusters.keys())
        self.log_history("split", cid, new_cid, details)
        self.save_to_db()
        
    def log_history(self, action: str, cid1: int, cid2: int, details: str):
        """Saves merge/split history records directly to the SQLite table."""
        try:
            with cache_engine._db_lock:
                with cache_engine._get_db_connection() as conn:
                    conn.execute("""
                        INSERT INTO cluster_history (action_type, cluster_id_1, cluster_id_2, timestamp, details)
                        VALUES (?, ?, ?, ?, ?)
                    """, (action, cid1, cid2, time.time(), details))
                    conn.commit()
        except Exception as e:
            print(f"[IdentityGraph] Failed to log history: {e}")
