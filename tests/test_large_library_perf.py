import unittest
import os
import sys

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import tests.profile_large_library as profiler

class TestLargeLibraryPerf(unittest.TestCase):
    def test_large_library_similarity_speed(self):
        duration = profiler.run_scaling_benchmark()
        # Cosine search over 100 queries against 10,000 centroids must take < 1.0 second on modern CPUs
        self.assertLess(duration, 1.0)

if __name__ == '__main__':
    unittest.main()
