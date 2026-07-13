from typing import List, Dict, Any

def select_best_shots(photo_details: List[Dict[str, Any]]) -> Dict[int, str]:
    """
    Compares face quality scores for each person across multiple images.
    Returns a dictionary mapping person_id (or cluster_id fallback) to the file_path of the best shot.
    """
    best_scores = {}
    
    for photo in photo_details:
        path = photo.get("file_path")
        metrics = photo.get("metrics", {})
        if not metrics:
            continue
        faces = metrics.get("faces", [])
        
        for face in faces:
            pid = face.get("person_id")
            if pid is None:
                pid = face.get("cluster_id")
            if pid is None:
                continue
                
            q_score = face.get("face_quality_score", 0.0)
            
            if pid not in best_scores or q_score > best_scores[pid][0]:
                best_scores[pid] = (q_score, path)
                
    return {pid: path for pid, (score, path) in best_scores.items()}
