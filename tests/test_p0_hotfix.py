import os
import sys
import json
import shutil
import unittest
import tempfile
import datetime
from pathlib import Path

# Setup workspace path
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_DIR))

import licensing

class TestP0HotfixRegressions(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests to isolate database and files
        self.test_dir = Path(tempfile.mkdtemp(prefix="qc_p0_hotfix_"))
        
        # Override paths in licensing module
        self.original_license_path = licensing.LICENSE_FILE_PATH
        self.original_state_path = licensing.STATE_FILE_PATH
        self.original_db_path = licensing.CACHE_DB_PATH
        
        licensing.LICENSE_FILE_PATH = self.test_dir / "qc_license.dat"
        licensing.STATE_FILE_PATH = self.test_dir / "qc_state.dat"
        licensing.CACHE_DB_PATH = self.test_dir / ".quantilecull_cache.db"
        
        self.lm = licensing.LicenseManager()

    def tearDown(self):
        # Clean up temporary directory
        shutil.rmtree(self.test_dir, ignore_errors=True)
        
        # Restore original paths
        licensing.LICENSE_FILE_PATH = self.original_license_path
        licensing.STATE_FILE_PATH = self.original_state_path
        licensing.CACHE_DB_PATH = self.original_db_path

    def test_fresh_install_launch(self):
        # Ensure that on a fresh install (no database, no license file, no state file),
        # validation returns unactivated, NOT tampered.
        self.assertFalse(licensing.LICENSE_FILE_PATH.exists())
        self.assertFalse(licensing.STATE_FILE_PATH.exists())
        
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "unactivated")
        self.assertNotEqual(status["status"], "tampered")

    def test_minor_clock_drift_allowed(self):
        # Under V1.2.1, clock shifts of less than 24 hours should NOT trigger rollback.
        fingerprint = licensing.get_machine_fingerprint()
        now = licensing.get_utc_now()
        expiry = now + datetime.timedelta(days=30)
        
        payload = {
            "fingerprint": fingerprint,
            "activation_date": now.isoformat(),
            "expiry_date": expiry.isoformat(),
            "license_type": "trial"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        self.assertTrue(self.lm.install_license(encrypted))
        
        # First verification sets the last run to now (UTC)
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "active")
        
        # Simulate a clock drift backward of 23 hours
        drifted_last_run = now + datetime.timedelta(hours=23)
        self.lm._update_last_run_time(drifted_last_run)
        
        # Validation should STILL be active since 23 hours is within the 24-hour threshold
        status2 = self.lm.validate_license()
        self.assertEqual(status2["status"], "active")

    def test_major_clock_rollback_blocked(self):
        # Shifting clock back by >24 hours MUST trigger rollback block
        fingerprint = licensing.get_machine_fingerprint()
        now = licensing.get_utc_now()
        expiry = now + datetime.timedelta(days=30)
        
        payload = {
            "fingerprint": fingerprint,
            "activation_date": now.isoformat(),
            "expiry_date": expiry.isoformat(),
            "license_type": "trial"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        self.assertTrue(self.lm.install_license(encrypted))
        
        # Set last run
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "active")
        
        # Simulate a major rollback (e.g. clock shifted back by 2 days)
        future_last_run = now + datetime.timedelta(days=2)
        self.lm._update_last_run_time(future_last_run)
        
        # Validation should trigger tampered (rollback block)
        status2 = self.lm.validate_license()
        self.assertEqual(status2["status"], "tampered")
        self.assertEqual(status2["message"], "License Verification Failed")
        self.assertTrue("current_time" in status2)
        self.assertTrue("last_run_time" in status2)

    def test_corrupted_license_not_tampered(self):
        # A corrupted, invalid, or mismatched license should return unactivated/invalid status,
        # NOT the tampered/rollback state.
        
        # 1. Write garbage to license file
        with open(licensing.LICENSE_FILE_PATH, "w") as f:
            f.write("GARBAGE_PAYLOAD_DATA_THAT_CANNOT_BE_DECRYPTED")
            
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "unactivated")
        self.assertNotEqual(status["status"], "tampered")
        
        # 2. Write valid license of a different machine fingerprint
        different_fp = "mismatching_fingerprint_hash_abc123"
        payload = {
            "fingerprint": different_fp,
            "activation_date": licensing.get_utc_now().isoformat(),
            "expiry_date": (licensing.get_utc_now() + datetime.timedelta(days=30)).isoformat(),
            "license_type": "trial"
        }
        # Encrypting with different fingerprint
        encrypted = self.lm.encrypt_license(payload, different_fp)
        
        # Directly write to license path
        with open(licensing.LICENSE_FILE_PATH, "w") as f:
            f.write(encrypted)
            
        # Validation should fail decryption (fingerprint mismatch) and return unactivated
        status2 = self.lm.validate_license()
        self.assertEqual(status2["status"], "unactivated")
        self.assertNotEqual(status2["status"], "tampered")

if __name__ == "__main__":
    unittest.main()
