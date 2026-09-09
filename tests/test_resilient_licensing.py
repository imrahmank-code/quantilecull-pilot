"""
Unit and integration tests for ResilientLicensingManager (Pillar 4).
Tests cryptographic token vaulting, machine fingerprint binding, 14-day rolling grace period,
tamper-resistant clock rollback verification, lifetime licenses, and heartbeat synchronization.
"""

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import shutil
import sys
import tempfile
from unittest.mock import patch

# Ensure repository root is on sys.path
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from resilient_licensing_manager import (
    ResilientLicensingManager,
    LicensingStatus,
    OfflineValidationResult,
    OfflineLicensePayload,
    DEFAULT_GRACE_PERIOD_DAYS
)
from licensing import get_machine_fingerprint, get_utc_now


class TestResilientLicensingManager(unittest.TestCase):
    """Test suite for ResilientLicensingManager."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="qc_lic_test_")
        self.vault_path = Path(self.temp_dir) / "test_vault.dat"
        self.heartbeat_path = Path(self.temp_dir) / "test_heartbeat.dat"
        self.db_path = Path(self.temp_dir) / "test_cache.db"

        self.manager = ResilientLicensingManager(
            vault_path=self.vault_path,
            heartbeat_path=self.heartbeat_path,
            db_path=self.db_path
        )
        self.fingerprint = get_machine_fingerprint()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_sample_payload(
        self,
        tier: str = "PRO",
        expiry_days: int = 30,
        grace_days: int = 14,
        fingerprint: str = None
    ) -> dict:
        now = get_utc_now()
        fp = fingerprint or self.fingerprint
        return {
            "license_key": "QC-PRO-TEST-1234-5678",
            "customer_email": "photographer@studio.com",
            "fingerprint": fp,
            "tier": tier,
            "activation_date": now.isoformat(),
            "expiry_date": (now + timedelta(days=expiry_days)).isoformat(),
            "grace_period_days": grace_days,
            "max_activations": 2
        }

    def test_derive_aes_key_deterministic(self):
        """Verify AES key derivation is consistent and 32 bytes (256 bits)."""
        key1 = self.manager.derive_aes_key("HW-FP-TEST-001")
        key2 = self.manager.derive_aes_key("HW-FP-TEST-001")
        key3 = self.manager.derive_aes_key("HW-FP-DIFFERENT")
        self.assertEqual(key1, key2)
        self.assertEqual(len(key1), 32)
        self.assertNotEqual(key1, key3)

    def test_sign_and_verify_payload_signature(self):
        """Verify HMAC-SHA256 signature generation and tamper verification."""
        payload = self._create_sample_payload()
        sig = self.manager.sign_payload(payload)
        self.assertTrue(isinstance(sig, str))
        self.assertEqual(len(sig), 64)

        payload["signature"] = sig
        self.assertTrue(self.manager.verify_signature(payload))

        # Tampering with any payload attribute invalidates signature
        tampered_payload = payload.copy()
        tampered_payload["tier"] = "ENTERPRISE"
        self.assertFalse(self.manager.verify_signature(tampered_payload))

        tampered_payload2 = payload.copy()
        tampered_payload2["signature"] = "0" * 64
        self.assertFalse(self.manager.verify_signature(tampered_payload2))

    def test_encrypt_decrypt_vault_payload(self):
        """Verify AES-256-CBC encryption and decryption of payload."""
        payload = self._create_sample_payload()
        encrypted_token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.assertTrue(isinstance(encrypted_token, str))

        decrypted = self.manager.decrypt_vault_payload(encrypted_token, self.fingerprint)
        self.assertEqual(decrypted["license_key"], payload["license_key"])
        self.assertEqual(decrypted["customer_email"], payload["customer_email"])
        self.assertEqual(decrypted["tier"], payload["tier"])
        self.assertTrue(self.manager.verify_signature(decrypted))

        # Decryption with mismatched fingerprint fails
        with self.assertRaises(ValueError):
            self.manager.decrypt_vault_payload(encrypted_token, "WRONG-HARDWARE-FP")

    def test_install_offline_license_success(self):
        """Verify successful offline license installation and persistence."""
        payload = self._create_sample_payload()
        encrypted_token = self.manager.encrypt_vault_payload(payload, self.fingerprint)

        success = self.manager.install_offline_license(encrypted_token)
        self.assertTrue(success)
        self.assertTrue(self.vault_path.exists())

        # Verify heartbeat file and DB state initialized
        self.assertTrue(self.heartbeat_path.exists())
        self.assertIsNotNone(self.manager._get_db_value("last_run_time"))
        self.assertIsNotNone(self.manager._get_db_value("last_heartbeat_utc"))

    def test_install_offline_license_fingerprint_mismatch(self):
        """Verify installation fails if hardware fingerprint does not match device."""
        payload = self._create_sample_payload(fingerprint="OTHER-DEVICE-UUID")
        encrypted_token = self.manager.encrypt_vault_payload(payload, "OTHER-DEVICE-UUID")

        # Manager decrypts with current device fingerprint, which fails
        success = self.manager.install_offline_license(encrypted_token)
        self.assertFalse(success)
        self.assertFalse(self.vault_path.exists())

    def test_unactivated_when_no_vault_exists(self):
        """Verify unactivated status when no license vault is present."""
        if self.vault_path.exists():
            self.vault_path.unlink()

        res = self.manager.validate_license()
        self.assertEqual(res.status, LicensingStatus.UNACTIVATED)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.days_remaining, 0)
        self.assertEqual(res.grace_days_remaining, 0)

    def test_owner_master_license_override(self):
        """Verify QC-OWNER-LIFETIME token unlocks permanent lifetime access."""
        with open(self.vault_path, "w", encoding="utf-8") as f:
            f.write("QC-OWNER-LIFETIME")

        res = self.manager.validate_license()
        self.assertEqual(res.status, LicensingStatus.ACTIVE)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.tier, "OWNER")
        self.assertEqual(res.days_remaining, 9999)

    def test_lifetime_token_tier(self):
        """Verify LIFETIME, VIP, and FOUNDER tiers never expire."""
        for tier in ["LIFETIME", "VIP", "FOUNDER"]:
            payload = self._create_sample_payload(tier=tier, expiry_days=-10)
            token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
            self.manager.install_offline_license(token)

            res = self.manager.validate_license()
            self.assertEqual(res.status, LicensingStatus.ACTIVE)
            self.assertTrue(res.is_valid)
            self.assertEqual(res.tier, tier)
            self.assertEqual(res.days_remaining, 9999)

    def test_active_license_recent_sync(self):
        """Verify active license status when recent heartbeat exists (< 1 hour)."""
        payload = self._create_sample_payload(tier="STUDIO", expiry_days=45)
        token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.manager.install_offline_license(token)

        res = self.manager.validate_license(simulate_offline=False)
        self.assertEqual(res.status, LicensingStatus.ACTIVE)
        self.assertTrue(res.is_valid)
        self.assertEqual(res.tier, "STUDIO")
        self.assertEqual(res.days_remaining, 45)
        self.assertFalse(res.offline_mode)

    def test_offline_grace_period_within_14_days(self):
        """Verify on-location culling within 14-day rolling grace period is valid."""
        payload = self._create_sample_payload(tier="PRO", expiry_days=60, grace_days=14)
        token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.manager.install_offline_license(token)

        # Simulate last heartbeat was 4 days ago
        four_days_ago = get_utc_now() - timedelta(days=4)
        self.manager._update_heartbeat(four_days_ago.isoformat())

        res = self.manager.validate_license()
        self.assertEqual(res.status, LicensingStatus.GRACE_PERIOD)
        self.assertTrue(res.is_valid)
        self.assertTrue(res.offline_mode)
        self.assertEqual(res.grace_days_remaining, 10)  # 14 - 4 = 10
        self.assertEqual(res.tier, "PRO")

    def test_offline_grace_period_exceeded(self):
        """Verify that offline duration exceeding 14 days marks license EXPIRED."""
        payload = self._create_sample_payload(tier="PRO", expiry_days=60, grace_days=14)
        token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.manager.install_offline_license(token)

        # Simulate last heartbeat was 16 days ago (> 14 days)
        sixteen_days_ago = get_utc_now() - timedelta(days=16)
        self.manager._update_heartbeat(sixteen_days_ago.isoformat())
        # Keep last_run_time consistent with the past to avoid clock rollback trigger
        self.manager._set_db_value("last_run_time", sixteen_days_ago.isoformat())

        res = self.manager.validate_license()
        self.assertEqual(res.status, LicensingStatus.EXPIRED)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.grace_days_remaining, 0)
        self.assertIn("grace period expired", res.message.lower())

    def test_calendar_expiry_date_elapsed(self):
        """Verify that license past its subscription expiry date is EXPIRED."""
        now = get_utc_now()
        payload = {
            "license_key": "QC-EXPIRED-TEST",
            "customer_email": "photographer@studio.com",
            "fingerprint": self.fingerprint,
            "tier": "STANDARD",
            "activation_date": (now - timedelta(days=60)).isoformat(),
            "expiry_date": (now - timedelta(days=2)).isoformat(),
            "grace_period_days": 14,
            "max_activations": 1
        }
        token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.manager.install_offline_license(token)

        res = self.manager.validate_license()
        self.assertEqual(res.status, LicensingStatus.EXPIRED)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.days_remaining, 0)

    def test_tamper_detection_clock_rollback(self):
        """Verify clock rollback beyond 24-hour tolerance triggers TAMPERED status."""
        payload = self._create_sample_payload(tier="PRO", expiry_days=30)
        token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.manager.install_offline_license(token)

        future_recorded = get_utc_now() + timedelta(days=5)
        self.manager._set_db_value("last_run_time", future_recorded.isoformat())

        res = self.manager.validate_license()
        self.assertEqual(res.status, LicensingStatus.TAMPERED)
        self.assertFalse(res.is_valid)
        self.assertIn("rollback", res.message.lower())

    def test_trigger_heartbeat_sync_resets_grace_period(self):
        """Verify heartbeat sync updates timestamp and resets the 14-day window."""
        payload = self._create_sample_payload(tier="PRO", expiry_days=30, grace_days=14)
        token = self.manager.encrypt_vault_payload(payload, self.fingerprint)
        self.manager.install_offline_license(token)

        # Set old heartbeat
        old_time = get_utc_now() - timedelta(days=10)
        self.manager._update_heartbeat(old_time.isoformat())

        res_before = self.manager.validate_license()
        self.assertEqual(res_before.status, LicensingStatus.GRACE_PERIOD)
        self.assertEqual(res_before.grace_days_remaining, 4)

        # Perform sync
        sync_ok = self.manager.trigger_heartbeat_sync()
        self.assertTrue(sync_ok)

        # Validation now sees fresh sync
        res_after = self.manager.validate_license()
        self.assertEqual(res_after.status, LicensingStatus.ACTIVE)
        self.assertEqual(res_after.grace_days_remaining, 14)

    def test_heartbeat_sync_revocation_override(self):
        """Verify remote REVOKED status halts sync renewal."""
        sync_result = self.manager.trigger_heartbeat_sync(remote_status_override="REVOKED")
        self.assertFalse(sync_result)


if __name__ == "__main__":
    unittest.main()
