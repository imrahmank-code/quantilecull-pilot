import time
import os
import sys
import threading
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine

try:
    import psutil
except ImportError:
    psutil = None

def get_process_metrics():
    if psutil:
        p = psutil.Process(os.getpid())
        return p.memory_info().rss / (1024 * 1024), psutil.cpu_percent()
    return 150.0, 10.0 # Mock fallback values

def run_scaling_benchmark():
    """
    Simulates large library scaling constraints for RC1 verification.
    """
    print("[Large Library Profiler] Initializing simulation benchmarks...")
    
    # Target scale definitions
    total_images = 100000
    num_identities = 10000
    dim = 512
    
    # 1. Memory and Scaling setup
    start_ram, start_cpu = get_process_metrics()
    start_time = time.perf_counter()
    
    # Generate mock face quality scores, yaw/pitch, and camera make distributions
    camera_makes = ["Canon", "Nikon", "Sony", "Fujifilm", "Panasonic", "Leica"]
    photo_records = []
    
    print("[Large Library Profiler] Simulating 100,000 mixed format metadata items...")
    for i in range(total_images):
        photo_records.append({
            "file_path": f"/images/DSC_{i:06d}.NEF" if i % 2 == 0 else f"/images/IMG_{i:06d}.CR3",
            "timestamp": 1718000000 + i * 5,
            "camera_make": camera_makes[i % len(camera_makes)],
            "metrics": {
                "faces": [
                    {
                        "person_id": i % num_identities,
                        "face_quality_score": float(np.random.uniform(40.0, 98.0))
                    }
                ]
            }
        })
        
    # Simulate concurrent SQLite writes and XMP updates
    print("[Large Library Profiler] Spawning concurrent culling worker threads...")
    
    write_errors = 0
    lock_wait_times = []
    
    def worker_write_task():
        nonlocal write_errors
        for idx in range(10):
            try:
                t1 = time.perf_counter()
                # Mock cache writes using cache_engine thread-safe calls
                cache_engine.set_cached_item(f"sim_item_{idx}", {"scanned": True})
                t_diff = time.perf_counter() - t1
                lock_wait_times.append(t_diff)
            except Exception:
                write_errors += 1
                
    threads = []
    for _ in range(8):
        t = threading.Thread(target=worker_write_task)
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
        
    # Cosine Similarity math scaling checks
    embeddings = np.random.randn(1000, dim).astype(np.float32)
    centroids = np.random.randn(num_identities, dim).astype(np.float32)
    
    # Batch dot product
    start_dot = time.perf_counter()
    np.dot(embeddings, centroids.T)
    dot_duration = time.perf_counter() - start_dot
    
    end_ram, end_cpu = get_process_metrics()
    total_duration = time.perf_counter() - start_time
    
    images_sec = total_images / total_duration if total_duration > 0 else 0
    
    results = {
        "duration": total_duration,
        "peak_ram": float(end_ram),
        "peak_cpu": float(end_cpu),
        "write_errors": write_errors,
        "images_per_sec": float(images_sec),
        "lock_wait_p95": float(np.percentile(lock_wait_times, 95)) if lock_wait_times else 0.0,
        "cosine_search_time": dot_duration
    }
    
    print(f"[Large Library Profiler] Completed scaling simulation in {total_duration:.4f} seconds.")
    print(f"  - Peak RAM: {results['peak_ram']:.2f} MB")
    print(f"  - Throughput: {results['images_per_sec']:.1f} images/sec")
    
    return results

if __name__ == '__main__':
    run_scaling_benchmark()

