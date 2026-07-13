import numpy as np
from typing import List, Tuple

def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Computes the cosine similarity between two feature vectors."""
    dot = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot / (norm1 * norm2))

def compute_distance(vec1: np.ndarray, vec2: np.ndarray, metric: str = "cosine") -> float:
    """Computes distance between two vectors. Metric can be 'cosine' or 'euclidean'."""
    if metric == "cosine":
        return 1.0 - cosine_similarity(vec1, vec2)
    elif metric == "euclidean":
        return float(np.linalg.norm(vec1 - vec2))
    else:
        raise ValueError(f"Unknown metric: {metric}")

def find_similar_faces(face_embedding: np.ndarray, candidate_embeddings: List[np.ndarray], threshold: float = 0.75) -> List[Tuple[int, float]]:
    """Finds indices of candidate embeddings with similarity above the threshold, sorted by descending similarity."""
    matches = []
    for idx, candidate in enumerate(candidate_embeddings):
        sim = cosine_similarity(face_embedding, candidate)
        if sim >= threshold:
            matches.append((idx, sim))
    # Sort descending by similarity
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches

def build_similarity_matrix(embeddings: List[np.ndarray]) -> np.ndarray:
    """Builds a similarity matrix (symmetric, values between -1 and 1) for a list of embeddings."""
    n = len(embeddings)
    matrix = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i, n):
            sim = cosine_similarity(embeddings[i], embeddings[j])
            matrix[i, j] = sim
            matrix[j, i] = sim
    return matrix
