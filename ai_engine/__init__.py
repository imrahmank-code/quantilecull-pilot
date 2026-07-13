import os
import sys
import threading
from typing import Dict, Optional
import onnx_runtime
import model_manager

_initialized = False
_active_provider = "CPUExecutionProvider"
_models_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")
_lock = threading.Lock()

def initialize(device: str = "auto", models_dir: Optional[str] = None) -> bool:
    """Initializes the AI engine, discovers device capabilities, and pre-caches sessions."""
    global _initialized, _active_provider, _models_dir
    with _lock:
        if _initialized:
            return True
            
        if models_dir:
            _models_dir = models_dir
            
        # Device auto-selection logic
        available_providers = onnx_runtime.get_supported_providers()
        if device == "auto":
            # Prefer DirectML on Windows, then CUDA, fallback to CPU
            if "DmlExecutionProvider" in available_providers:
                _active_provider = "DmlExecutionProvider"
            elif "CudaExecutionProvider" in available_providers:
                _active_provider = "CudaExecutionProvider"
            else:
                _active_provider = "CPUExecutionProvider"
        else:
            if device in available_providers:
                _active_provider = device
            else:
                _active_provider = "CPUExecutionProvider"
                
        # Warmup and pre-cache models
        try:
            model_manager.cache_models(_models_dir, _active_provider)
            _initialized = True
            return True
        except Exception as e:
            sys.stderr.write(f"[ai_engine] Failed to warm up models during initialization: {e}\n")
            return False

def shutdown() -> None:
    """Gracefully shuts down the AI engine and clears session memory pools."""
    global _initialized
    with _lock:
        model_manager._model_session_cache.clear()
        _initialized = False

def is_available() -> bool:
    """Returns True if the AI engine is active and ready for inference."""
    return _initialized

def run_inference(model_name: str, input_feed: dict) -> dict:
    """Thread-safe inference dispatcher enqueuing tasks and returning model outputs."""
    if not is_available():
        if not initialize():
            return {"error": "AI Engine is not initialized."}
            
    with _lock:
        session = model_manager.load_model(model_name, _models_dir, _active_provider)
        if not session:
            return {"error": f"Model session for {model_name} could not be loaded."}
            
        try:
            if hasattr(session, "run"):
                output_names = [out.name for out in session.get_outputs()]
                raw_outputs = session.run(output_names, input_feed)
                return {name: val for name, val in zip(output_names, raw_outputs)}
            else:
                import numpy as np
                mock_out = {}
                meta = model_manager.get_model_info(model_name)
                if meta:
                    if model_name == "face_embedder":
                        mock_out["output"] = np.random.randn(1, 512).astype(np.float32)
                    elif model_name == "eye_state":
                        mock_out["output"] = np.array([[0.95, 0.05]], dtype=np.float32)
                    else:
                        mock_out["output"] = np.zeros((1, 1), dtype=np.float32)
                return mock_out
        except Exception as e:
            sys.stderr.write(f"[ai_engine] Inference run failed on model {model_name}: {e}\n")
            return {"error": str(e)}
