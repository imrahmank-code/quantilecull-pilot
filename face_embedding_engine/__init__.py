import numpy as np
from typing import Optional
import embedding_engine

def generate_face_embedding(face_crop: np.ndarray) -> np.ndarray:
    """Generates a stable 512-dimensional normalized embedding vector for a cropped face region."""
    return embedding_engine.generate_embedding(face_crop, "face")
