import unittest
import os
import sys

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)

import feature_registry

class TestFeatureRegistry(unittest.TestCase):
    def test_registered_features(self):
        info = feature_registry.get_feature_info("FACE_EMBEDDING")
        self.assertIsNotNone(info)
        self.assertEqual(info["required_model"], "face_embedder")
        self.assertEqual(info["dependencies"], ["FACE_DETECTION"])

    def test_execution_order_simple(self):
        # FACE_EMBEDDING requires FACE_DETECTION
        order = feature_registry.get_execution_order(["FACE_EMBEDDING"])
        self.assertEqual(order, ["FACE_DETECTION", "FACE_EMBEDDING"])

    def test_execution_order_multi(self):
        # STORY depends on SCENE and FACE_EMBEDDING. FACE_EMBEDDING depends on FACE_DETECTION.
        order = feature_registry.get_execution_order(["STORY"])
        
        # Verify prerequisites precede dependants
        self.assertLess(order.index("FACE_DETECTION"), order.index("FACE_EMBEDDING"))
        self.assertLess(order.index("SCENE"), order.index("STORY"))
        self.assertLess(order.index("FACE_EMBEDDING"), order.index("STORY"))

    def test_circular_dependency(self):
        # Temporarily register circular features
        feature_registry.register_feature("A", "model_a", ["B"], 1, 0.1)
        feature_registry.register_feature("B", "model_b", ["A"], 2, 0.1)
        
        with self.assertRaises(ValueError):
            feature_registry.get_execution_order(["A"])
            
        # Clean up by removing from dict
        del feature_registry._registry["A"]
        del feature_registry._registry["B"]

if __name__ == '__main__':
    unittest.main()
