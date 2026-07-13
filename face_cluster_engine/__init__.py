import numpy as np
import time
from typing import List, Dict, Tuple, Optional
import similarity_engine

def cluster_faces(embeddings: List[np.ndarray], method: str = "dbscan", **kwargs) -> List[int]:
    """
    Groups a flat list of face embeddings into cluster labels.
    Returns a list of cluster IDs corresponding to the input list, where -1 indicates noise.
    """
    if not embeddings:
        return []
        
    n = len(embeddings)
    if n == 1:
        return [0]
        
    sim_matrix = similarity_engine.build_similarity_matrix(embeddings)
    dist_matrix = 1.0 - sim_matrix
    
    threshold = kwargs.get("threshold", 0.25)
    
    if method == "dbscan":
        min_samples = kwargs.get("min_samples", 2)
        labels = -np.ones(n, dtype=int)
        cluster_id = 0
        
        for i in range(n):
            if labels[i] != -1:
                continue
                
            neighbors = np.where(dist_matrix[i] <= threshold)[0]
            if len(neighbors) < min_samples:
                continue
                
            labels[i] = cluster_id
            queue = list(neighbors)
            visited = {i}
            
            idx = 0
            while idx < len(queue):
                point = queue[idx]
                idx += 1
                
                if point not in visited:
                    visited.add(point)
                    
                if labels[point] == -1:
                    labels[point] = cluster_id
                    
                point_neighbors = np.where(dist_matrix[point] <= threshold)[0]
                if len(point_neighbors) >= min_samples:
                    for pm in point_neighbors:
                        if pm not in visited:
                            visited.add(pm)
                            queue.append(pm)
                            
            cluster_id += 1
            
        return labels.tolist()
        
    elif method == "hierarchical":
        labels = np.arange(n)
        active_clusters = {i: [i] for i in range(n)}
        
        dists = dist_matrix.copy()
        np.fill_diagonal(dists, np.inf)
        
        while len(active_clusters) > 1:
            min_idx = np.unravel_index(np.argmin(dists), dists.shape)
            min_dist = dists[min_idx]
            
            if min_dist > threshold:
                break
                
            c1, c2 = min_idx
            active_clusters[c1].extend(active_clusters[c2])
            for node in active_clusters[c2]:
                labels[node] = c1
            del active_clusters[c2]
            
            for c in active_clusters:
                if c == c1:
                    continue
                sub_dists = dist_matrix[np.ix_(active_clusters[c], active_clusters[c1])]
                avg_dist = np.mean(sub_dists)
                dists[c, c1] = avg_dist
                dists[c1, c] = avg_dist
                
            dists[c2, :] = np.inf
            dists[:, c2] = np.inf
            
        unique_labels = sorted(list(set(labels)))
        label_map = {old: new for new, old in enumerate(unique_labels)}
        return [label_map[l] for l in labels]
        
    else:
        raise ValueError(f"Unknown clustering method: {method}")

def update_clusters(new_embeddings: List[np.ndarray], existing_clusters: Dict[int, dict], **kwargs) -> Tuple[List[int], Dict[int, dict]]:
    """
    Incremental face clustering: assigns new embeddings to the existing cluster centers.
    Returns a tuple of:
      - list of assigned cluster IDs for the new embeddings
      - updated existing_clusters dict
    """
    threshold = kwargs.get("threshold", 0.75)
    assigned_labels = []
    
    centroids = {}
    for cid, c in existing_clusters.items():
        if c.get("status") == "active" and c.get("average_embedding"):
            centroids[cid] = np.array(c["average_embedding"], dtype=np.float32)
            
    next_cid = max(existing_clusters.keys()) + 1 if existing_clusters else 0
    
    for emb in new_embeddings:
        best_cid = None
        best_sim = -1.0
        
        for cid, cent in centroids.items():
            sim = similarity_engine.cosine_similarity(emb, cent)
            if sim > best_sim:
                best_sim = sim
                best_cid = cid
                
        if best_cid is not None and best_sim >= threshold:
            assigned_labels.append(best_cid)
            c = existing_clusters[best_cid]
            faces_count = len(c.get("faces", []))
            
            old_cent = centroids[best_cid]
            new_cent = (old_cent * faces_count + emb) / (faces_count + 1)
            norm = np.linalg.norm(new_cent)
            if norm > 0:
                new_cent /= norm
            centroids[best_cid] = new_cent
            c["average_embedding"] = new_cent.tolist()
            c["last_updated"] = time.time()
        else:
            assigned_labels.append(next_cid)
            centroids[next_cid] = emb
            existing_clusters[next_cid] = {
                "cluster_id": next_cid,
                "average_embedding": emb.tolist(),
                "confidence": 1.0,
                "creation_timestamp": time.time(),
                "last_updated": time.time(),
                "status": "active",
                "faces": []
            }
            next_cid += 1
            
    return assigned_labels, existing_clusters

def merge_clusters(cluster_id_1: int, cluster_id_2: int, existing_clusters: Dict[int, dict]) -> Dict[int, dict]:
    """Merges cluster_id_2 into cluster_id_1, consolidating all faces and recalculating the centroid."""
    if cluster_id_1 not in existing_clusters or cluster_id_2 not in existing_clusters:
        return existing_clusters
        
    c1 = existing_clusters[cluster_id_1]
    c2 = existing_clusters[cluster_id_2]
    
    c1["faces"].extend(c2["faces"])
    c2["faces"] = []
    c2["status"] = "merged"
    c2["last_updated"] = time.time()
    
    embs = [np.array(f["embedding"], dtype=np.float32) for f in c1["faces"] if f.get("embedding")]
    if embs:
        avg = np.mean(embs, axis=0)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg /= norm
        c1["average_embedding"] = avg.tolist()
        
    c1["last_updated"] = time.time()
    return existing_clusters

def split_cluster(cluster_id: int, face_ids_to_split: List[int], existing_clusters: Dict[int, dict]) -> Dict[int, dict]:
    """Splits specific face IDs out of an existing cluster, forming a new identity cluster."""
    if cluster_id not in existing_clusters:
        return existing_clusters
        
    c = existing_clusters[cluster_id]
    faces_to_move = [f for f in c["faces"] if f.get("face_id") in face_ids_to_split]
    c["faces"] = [f for f in c["faces"] if f.get("face_id") not in face_ids_to_split]
    
    embs_orig = [np.array(f["embedding"], dtype=np.float32) for f in c["faces"] if f.get("embedding")]
    if embs_orig:
        avg = np.mean(embs_orig, axis=0)
        norm = np.linalg.norm(avg)
        if norm > 0:
            avg /= norm
        c["average_embedding"] = avg.tolist()
    c["last_updated"] = time.time()
    
    if faces_to_move:
        new_cid = max(existing_clusters.keys()) + 1
        embs_new = [np.array(f["embedding"], dtype=np.float32) for f in faces_to_move if f.get("embedding")]
        avg_new = np.zeros(512, dtype=np.float32)
        if embs_new:
            avg_new = np.mean(embs_new, axis=0)
            norm = np.linalg.norm(avg_new)
            if norm > 0:
                avg_new /= norm
                
        existing_clusters[new_cid] = {
            "cluster_id": new_cid,
            "average_embedding": avg_new.tolist(),
            "confidence": np.mean([f.get("confidence", 1.0) for f in faces_to_move]),
            "creation_timestamp": time.time(),
            "last_updated": time.time(),
            "status": "active",
            "faces": faces_to_move
        }
        
    return existing_clusters
