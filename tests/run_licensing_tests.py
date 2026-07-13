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

class TestLicensing(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory for tests to isolate database and files
        self.test_dir = Path(tempfile.mkdtemp(prefix="qc_license_test_"))
        
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

    def test_fingerprint_stability(self):
        fp1 = licensing.get_machine_fingerprint()
        fp2 = licensing.get_machine_fingerprint()
        self.assertEqual(fp1, fp2)
        self.assertTrue(len(fp1) == 64)  # SHA-256 hex digest length

    def test_encryption_decryption(self):
        fingerprint = "test_fingerprint_12345"
        payload = {
            "fingerprint": fingerprint,
            "license_type": "trial",
            "activation_date": "2026-06-25T00:00:00",
            "expiry_date": "2026-07-25T00:00:00"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        decrypted = self.lm.decrypt_license(encrypted, fingerprint)
        
        self.assertEqual(payload["fingerprint"], decrypted["fingerprint"])
        self.assertEqual(payload["license_type"], decrypted["license_type"])
        self.assertEqual(payload["activation_date"], decrypted["activation_date"])
        self.assertEqual(payload["expiry_date"], decrypted["expiry_date"])
        
        # Verify signature was generated and verified
        self.assertTrue(self.lm.verify_signature(decrypted))

    def test_encryption_invalid_fingerprint(self):
        fp_owner = "owner_fingerprint"
        fp_attacker = "attacker_fingerprint"
        payload = {"fingerprint": fp_owner, "test": "data"}
        
        encrypted = self.lm.encrypt_license(payload, fp_owner)
        
        # Trying to decrypt with a different fingerprint should raise error or yield garbled data
        with self.assertRaises(ValueError):
            self.lm.decrypt_license(encrypted, fp_attacker)

    def test_license_signature_tampering(self):
        fingerprint = licensing.get_machine_fingerprint()
        payload = {
            "fingerprint": fingerprint,
            "activation_date": "2026-06-25T00:00:00",
            "expiry_date": "2026-07-25T00:00:00"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        decrypted = self.lm.decrypt_license(encrypted, fingerprint)
        
        # Modify expiry date manually on the decrypted dictionary
        decrypted["expiry_date"] = "2029-07-25T00:00:00"
        
        # Verification should fail because HMAC doesn't match
        self.assertFalse(self.lm.verify_signature(decrypted))

    def test_license_install_and_validate_active(self):
        fingerprint = licensing.get_machine_fingerprint()
        now = datetime.datetime.now()
        expiry = now + datetime.timedelta(days=15) # 15 days left
        
        payload = {
            "fingerprint": fingerprint,
            "activation_date": now.isoformat(),
            "expiry_date": expiry.isoformat(),
            "license_type": "trial"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        
        self.assertTrue(self.lm.install_license(encrypted))
        
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "active")
        self.assertEqual(status["days_remaining"], 14) # rounds down to 14 full remaining days in .days

    def test_license_validate_expired(self):
        fingerprint = licensing.get_machine_fingerprint()
        now = datetime.datetime.now()
        activation = now - datetime.timedelta(days=40)
        expiry = now - datetime.timedelta(days=10) # expired 10 days ago
        
        payload = {
            "fingerprint": fingerprint,
            "activation_date": activation.isoformat(),
            "expiry_date": expiry.isoformat(),
            "license_type": "trial"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        self.assertTrue(self.lm.install_license(encrypted))
        
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "expired")
        self.assertEqual(status["days_remaining"], 0)

    def test_clock_rollback_detection(self):
        fingerprint = licensing.get_machine_fingerprint()
        now = datetime.datetime.now()
        expiry = now + datetime.timedelta(days=30)
        
        payload = {
            "fingerprint": fingerprint,
            "activation_date": now.isoformat(),
            "expiry_date": expiry.isoformat(),
            "license_type": "trial"
        }
        
        encrypted = self.lm.encrypt_license(payload, fingerprint)
        self.assertTrue(self.lm.install_license(encrypted))
        
        # First check, updates last_run_time to now
        status = self.lm.validate_license()
        self.assertEqual(status["status"], "active")
        
        # Simulate clock rollback of 2 days by forcing a future time in the state db/file, 
        # then querying.
        future_time = now + datetime.timedelta(days=2)
        self.lm._update_last_run_time(future_time)
        
        # Validation should now fail as system time is rolled back compared to future_time
        status2 = self.lm.validate_license()
        self.assertEqual(status2["status"], "tampered")

if __name__ == "__main__":
    unittest.main()
