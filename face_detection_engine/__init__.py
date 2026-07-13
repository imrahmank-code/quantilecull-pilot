import cv2
import numpy as np
import math
from typing import List, Dict

def detect_faces(image_data: np.ndarray) -> List[Dict]:
    """
    Detects faces in the image data.
    Returns a list of face dictionaries, each containing:
      - bbox: [x, y, w, h]
      - confidence: float
      - landmarks: dict of key points (left_eye, right_eye, nose_tip, mouth_center)
      - orientation: dict of roll, pitch, yaw
      - quality: dict of sharpness, exposure
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
            if face_roi_hsv.size > 0:
                mean_v = np.mean(face_roi_hsv[:, :, 2])
                face_exposure = max(0.0, 100.0 - abs(mean_v - 130.0) * (100.0 / 120.0))
                
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
                "quality": {
                    "sharpness": float(face_sharpness),
                    "exposure": float(round(face_exposure, 1))
                }
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
            if face_roi_hsv.size > 0:
                mean_v = np.mean(face_roi_hsv[:, :, 2])
                face_exposure = max(0.0, 100.0 - abs(mean_v - 130.0) * (100.0 / 120.0))
                
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
                "quality": {
                    "sharpness": float(face_sharpness),
                    "exposure": float(round(face_exposure, 1))
                }
            })
            
    return faces
