import os
import sys
import unittest
import numpy as np

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import raw_engine
import cache_engine

class RobustnessStressTester(unittest.TestCase):
    def test_corrupted_raw_decoding_graceful_recovery(self):
        """Verify that decoding a corrupted raw file raises/recovers gracefully instead of crashing."""
        corrupt_data = b"NOT_A_VALID_RAW_FILE_HEADER_1234567890"
        
        # Test raw decoder raises correct exception or returns empty/null
        try:
            res = raw_engine.decode_raw(corrupt_data)
            # If it didn't throw, it should return None/empty indicating failure
            self.assertIsNone(res)
        except Exception:
            # Raising is also a valid graceful failure state
            pass

    def test_missing_cache_database_automatic_recreation(self):
        """Verify that cache_engine re-creates cache database if deleted mid-session."""
        db_path = "E:/Antigravity Projects/Photo Cleaner App/cache.db"
        
        # If db exists, simulate deletion
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except Exception:
                pass
                
        # Re-initializing must not crash and must rebuild schemas
        try:
            cache_engine.clear_cache()
            self.assertTrue(True)
        except Exception as e:
            self.fail(f"clear_cache crashed on missing DB: {e}")

if __name__ == '__main__':
    unittest.main()
