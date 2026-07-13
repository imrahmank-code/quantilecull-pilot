import unittest
import os
import sys
from unittest.mock import patch, MagicMock

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(workspace_dir)

import ai_engine

class TestAiEngine(unittest.TestCase):
    def setUp(self):
        ai_engine.shutdown()

    def tearDown(self):
        ai_engine.shutdown()

    def test_initialization_auto(self):
        success = ai_engine.initialize(device="auto")
        self.assertTrue(success)
        self.assertTrue(ai_engine.is_available())

    def test_initialization_specific(self):
        # Force a provider not in available providers -> should fallback to CPU
        success = ai_engine.initialize(device="NonexistentProvider")
        self.assertTrue(success)
        self.assertEqual(ai_engine._active_provider, "CPUExecutionProvider")

    def test_shutdown(self):
        ai_engine.initialize()
        self.assertTrue(ai_engine.is_available())
        ai_engine.shutdown()
        self.assertFalse(ai_engine.is_available())

    @patch('model_manager.load_model', return_value="mock_session_obj")
    def test_run_inference_mock(self, mock_load):
        ai_engine.initialize()
        # Test mock inference for eye_state
        out = ai_engine.run_inference("eye_state", {"input": None})
        self.assertIn("output", out)
        self.assertEqual(out["output"].shape, (1, 2))

if __name__ == '__main__':
    unittest.main()
