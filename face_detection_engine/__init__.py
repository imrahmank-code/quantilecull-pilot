import cv2
import numpy as np
import math
from typing import List, Dict

def detect_faces(image_data: np.ndarray) -> List[Dict]:
    """
    Detects faces in the image data and performs Expression Intelligence scoring.
    Returns a list of face dictionaries.
    """
    import image_analyzer
    
    h, w = image_data.shape[:2]
    mp_faces = []
    try:
        mp_faces = image_analyzer._analyze_eyes_mediapipe(image_data)
    except Exception as e:
        print(f"[face_detection_engine] MediaPipe processing skipped: {e}")
        
    faces = []
    
    if mp_faces:
        for idx, mp_face in enumerate(mp_faces):
            x, y, fw, fh = mp_face["x"], mp_face["y"], mp_face["w"], mp_face["h"]
            
            left_eye = mp_face.get("left_eye_landmarks", [])
            right_eye = mp_face.get("right_eye_landmarks", [])
            
            left_eye_center = np.mean(left_eye, axis=0).tolist() if len(left_eye) > 0 else [x + fw * 0.35, y + fh * 0.4]
            right_eye_center = np.mean(right_eye, axis=0).tolist() if len(right_eye) > 0 else [x + fw * 0.65, y + fh * 0.4]
            nose_tip = [x + fw * 0.5, y + fh * 0.55]
            mouth_center = [x + fw * 0.5, y + fh * 0.75]
            
            dy = right_eye_center[1] - left_eye_center[1]
            dx = right_eye_center[0] - left_eye_center[0]
            roll = math.degrees(math.atan2(dy, dx)) if dx != 0 else 0.0
            
            d_left = math.sqrt((nose_tip[0] - left_eye_center[0])**2 + (nose_tip[1] - left_eye_center[1])**2)
            d_right = math.sqrt((nose_tip[0] - right_eye_center[0])**2 + (nose_tip[1] - right_eye_center[1])**2)
            yaw = float(round(math.degrees(math.atan2(d_left - d_right, (d_left + d_right)/2)) * 1.5, 1)) if (d_left + d_right) > 0 else 0.0
            
            pitch = float(round(mp_face.get("camera_facing", 90.0) - 90.0, 1))
            
            gray = cv2.cvtColor(image_data, cv2.COLOR_RGB2GRAY)
            x1, y1 = max(0, int(x)), max(0, int(y))
            x2, y2 = min(w, int(x + fw)), min(h, int(y + fh))
            face_roi = gray[y1:y2, x1:x2]
            
            face_sharpness = 50.0
            if face_roi.size > 0:
                face_roi_filtered = cv2.GaussianBlur(face_roi, (3, 3), 0)
                face_lap = cv2.Laplacian(face_roi_filtered, cv2.CV_64F).var()
                face_denom = image_analyzer._get_dynamic_denominator(image_data.shape, base_denom=30.0)
                face_sharpness = round(100 * (1.0 - math.exp(-face_lap / face_denom)), 1)
                
            hsv = cv2.cvtColor(image_data, cv2.COLOR_RGB2HSV)
            face_roi_hsv = hsv[y1:y2, x1:x2]
            face_exposure = 80.0
            lighting_quality = 80.0
            if face_roi_hsv.size > 0:
                mean_v = np.mean(face_roi_hsv[:, :, 2])
                std_v = np.std(face_roi_hsv[:, :, 2])
                face_exposure = max(0.0, 100.0 - abs(mean_v - 130.0) * (100.0 / 120.0))
                mean_factor = max(0.0, 1.0 - abs(mean_v - 130.0) / 110.0)
                contrast_factor = min(1.0, std_v / 40.0)
                lighting_quality = float(round(mean_factor * contrast_factor * 100.0, 1))
                
            eye_openness = mp_face.get("eye_openness", 90.0)
            blink_probability = float(round(100.0 - eye_openness, 1))
            smile_confidence = mp_face.get("smile_confidence", 50.0)
            occlusion_score = mp_face.get("occlusion_score", 0.0)
            expression_score = float(round(0.4 * eye_openness + 0.6 * smile_confidence, 1))
            
            looking_at_camera = abs(yaw) < 15.0 and abs(pitch) < 15.0
            
            head_pose_score = float(round(max(0.0, 100.0 - (abs(yaw) + abs(pitch) + abs(roll)) * 1.2), 1))
            
            face_quality_score = float(round(
                0.3 * face_sharpness +
                0.2 * eye_openness +
                0.15 * smile_confidence +
                0.15 * head_pose_score +
                0.1 * lighting_quality +
                0.1 * (100.0 - occlusion_score),
                1
            ))
            
            faces.append({
                "bbox": [int(x), int(y), int(fw), int(fh)],
                "confidence": float(mp_face.get("confidence", 0.95)),
                "landmarks": {
                    "left_eye": left_eye_center,
                    "right_eye": right_eye_center,
                    "nose_tip": nose_tip,
                    "mouth_center": mouth_center
                },
                "orientation": {
                    "roll": float(round(roll, 1)),
                    "pitch": float(round(pitch, 1)),
                    "yaw": float(round(yaw, 1))
                },
                "subject_orientation": {
                    "roll": float(round(roll, 1)),
                    "pitch": float(round(pitch, 1)),
                    "yaw": float(round(yaw, 1))
                },
                "quality": {
                    "sharpness": float(face_sharpness),
                    "exposure": float(round(face_exposure, 1))
                },
                "eye_openness": float(round(eye_openness, 1)),
                "blink_probability": blink_probability,
                "smile_confidence": float(round(smile_confidence, 1)),
                "face_sharpness": float(face_sharpness),
                "occlusion_score": float(round(occlusion_score, 1)),
                "lighting_quality": lighting_quality,
                "expression_score": expression_score,
                "expression_confidence": expression_score,
                "looking_at_camera": looking_at_camera,
                "looking_toward_camera": looking_at_camera,
                "head_pose_score": head_pose_score,
                "head_pose_quality": head_pose_score,
                "face_quality_score": face_quality_score
            })
            
    else:
        faces_raw = image_analyzer._detect_faces_dnn(image_data)
        for face_raw in faces_raw:
            x, y, fw, fh, conf = face_raw
            left_eye_center = [x + fw * 0.35, y + fh * 0.4]
            right_eye_center = [x + fw * 0.65, y + fh * 0.4]
            nose_tip = [x + fw * 0.5, y + fh * 0.55]
            mouth_center = [x + fw * 0.5, y + fh * 0.75]
            
            gray = cv2.cvtColor(image_data, cv2.COLOR_RGB2GRAY)
            x1, y1 = max(0, int(x)), max(0, int(y))
            x2, y2 = min(w, int(x + fw)), min(h, int(y + fh))
            face_roi = gray[y1:y2, x1:x2]
            face_sharpness = 50.0
            if face_roi.size > 0:
                face_roi_filtered = cv2.GaussianBlur(face_roi, (3, 3), 0)
                face_lap = cv2.Laplacian(face_roi_filtered, cv2.CV_64F).var()
                face_denom = image_analyzer._get_dynamic_denominator(image_data.shape, base_denom=30.0)
                face_sharpness = round(100 * (1.0 - math.exp(-face_lap / face_denom)), 1)
                
            hsv = cv2.cvtColor(image_data, cv2.COLOR_RGB2HSV)
            face_roi_hsv = hsv[y1:y2, x1:x2]
            face_exposure = 80.0
            lighting_quality = 80.0
            if face_roi_hsv.size > 0:
                mean_v = np.mean(face_roi_hsv[:, :, 2])
                std_v = np.std(face_roi_hsv[:, :, 2])
                face_exposure = max(0.0, 100.0 - abs(mean_v - 130.0) * (100.0 / 120.0))
                mean_factor = max(0.0, 1.0 - abs(mean_v - 130.0) / 110.0)
                contrast_factor = min(1.0, std_v / 40.0)
                lighting_quality = float(round(mean_factor * contrast_factor * 100.0, 1))
                
            eye_openness = 80.0
            blink_probability = 20.0
            smile_confidence = 50.0
            occlusion_score = 0.0
            expression_score = 62.0
            looking_at_camera = True
            head_pose_score = 80.0
            
            face_quality_score = float(round(
                0.3 * face_sharpness +
                0.2 * eye_openness +
                0.15 * smile_confidence +
                0.15 * head_pose_score +
                0.1 * lighting_quality +
                0.1 * (100.0 - occlusion_score),
                1
            ))
            
            faces.append({
                "bbox": [int(x), int(y), int(fw), int(fh)],
                "confidence": float(conf),
                "landmarks": {
                    "left_eye": left_eye_center,
                    "right_eye": right_eye_center,
                    "nose_tip": nose_tip,
                    "mouth_center": mouth_center
                },
                "orientation": {
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": 0.0
                },
                "subject_orientation": {
                    "roll": 0.0,
                    "pitch": 0.0,
                    "yaw": 0.0
                },
                "quality": {
                    "sharpness": float(face_sharpness),
                    "exposure": float(round(face_exposure, 1))
                },
                "eye_openness": eye_openness,
                "blink_probability": blink_probability,
                "smile_confidence": smile_confidence,
                "face_sharpness": float(face_sharpness),
                "occlusion_score": occlusion_score,
                "lighting_quality": lighting_quality,
                "expression_score": expression_score,
                "expression_confidence": expression_score,
                "looking_at_camera": looking_at_camera,
                "looking_toward_camera": looking_at_camera,
                "head_pose_score": head_pose_score,
                "head_pose_quality": head_pose_score,
                "face_quality_score": face_quality_score
            })
            
    return faces
