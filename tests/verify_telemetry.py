import os
import sys
import time
import shutil
import json
import threading
from pathlib import Path
from PIL import Image

# Add workspace root to path to import local modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from telemetry import TelemetryLogger, TelemetryLevel, CancellationToken
from recovery import RecoveryManager
from image_analyzer import process_and_group_generator

def generate_dummy_images(dir_path, count):
    os.makedirs(dir_path, exist_ok=True)
    print(f"Generating {count} dummy 1x1 JPEG images...")
    img = Image.new('RGB', (1, 1), color='red')
    for i in range(count):
        img.save(os.path.join(dir_path, f"dummy_{i:04d}.jpg"), "JPEG")
    print("Generation complete.")

def main():
    print("=== QuantileCull Telemetry & Cancellation Stress Test ===")
    
    # Setup test paths
    test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch_test_stress")
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
        
    generate_dummy_images(test_dir, 1000)
    
    # Scan directory for images
    image_paths = [os.path.join(test_dir, f) for f in os.listdir(test_dir) if f.endswith(".jpg")]
    
    # Initialize Managers
    logger = TelemetryLogger()
    recovery = RecoveryManager()
    
    # Clear any old recovery checkpoints
    recovery.clear_checkpoint()
    
    token = CancellationToken()
    run_context = {
        "run_id": "TEST-STRESS-RUN-001",
        "job_id": "TEST-JOB-001"
    }
    
    # Checkpoints counter helper
    checkpoint_calls = []
    def save_checkpoint_fn(proc_paths, rem_paths):
        checkpoint_calls.append(len(proc_paths))
        recovery.save_checkpoint(
            "TEST-JOB-001", 
            proc_paths, 
            rem_paths, 
            threshold=12, 
            top_percent=25, 
            target_path=test_dir
        )
        print(f"[Test Checkpoint] Processed: {len(proc_paths)}, Remaining: {len(rem_paths)}")
        
    # Run pipeline generator in a separate thread
    pipeline_thread_error = None
    pipeline_finished = threading.Event()
    partial_groups_result = []
    
    def run_pipeline():
        nonlocal partial_groups_result, pipeline_thread_error
        try:
            generator = process_and_group_generator(
                image_paths, 
                threshold=12, 
                token=token, 
                save_checkpoint_fn=save_checkpoint_fn, 
                logger=logger, 
                run_context=run_context
            )
            for processed, total, groups in generator:
                if groups is not None:
                    partial_groups_result = groups
        except Exception as e:
            pipeline_thread_error = e
        finally:
            pipeline_finished.set()

    print("Starting pipeline in background thread...")
    t_start = time.time()
    t = threading.Thread(target=run_pipeline)
    t.start()
    
    # Wait for pipeline to process some images (which will trigger at least one checkpoint)
    print("Waiting for pipeline to progress...")
    time.sleep(15.0)
    
    # Trigger cancellation
    print("Triggering cancellation...")
    t_cancel_trigger = time.time()
    token.cancel()
    
    # Wait for thread to exit
    t.join(timeout=5.0)
    t_end = time.time()
    
    halt_duration_ms = (t_end - t_cancel_trigger) * 1000
    print(f"Pipeline exited. Halt duration: {halt_duration_ms:.2f}ms")
    
    # Check errors
    if pipeline_thread_error:
        print(f"TEST FAILED: Pipeline crashed with error: {pipeline_thread_error}")
        sys.exit(1)
        
    # ASSERTION 1: Halts within 1,000ms
    assert halt_duration_ms < 1000.0, f"Halt duration exceeded 1,000ms limit: {halt_duration_ms:.2f}ms"
    print("[OK] Assertion 1 Passed: Threads halted in under 1,000ms.")
    
    # ASSERTION 2: Recovery checkpoint triggered
    assert len(checkpoint_calls) > 0, "No checkpoints were saved during the run"
    state = recovery.load_checkpoint()
    assert state is not None, "Saved recovery state file not found"
    assert state["processed_count"] > 0, "State file has empty processed count"
    assert len(state["processed_paths"]) == state["processed_count"], "State processed paths size mismatch"
    print("[OK] Assertion 2 Passed: Checkpoint was saved and contains correct state fields.")
    
    # Clean up checkpoint for next run
    recovery.clear_checkpoint()
    
    # ASSERTION 3: Telemetry and debug files exist in AppData and have events
    assert logger.debug_log_path.exists(), "debug.log was not created"
    assert logger.telemetry_path.exists(), "telemetry.jsonl was not created"
    
    # Verify telemetry logs contain events
    telemetry_events = []
    with open(logger.telemetry_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                telemetry_events.append(json.loads(line.strip()))
                
    event_names = [e["event"] for e in telemetry_events]
    print(f"Recorded telemetry events: {event_names}")
    
    assert "analysis_started" in event_names, "analysis_started event missing"
    assert "analysis_cancelled" in event_names, "analysis_cancelled event missing"
    print("[OK] Assertion 3 Passed: Telemetry populated successfully with started and cancelled events.")
    
    # Clean up test files
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    print("Test directory cleaned up.")
    print("=== ALL STRESS TESTS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    main()
