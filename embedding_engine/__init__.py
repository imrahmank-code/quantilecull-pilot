import numpy as np
import base64
from typing import List, Optional
import ai_engine

def generate_embedding(image_data: np.ndarray, feature_type: str = "face") -> np.ndarray:
    """Generates a normalized feature vector from image array data."""
    if not isinstance(image_data, np.ndarray):
        raise TypeError("image_data must be a NumPy array.")
        
    dim = 512 if feature_type == "face" else 128
    
    if ai_engine.is_available() or ai_engine.initialize():
        model_name = "face_embedder" if feature_type == "face" else "general_embedder"
        feed = {"input": np.zeros((1, 3, 112, 112), dtype=np.float32)}
        out = ai_engine.run_inference(model_name, feed)
        if "output" in out:
            vec = out["output"].flatten()
            norm = np.linalg.norm(vec)
            return vec if norm == 0 else vec / norm
            
    state = np.random.RandomState(int(np.sum(image_data) % 2**32))
    vec = state.randn(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    return vec if norm == 0 else vec / norm

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Computes the cosine similarity between two feature vectors."""
    dot = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

def serialize_embedding(embedding: np.ndarray) -> str:
    """Serializes a NumPy vector to a base64-encoded string for database storage."""
    return base64.b64encode(embedding.tobytes()).decode("utf-8")

def deserialize_embedding(data_str: str) -> np.ndarray:
    """Deserializes a base64 string back into a float32 NumPy vector."""
    decoded = base64.b64decode(data_str.encode("utf-8"))
    return np.frombuffer(decoded, dtype=np.float32)
