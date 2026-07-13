import os
import sys
from typing import List, Optional

try:
    import onnxruntime as ort
    HAS_ORT = True
except ImportError:
    HAS_ORT = False

def get_supported_providers() -> List[str]:
    """Returns a list of supported ONNX Runtime execution providers."""
    if not HAS_ORT:
        return ["CPUExecutionProvider"]
    try:
        return ort.get_available_providers()
    except Exception:
        return ["CPUExecutionProvider"]

def create_inference_session(model_path: str, provider: Optional[str] = None) -> Optional[object]:
    """Creates a new ONNX Runtime inference session on the designated provider."""
    if not HAS_ORT:
        sys.stderr.write("[onnx_runtime] ONNX Runtime is not installed/loaded.\n")
        return None
        
    if not os.path.exists(model_path):
        sys.stderr.write(f"[onnx_runtime] Model file not found: {model_path}\n")
        return None

    # Fallback/default logic for provider selection
    available = get_supported_providers()
    if provider is None or provider not in available:
        provider = "CPUExecutionProvider"
        
    try:
        sess_opt = ort.SessionOptions()
        sess_opt.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        
        session = ort.InferenceSession(
            model_path,
            sess_options=sess_opt,
            providers=[provider]
        )
        return session
    except Exception as e:
        sys.stderr.write(f"[onnx_runtime] Failed to create session for {model_path}: {e}\n")
        # Try falling back to CPU if DirectML/CUDA failed
        if provider != "CPUExecutionProvider":
            try:
                sys.stderr.write("[onnx_runtime] Retrying session creation with CPUExecutionProvider fallback...\n")
                return ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
            except Exception as ex:
                sys.stderr.write(f"[onnx_runtime] Fallback CPU session creation failed: {ex}\n")
        return None
