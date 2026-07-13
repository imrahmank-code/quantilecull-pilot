import time
import os
import sys
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine
import similarity_engine

def run_scaling_benchmark():
    """
    Benchmarks culling indexes search and L2 cosine distance math scaling bounds.
    Simulates:
      - 100,000 image metadata records
      - 100,000 face embeddings (512-dim vectors)
      - 10,000 identity centroids
    """
    print("[Benchmark] Generating mock large culling library stats...")
    num_embeddings = 100000
    dim = 512
    
    # Generate 100,000 random unit-normalized embeddings
    embeddings = np.random.randn(num_embeddings, dim).astype(np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    embeddings /= np.where(norms == 0, 1.0, norms)
    
    # Generate 10,000 random unit-normalized centroids
    num_centroids = 10000
    centroids = np.random.randn(num_centroids, dim).astype(np.float32)
    c_norms = np.linalg.norm(centroids, axis=1, keepdims=True)
    centroids /= np.where(c_norms == 0, 1.0, c_norms)
    
    print(f"[Benchmark] Target dimensions: {num_embeddings} embeddings, {num_centroids} centroids")
    
    # 1. Measure Cosine Similarity search matrix multiplication time
    start = time.perf_counter()
    # Batch multiply: 100 queries against all 10,000 centroids
    queries = embeddings[:100]
    similarities = np.dot(queries, centroids.T)
    top_matches = np.argmax(similarities, axis=1)
    duration = time.perf_counter() - start
    
    print(f"[Benchmark] Cosine Search matrix multiplication (100 queries against 10,000 centroids): {duration:.4f} seconds")
    return duration

if __name__ == '__main__':
    run_scaling_benchmark()
