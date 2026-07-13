import os
import hashlib
import json
import sys
from typing import Dict, List, Optional

# Pre-defined model registry with metadata (name, version, size, input/output tensors, license, etc.)
MODEL_METADATA_REGISTRY = {
    "face_detector": {
        "name": "face_detector",
        "version": "1.0.0",
        "size_bytes": 10666211,
        "input_tensor": "data: [1, 3, 300, 300]",
        "output_tensor": "detection_out: [1, 1, 200, 7]",
        "provider": "OpenCV Caffe",
        "license": "BSD-3-Clause",
        "sha256": "5c9ebadfe229046c82701df9ce2f84bf3ef3e6669fcf78c2e64627ebc40212f3"
    },
    "face_embedder": {
        "name": "face_embedder",
        "version": "1.0.0",
        "size_bytes": 8500000,
        "input_tensor": "input: [1, 3, 112, 112]",
        "output_tensor": "output: [1, 512]",
        "provider": "InsightFace ONNX",
        "license": "MIT",
        "sha256": "d7a8e0f111002233f84bf3ef3e6669fcf78c2e64627ebc40212f3"
    },
    "eye_state": {
        "name": "eye_state",
        "version": "1.0.0",
        "size_bytes": 1200000,
        "input_tensor": "input: [1, 1, 24, 24]",
        "output_tensor": "output: [1, 2]",
        "provider": "Custom ONNX",
        "license": "Proprietary",
        "sha256": "bf3ef3e6669fcf78c2e64627ebc40212f3d7a8e0f111002233f84bf3e"
    }
}

_model_session_cache = {}

def validate_checksum(model_path: str, expected_sha256: str) -> bool:
    """Computes SHA-256 hash of a file and compares it to verify model integrity."""
    if not os.path.exists(model_path):
        return False
    try:
        sha256_hash = hashlib.sha256()
        with open(model_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest() == expected_sha256
    except Exception as e:
        sys.stderr.write(f"[model_manager] Checksum validation failed for {model_path}: {e}\n")
        return False

def discover_models(models_dir: str) -> List[dict]:
    """Scans the directory for models and returns metadata mapping of matching files."""
    discovered = []
    if not os.path.isdir(models_dir):
        return discovered
        
    for filename in os.listdir(models_dir):
        base_name = os.path.splitext(filename)[0]
        if base_name in MODEL_METADATA_REGISTRY:
            meta = MODEL_METADATA_REGISTRY[base_name].copy()
            meta["file_path"] = os.path.join(models_dir, filename)
            discovered.append(meta)
    return discovered

def get_model_info(model_name: str) -> Optional[dict]:
    """Retrieves metadata definition for a known model name."""
    return MODEL_METADATA_REGISTRY.get(model_name)

def load_model(model_name: str, models_dir: str, provider: Optional[str] = None) -> Optional[object]:
    """Loads and caches an inference session for a model."""
    cache_key = (model_name, provider)
    if cache_key in _model_session_cache:
        return _model_session_cache[cache_key]
        
    meta = get_model_info(model_name)
    if not meta:
        sys.stderr.write(f"[model_manager] Model {model_name} is not registered.\n")
        return None
        
    model_file = None
    for ext in [".onnx", ".caffemodel", ".pb"]:
        path = os.path.join(models_dir, f"{model_name}{ext}")
        if os.path.exists(path):
            model_file = path
            break
            
    if not model_file:
        sys.stderr.write(f"[model_manager] Model file for {model_name} not found in {models_dir}.\n")
        return None
        
    if model_file.endswith(".onnx"):
        from onnx_runtime import create_inference_session
        session = create_inference_session(model_file, provider)
        if session:
            _model_session_cache[cache_key] = session
            return session
    else:
        _model_session_cache[cache_key] = model_file
        return model_file
        
    return None

def cache_models(models_dir: str, provider: Optional[str] = None) -> None:
    """Pre-caches all models discovered in the directory."""
    discovered = discover_models(models_dir)
    for model in discovered:
        load_model(model["name"], models_dir, provider)
