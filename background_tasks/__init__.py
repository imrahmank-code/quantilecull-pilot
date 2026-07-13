import threading
import queue
import time
import os
from concurrent.futures import ThreadPoolExecutor

class BackgroundTaskManager:
    def __init__(self, max_workers: int = 2):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks = {}  # task_id -> cancel_event
        self.tasks_lock = threading.Lock()

    def submit_task(self, task_id: str, fn, *args, **kwargs) -> threading.Event:
        """Submits a cancelable task to the background queue."""
        self.cancel_task(task_id)
        
        cancel_event = threading.Event()
        with self.tasks_lock:
            self.active_tasks[task_id] = cancel_event

        def wrapper():
            try:
                fn(cancel_event, *args, **kwargs)
            except Exception as e:
                print(f"[background_tasks] Error running task {task_id}: {e}")
            finally:
                with self.tasks_lock:
                    if self.active_tasks.get(task_id) == cancel_event:
                        self.active_tasks.pop(task_id, None)

        self.executor.submit(wrapper)
        return cancel_event

    def cancel_task(self, task_id: str):
        """Signals cancellation to an active task."""
        with self.tasks_lock:
            cancel_event = self.active_tasks.pop(task_id, None)
            if cancel_event:
                cancel_event.set()

    def cancel_all(self):
        """Cancels all active background tasks."""
        with self.tasks_lock:
            for task_id, cancel_event in list(self.active_tasks.items()):
                cancel_event.set()
            self.active_tasks.clear()

# Global background task manager instance
background_manager = BackgroundTaskManager()

def background_precache_thumbnails(cancel_event: threading.Event, image_paths: list, process_fn):
    """Background task that pre-caches thumbnails/analysis metrics for all images."""
    print(f"[background_tasks] Starting thumbnail pre-caching for {len(image_paths)} images...")
    for i, path in enumerate(image_paths):
        if cancel_event.is_set():
            print("[background_tasks] Pre-caching cancelled.")
            break
            
        try:
            # Process single image (this triggers cache hydration)
            process_fn(path)
        except Exception as e:
            print(f"[background_tasks] Failed to pre-cache {os.path.basename(path)}: {e}")
            
    print("[background_tasks] Pre-caching complete.")

def background_preload_images(cancel_event: threading.Event, current_path: str, all_paths: list, process_fn, window_size: int = 3):
    """
    Background task that pre-caches surrounding images.
    Caches the nearest 'window_size' next and previous images.
    """
    if current_path not in all_paths:
        return
        
    idx = all_paths.index(current_path)
    # Collect adjacent indices
    indices_to_preload = []
    for offset in range(1, window_size + 1):
        if idx + offset < len(all_paths):
            indices_to_preload.append(idx + offset)
        if idx - offset >= 0:
            indices_to_preload.append(idx - offset)
            
    paths_to_preload = [all_paths[i] for i in indices_to_preload]
    
    print(f"[background_tasks] Preloading {len(paths_to_preload)} adjacent images...")
    for path in paths_to_preload:
        if cancel_event.is_set():
            break
        try:
            process_fn(path)
        except Exception as e:
            pass
