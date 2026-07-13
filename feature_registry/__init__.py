from typing import Dict, List, Optional

_registry = {}

def register_feature(name: str, required_model: str, dependencies: List[str], priority: int, est_runtime: float) -> None:
    """Registers a new AI vision capability and its dependencies."""
    _registry[name] = {
        "name": name,
        "required_model": required_model,
        "dependencies": dependencies,
        "priority": priority,
        "estimated_runtime": est_runtime
    }

def get_feature_info(name: str) -> Optional[dict]:
    """Retrieves metadata definition for a registered feature name."""
    return _registry.get(name)

def get_execution_order(enabled_features: List[str]) -> List[str]:
    """Resolves topological dependencies and returns execution order sorted by priority."""
    visited = {}
    order = []
    
    def visit(node):
        if visited.get(node) == "temp":
            raise ValueError(f"Circular dependency detected in feature registry at: {node}")
        if visited.get(node) == "perm":
            return
            
        visited[node] = "temp"
        info = get_feature_info(node)
        if info:
            for dep in info.get("dependencies", []):
                visit(dep)
                
        visited[node] = "perm"
        order.append(node)

    for f in enabled_features:
        if f in _registry:
            visit(f)
            
    return order

# Initialize standard Feature Pack 2 registry definitions
register_feature("FACE_DETECTION", "face_detector", [], 1, 0.05)
register_feature("FACE_EMBEDDING", "face_embedder", ["FACE_DETECTION"], 2, 0.15)
register_feature("EYE_STATE", "eye_state", ["FACE_DETECTION"], 3, 0.08)
register_feature("SMILE", "smile_classifier", ["FACE_DETECTION"], 4, 0.06)
register_feature("SUBJECT", "subject_detector", [], 5, 0.12)
register_feature("BODY", "body_detector", [], 6, 0.10)
register_feature("SCENE", "scene_classifier", [], 7, 0.08)
register_feature("STORY", "storytelling_analyzer", ["SCENE", "FACE_EMBEDDING"], 8, 0.20)
register_feature("QUALITY", "quality_estimator", [], 0, 0.02)
