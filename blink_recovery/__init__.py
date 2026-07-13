import cv2
import numpy as np
import math
from typing import List, Dict, Tuple, Optional

def classify_eye_state(left_openness: float, right_openness: float) -> str:
    """Classifies eye state: Fully open, Partially open, Closed, Wink, Squint."""
    if left_openness < 20.0 and right_openness < 20.0:
        return "Closed"
    elif (left_openness >= 65.0 and right_openness < 30.0) or (right_openness >= 65.0 and left_openness < 30.0):
        return "Wink"
    elif 20.0 <= left_openness < 45.0 and 20.0 <= right_openness < 45.0:
        return "Squint"
    elif left_openness >= 75.0 and right_openness >= 75.0:
        return "Fully open"
    else:
        return "Partially open"

def find_recovery_candidates(target_face: dict, photo_details_list: list) -> list:
    """
    Finds open-eye candidate face records in same-person clusters
    with matching pose, expression, and lighting.
    """
    candidates = []
    t_pid = target_face.get("person_id")
    if t_pid is None:
        t_pid = target_face.get("cluster_id")
    if t_pid is None:
        return []
        
    t_orient = target_face.get("orientation", target_face.get("subject_orientation", {}))
    t_yaw = t_orient.get("yaw", 0.0)
    t_pitch = t_orient.get("pitch", 0.0)
    t_roll = t_orient.get("roll", 0.0)
    t_smile = target_face.get("smile_confidence", 50.0)
    t_light = target_face.get("lighting_quality", 80.0)
    
    for photo in photo_details_list:
        path = photo.get("file_path")
        metrics = photo.get("metrics", {})
        if not metrics:
            continue
        faces = metrics.get("faces", [])
        
        for face in faces:
            c_pid = face.get("person_id")
            if c_pid is None:
                c_pid = face.get("cluster_id")
            if c_pid != t_pid:
                continue
                
            c_open = face.get("eye_openness", 0.0)
            if c_open < 75.0:
                continue
                
            c_orient = face.get("orientation", face.get("subject_orientation", {}))
            c_yaw = c_orient.get("yaw", 0.0)
            c_pitch = c_orient.get("pitch", 0.0)
            c_roll = c_orient.get("roll", 0.0)
            c_smile = face.get("smile_confidence", 50.0)
            c_light = face.get("lighting_quality", 80.0)
            
            if abs(t_yaw - c_yaw) > 12.0 or abs(t_pitch - c_pitch) > 12.0 or abs(t_roll - c_roll) > 12.0:
                continue
            if abs(t_smile - c_smile) > 25.0:
                continue
            if abs(t_light - c_light) > 25.0:
                continue
                
            face_copy = face.copy()
            face_copy["file_path"] = path
            candidates.append(face_copy)
            
    return candidates

def recover_blink(target_img: np.ndarray, target_face: dict, candidate_img: np.ndarray, candidate_face: dict) -> Tuple[np.ndarray, bool]:
    """
    Warps and blends open eyes from a candidate photo onto a target photo.
    Rejects correction and returns target_img if validations fail.
    """
    t_orient = target_face.get("orientation", target_face.get("subject_orientation", {}))
    c_orient = candidate_face.get("orientation", candidate_face.get("subject_orientation", {}))
    
    t_yaw = t_orient.get("yaw", 0.0)
    t_pitch = t_orient.get("pitch", 0.0)
    t_roll = t_orient.get("roll", 0.0)
    t_smile = target_face.get("smile_confidence", 50.0)
    t_light = target_face.get("lighting_quality", 80.0)
    
    c_yaw = c_orient.get("yaw", 0.0)
    c_pitch = c_orient.get("pitch", 0.0)
    c_roll = c_orient.get("roll", 0.0)
    c_smile = candidate_face.get("smile_confidence", 50.0)
    c_light = candidate_face.get("lighting_quality", 80.0)
    
    if abs(t_yaw - c_yaw) > 12.0 or abs(t_pitch - c_pitch) > 12.0 or abs(t_roll - c_roll) > 12.0:
        return target_img, False
    if abs(t_smile - c_smile) > 25.0:
        return target_img, False
    if abs(t_light - c_light) > 25.0:
        return target_img, False
        
    t_bbox = target_face.get("bbox", [0, 0, 100, 100])
    c_bbox = candidate_face.get("bbox", [0, 0, 100, 100])
    
    t_landmarks = target_face.get("landmarks", {})
    c_landmarks = candidate_face.get("landmarks", {})
    
    t_left = t_landmarks.get("left_eye")
    t_right = t_landmarks.get("right_eye")
    c_left = c_landmarks.get("left_eye")
    c_right = c_landmarks.get("right_eye")
    
    if not t_left or not t_right or not c_left or not c_right:
        return target_img, False
        
    out_img = target_img.copy()
    
    eye_pairs = [("left", t_left, c_left, t_bbox[2], c_bbox[2]), ("right", t_right, c_right, t_bbox[2], c_bbox[2])]
    
    for side, t_eye, c_eye, t_fw, c_fw in eye_pairs:
        crop_w = int(t_fw * 0.30)
        crop_h = int(t_fw * 0.20)
        if crop_w <= 0 or crop_h <= 0:
            continue
            
        tx1 = max(0, int(t_eye[0] - crop_w // 2))
        ty1 = max(0, int(t_eye[1] - crop_h // 2))
        tx2 = min(target_img.shape[1], tx1 + crop_w)
        ty2 = min(target_img.shape[0], ty1 + crop_h)
        
        cx1 = max(0, int(c_eye[0] - crop_w // 2))
        cy1 = max(0, int(c_eye[1] - crop_h // 2))
        cx2 = min(candidate_img.shape[1], cx1 + crop_w)
        cy2 = min(candidate_img.shape[0], cy1 + crop_h)
        
        c_patch = candidate_img[cy1:cy2, cx1:cx2]
        if c_patch.size == 0:
            continue
            
        t_patch = target_img[ty1:ty2, tx1:tx2]
        if t_patch.size > 0:
            c_patch = match_illumination(c_patch, t_patch)
            
        mask = np.zeros((ty2 - ty1, tx2 - tx1), dtype=np.float32)
        center = (mask.shape[1] // 2, mask.shape[0] // 2)
        axes = (int(mask.shape[1] * 0.4), int(mask.shape[0] * 0.3))
        cv2.ellipse(mask, center, axes, 0, 0, 360, 1.0, -1)
        mask = cv2.GaussianBlur(mask, (7, 7), 0)
        
        warp_mat = np.eye(2, 3, dtype=np.float32)
        dx = (t_eye[0] - tx1) - (c_eye[0] - cx1)
        dy = (t_eye[1] - ty1) - (c_eye[1] - cy1)
        warp_mat[0, 2] = dx
        warp_mat[1, 2] = dy
        
        warped_patch = cv2.warpAffine(c_patch, warp_mat, (tx2 - tx1, ty2 - ty1), borderMode=cv2.BORDER_REPLICATE)
        
        for c in range(3):
            out_img[ty1:ty2, tx1:tx2, c] = (
                warped_patch[:, :, c] * mask + out_img[ty1:ty2, tx1:tx2, c] * (1.0 - mask)
            ).astype(np.uint8)
            
    return out_img, True

def match_illumination(src: np.ndarray, target: np.ndarray) -> np.ndarray:
    """Matches the average color gain/offset of src patch to target patch."""
    src_f = src.astype(np.float32)
    tgt_f = target.astype(np.float32)
    
    out = src_f.copy()
    for c in range(3):
        src_mean = np.mean(src_f[:, :, c])
        tgt_mean = np.mean(tgt_f[:, :, c])
        src_std = np.std(src_f[:, :, c])
        tgt_std = np.std(tgt_f[:, :, c])
        
        if src_std > 0 and tgt_std > 0:
            out[:, :, c] = (src_f[:, :, c] - src_mean) * (tgt_std / src_std) + tgt_mean
        else:
            out[:, :, c] = src_f[:, :, c] - src_mean + tgt_mean
            
    return np.clip(out, 0, 255).astype(np.uint8)
