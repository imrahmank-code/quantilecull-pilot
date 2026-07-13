import os
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple

def segment_timeline(photo_details: List[Dict[str, Any]], gap_seconds: int = 900) -> List[List[Dict[str, Any]]]:
    """
    Segments a photo collection chronologically into distinct event chapters.
    A new chapter starts if the time gap between consecutive photos exceeds gap_seconds.
    """
    if not photo_details:
        return []
        
    sorted_photos = sorted(photo_details, key=lambda x: x.get("timestamp", 0))
    
    chapters = []
    current_chapter = [sorted_photos[0]]
    
    for i in range(1, len(sorted_photos)):
        prev_time = sorted_photos[i - 1].get("timestamp", 0)
        curr_time = sorted_photos[i].get("timestamp", 0)
        
        if (curr_time - prev_time) > gap_seconds:
            chapters.append(current_chapter)
            current_chapter = [sorted_photos[i]]
        else:
            current_chapter.append(sorted_photos[i])
            
    if current_chapter:
        chapters.append(current_chapter)
        
    return chapters

def classify_scene(photo: Dict[str, Any]) -> str:
    """
    Heuristically infers the scene type: Ceremony, Reception, Portraits,
    Dance Floor, Details/Decor, or General based on faces and visual scores.
    """
    metrics = photo.get("metrics", {})
    if not metrics:
        return "General"
        
    faces = metrics.get("faces", [])
    num_faces = len(faces)
    
    if num_faces == 0:
        return "Details/Decor"
        
    if num_faces in (1, 2):
        for face in faces:
            bbox = face.get("bbox", [0, 0, 100, 100])
            fw, fh = bbox[2], bbox[3]
            if fw > 150 or fh > 150:
                return "Portraits"
        return "General"
        
    if 3 <= num_faces <= 6:
        avg_smile = sum(f.get("smile_confidence", 50.0) for f in faces) / num_faces
        if avg_smile > 60.0:
            return "Reception"
        return "Ceremony"
        
    if num_faces > 6:
        avg_smile = sum(f.get("smile_confidence", 50.0) for f in faces) / num_faces
        if avg_smile > 55.0:
            return "Dance Floor"
        return "Ceremony"
        
    return "General"

def select_highlights(photo_details: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Selects the top_n highlight photos based on average face quality scores
    and exposure attributes.
    """
    def get_photo_score(photo: Dict[str, Any]) -> float:
        metrics = photo.get("metrics", {})
        if not metrics:
            return 0.0
        faces = metrics.get("faces", [])
        if not faces:
            return 50.0
            
        face_avg = sum(f.get("face_quality_score", 50.0) for f in faces) / len(faces)
        return face_avg

    graded_photos = []
    for p in photo_details:
        score = get_photo_score(p)
        graded_photos.append((score, p))
        
    graded_photos.sort(key=lambda x: x[0], reverse=True)
    return [p for score, p in graded_photos[:top_n]]

def detect_coverage_gaps(photo_details: List[Dict[str, Any]], all_persons: List[int]) -> Dict[str, Any]:
    """
    Identifies missing narrative chapters or underrepresented people in highlights.
    """
    if not photo_details:
        return {"underrepresented_people": [], "long_duration_gaps": []}
        
    person_counts = {pid: 0 for pid in all_persons}
    total_face_appearances = 0
    
    for photo in photo_details:
        metrics = photo.get("metrics", {})
        if not metrics:
            continue
        faces = metrics.get("faces", [])
        for face in faces:
            pid = face.get("person_id")
            if pid is None:
                pid = face.get("cluster_id")
            if pid in person_counts:
                person_counts[pid] += 1
                total_face_appearances += 1
                
    underrepresented = []
    if total_face_appearances > 0:
        for pid, count in person_counts.items():
            if (count / total_face_appearances) < 0.05:
                underrepresented.append(pid)
                
    sorted_photos = sorted(photo_details, key=lambda x: x.get("timestamp", 0))
    gaps = []
    for i in range(1, len(sorted_photos)):
        t1 = sorted_photos[i - 1].get("timestamp", 0)
        t2 = sorted_photos[i].get("timestamp", 0)
        diff = t2 - t1
        if diff > 3600:
            gaps.append((t1, t2, diff))
            
    return {
        "underrepresented_people": underrepresented,
        "long_duration_gaps": gaps
    }

def export_dam_collection(photo_details: List[Dict[str, Any]], export_path: str) -> bool:
    """
    Generates a simple Lightroom-compatible XML collection list of files.
    """
    try:
        root = ET.Element("collection", name="QuantileCull Highlights")
        for photo in photo_details:
            path = photo.get("file_path", "")
            if path:
                ET.SubElement(root, "photo", path=path)
                
        tree = ET.ElementTree(root)
        os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
        tree.write(export_path, encoding="utf-8", xml_declaration=True)
        return True
    except Exception as e:
        print(f"[storytelling_engine] Export failed: {e}")
        return False
