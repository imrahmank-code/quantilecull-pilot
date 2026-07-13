import unittest
import os
import sys

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import blink_recovery

class TestEyeStateEngine(unittest.TestCase):
    def test_classify_closed(self):
        state = blink_recovery.classify_eye_state(10.0, 12.0)
        self.assertEqual(state, "Closed")

    def test_classify_wink(self):
        state = blink_recovery.classify_eye_state(85.0, 15.0)
        self.assertEqual(state, "Wink")

    def test_classify_squint(self):
        state = blink_recovery.classify_eye_state(30.0, 35.0)
        self.assertEqual(state, "Squint")

    def test_classify_fully_open(self):
        state = blink_recovery.classify_eye_state(88.0, 92.0)
        self.assertEqual(state, "Fully open")

if __name__ == '__main__':
    unittest.main()
