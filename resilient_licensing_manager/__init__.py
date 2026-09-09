"""
ResilientLicensingManager - Pillar 4 of QuantileCull Next-Iteration Architecture
Enterprise on-location offline licensing vault with 14-day rolling grace period,
anti-tampering clock rollback verification, and background heartbeat synchronization.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Tuple, Any, List
import base64
import hashlib
import hmac
import json
import math
import os
import sqlite3
import sys
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

# Import core machine fingerprinting and base directory resolution
from licensing import (
    get_machine_fingerprint,
    get_utc_now,
    parse_iso_to_naive_utc,
    _BASE_DIR,
    SECRET_SALT,
    HMAC_SECRET,
    CACHE_DB_PATH
)

OFFLINE_VAULT_FILE = _BASE_DIR / "qc_resilient_vault.dat"
HEARTBEAT_STATE_FILE = _BASE_DIR / "qc_heartbeat.dat"
DEFAULT_GRACE_PERIOD_DAYS = 14


class LicensingStatus(str, Enum):
    """Authoritative lifecycle status of the workstation license."""
    ACTIVE = "active"              # Fully verified online or valid unexpired offline token
    GRACE_PERIOD = "grace_period"  # Offline on-location, operating within 14-day rolling window
    EXPIRED = "expired"            # Offline grace window or subscription validity elapsed
    TAMPERED = "tampered"          # System clock rollback or signature mutation detected
    UNACTIVATED = "unactivated"    # No valid license installed on device


@dataclass
class OfflineValidationResult:
    """Diagnostic and runtime evaluation of the license."""
    status: LicensingStatus
    is_valid: bool
    days_remaining: int
    grace_days_remaining: int
    message: str
    offline_mode: bool
    tier: str = "TRIAL"
    last_sync_utc: Optional[str] = None
    fingerprint: Optional[str] = None


@dataclass
class OfflineLicensePayload:
    """Unencrypted internal structure of the signed licensing token."""
    license_key: str
    customer_email: str
    fingerprint: str
    tier: str
    activation_date: str
    expiry_date: str
    grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
    max_activations: int = 2
    signature: Optional[str] = None


class ResilientLicensingManager:
    """
    On-location resilient licensing manager.
    Enables wedding photographers to operate completely offline for up to 14 days
    while enforcing cryptographic integrity and clock-tampering detection.
    """

    def __init__(
        self,
        vault_path: Optional[Path] = None,
        heartbeat_path: Optional[Path] = None,
        db_path: Optional[Path] = None
    ):
        self.vault_path: Path = vault_path or OFFLINE_VAULT_FILE
        self.heartbeat_path: Path = heartbeat_path or HEARTBEAT_STATE_FILE
        self.db_path: Path = db_path or CACHE_DB_PATH
        self.grace_period_days: int = DEFAULT_GRACE_PERIOD_DAYS
        self._last_monotonic: float = time.monotonic()
        self._init_db()

    def _init_db(self) -> None:
        """Ensures SQLite persistence table for resilient licensing state exists."""
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=10.0)
            with conn:
                conn.execute("""CREATE TABLE IF NOT EXISTS resilient_license_state (
                                key TEXT PRIMARY KEY,
                                value TEXT)""")
            conn.close()
        except Exception as e:
            print(f"[ResilientLicensing] Warning: Could not initialize DB state: {e}")

    def _get_db_value(self, key: str, default: Optional[str] = None) -> Optional[str]:
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM resilient_license_state WHERE key=?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else default
        except Exception:
            return default

    def _set_db_value(self, key: str, value: str) -> None:
        try:
            conn = sqlite3.connect(str(self.db_path), timeout=5.0)
            with conn:
                conn.execute("INSERT OR REPLACE INTO resilient_license_state (key, value) VALUES (?, ?)", (key, value))
            conn.close()
        except Exception as e:
            print(f"[ResilientLicensing] Warning: Could not write key {key}: {e}")

    # =========================================================================
    # Cryptographic Vault Operations
    # =========================================================================

    def derive_aes_key(self, fingerprint: str) -> bytes:
        """Derives a device-bound 256-bit AES encryption key."""
        h = hashlib.sha256()
        h.update(fingerprint.encode('utf-8'))
        h.update(SECRET_SALT)
        return h.digest()

    def sign_payload(self, payload: dict) -> str:
        """Generates an HMAC-SHA256 signature for payload verification."""
        payload_copy = payload.copy()
        payload_copy.pop("signature", None)
        serialized = json.dumps(payload_copy, sort_keys=True).encode('utf-8')
        return hmac.new(HMAC_SECRET, serialized, hashlib.sha256).hexdigest()

    def verify_signature(self, payload: dict) -> bool:
        """Verifies cryptographic signature integrity against HMAC secret."""
        if "signature" not in payload:
            return False
        expected = self.sign_payload(payload)
        return hmac.compare_digest(payload["signature"], expected)

    def encrypt_vault_payload(self, payload: dict, fingerprint: str) -> str:
        """Encrypts licensing payload with AES-256-CBC and PKCS7 padding."""
        key = self.derive_aes_key(fingerprint)
        payload["signature"] = self.sign_payload(payload)
        data = json.dumps(payload).encode('utf-8')

        padder = padding.PKCS7(128).padder()
        padded = padder.update(data) + padder.finalize()

        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()

        combined = iv + ciphertext
        return base64.b64encode(combined).decode('utf-8')

    def decrypt_vault_payload(self, encrypted_str: str, fingerprint: str) -> dict:
        """Decrypts and unpacks license payload for current hardware fingerprint."""
        try:
            key = self.derive_aes_key(fingerprint)
            combined = base64.b64decode(encrypted_str.encode('utf-8'))
            if len(combined) < 16:
                raise ValueError("Payload corrupted or truncated")

            iv = combined[:16]
            ciphertext = combined[16:]

            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()

            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded) + unpadder.finalize()
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            raise ValueError(f"Vault decryption failed: {str(e)}")

    def install_offline_license(self, encrypted_token: str) -> bool:
        """
        Installs an encrypted license token into the persistent offline vault.
        Validates cryptographic signature and hardware fingerprint before commit.
        """
        try:
            fp = get_machine_fingerprint()
            payload = self.decrypt_vault_payload(encrypted_token, fp)

            if not self.verify_signature(payload):
                print("[ResilientLicensing] Signature verification failed.")
                return False

            if payload.get("fingerprint") != fp:
                print("[ResilientLicensing] Hardware fingerprint mismatch.")
                return False

            self.vault_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.vault_path, "w", encoding="utf-8") as f:
                f.write(encrypted_token)

            # Initialize last verified heartbeat timestamp
            now_iso = get_utc_now().isoformat()
            self._update_heartbeat(now_iso)
            self._set_db_value("last_run_time", now_iso)
            return True
        except Exception as e:
            print(f"[ResilientLicensing] Install failed: {e}")
            return False

    # =========================================================================
    # Tamper-Resistant Clock Rollback Verification
    # =========================================================================

    def _check_clock_tampering(self, current_utc: datetime) -> bool:
        """
        Validates forward time progression against database records and filesystem mtimes.
        Allows up to 24 hours tolerance for NTP/DST shifts, but flags explicit backward rollback.
        """
        last_run_str = self._get_db_value("last_run_time")
        heartbeat_str = self._get_last_heartbeat()

        recorded_times: List[datetime] = []
        for s in [last_run_str, heartbeat_str]:
            if s:
                try:
                    recorded_times.append(parse_iso_to_naive_utc(s))
                except Exception:
                    pass

        # Check filesystem anchor mtimes
        if self.vault_path.exists():
            recorded_times.append(datetime.fromtimestamp(os.path.getmtime(self.vault_path), tz=timezone.utc).replace(tzinfo=None))

        if recorded_times:
            max_past_time = max(recorded_times)
            # If current UTC is earlier than last recorded timestamp by > 24 hours -> rollback detected
            if current_utc < max_past_time - timedelta(hours=24):
                return True

        return False

    def _get_last_heartbeat(self) -> Optional[str]:
        """Retrieves last recorded heartbeat from DB or file fallback."""
        val = self._get_db_value("last_heartbeat_utc")
        if not val and self.heartbeat_path.exists():
            try:
                with open(self.heartbeat_path, "r", encoding="utf-8") as f:
                    val = f.read().strip()
            except Exception:
                pass
        return val

    def _update_heartbeat(self, iso_str: str) -> None:
        """Records a successful online or local heartbeat sync."""
        self._set_db_value("last_heartbeat_utc", iso_str)
        try:
            self.heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.heartbeat_path, "w", encoding="utf-8") as f:
                f.write(iso_str)
        except Exception:
            pass

    # =========================================================================
    # Validation & Grace Period Evaluation
    # =========================================================================

    def validate_license(self, simulate_offline: bool = False) -> OfflineValidationResult:
        """
        Comprehensive offline-resilient license validation.
        Evaluates cryptographic token, clock tampering, and 14-day rolling grace period.
        """
        fp = get_machine_fingerprint()
        now = get_utc_now()

        # Check for Owner master license override
        if self.vault_path.exists():
            try:
                with open(self.vault_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                if content == "QC-OWNER-LIFETIME":
                    return OfflineValidationResult(
                        status=LicensingStatus.ACTIVE,
                        is_valid=True,
                        days_remaining=9999,
                        grace_days_remaining=self.grace_period_days,
                        message="Owner License: Unlimited Lifetime",
                        offline_mode=False,
                        tier="OWNER",
                        fingerprint=fp
                    )
            except Exception:
                pass

        if not self.vault_path.exists():
            return OfflineValidationResult(
                status=LicensingStatus.UNACTIVATED,
                is_valid=False,
                days_remaining=0,
                grace_days_remaining=0,
                message="No license installed on device",
                offline_mode=simulate_offline,
                tier="UNACTIVATED",
                fingerprint=fp
            )

        # 1. Decrypt and verify signature
        try:
            with open(self.vault_path, "r", encoding="utf-8") as f:
                encrypted_str = f.read().strip()
            payload = self.decrypt_vault_payload(encrypted_str, fp)

            if not self.verify_signature(payload) or payload.get("fingerprint") != fp:
                return OfflineValidationResult(
                    status=LicensingStatus.UNACTIVATED,
                    is_valid=False,
                    days_remaining=0,
                    grace_days_remaining=0,
                    message="License cryptographic signature or device mismatch",
                    offline_mode=simulate_offline,
                    fingerprint=fp
                )
        except Exception as err:
            return OfflineValidationResult(
                status=LicensingStatus.UNACTIVATED,
                is_valid=False,
                days_remaining=0,
                grace_days_remaining=0,
                message=f"Vault decryption error: {err}",
                offline_mode=simulate_offline,
                fingerprint=fp
            )

        # 2. Clock Rollback Check
        if self._check_clock_tampering(now):
            return OfflineValidationResult(
                status=LicensingStatus.TAMPERED,
                is_valid=False,
                days_remaining=0,
                grace_days_remaining=0,
                message="System clock rollback detected. Re-synchronize network time to proceed.",
                offline_mode=simulate_offline,
                fingerprint=fp
            )

        # Update last run time forward
        self._set_db_value("last_run_time", now.isoformat())

        # 3. Lifetime Licenses (Never Expire)
        tier = payload.get("tier", "TRIAL").upper()
        if tier in ["LIFETIME", "VIP", "FOUNDER"]:
            return OfflineValidationResult(
                status=LicensingStatus.ACTIVE,
                is_valid=True,
                days_remaining=9999,
                grace_days_remaining=self.grace_period_days,
                message=f"Permanent {tier} License: Active",
                offline_mode=simulate_offline,
                tier=tier,
                last_sync_utc=self._get_last_heartbeat(),
                fingerprint=fp
            )

        # 4. Standard / Trial Licenses (Calculate Expiry & Grace Period)
        expiry_dt = parse_iso_to_naive_utc(payload.get("expiry_date", now.isoformat()))
        grace_days_config = payload.get("grace_period_days", self.grace_period_days)

        # Heartbeat check for on-location offline culling
        last_hb_str = self._get_last_heartbeat()
        last_hb_dt = parse_iso_to_naive_utc(last_hb_str) if last_hb_str else now

        offline_duration = (now - last_hb_dt).total_seconds()
        grace_window_seconds = grace_days_config * 86400.0

        if now <= expiry_dt:
            days_left = max(0, math.ceil((expiry_dt - now).total_seconds() / 86400.0))
            # License is within valid calendar window
            if simulate_offline or offline_duration > 3600:
                if offline_duration > grace_window_seconds:
                    return OfflineValidationResult(
                        status=LicensingStatus.EXPIRED,
                        is_valid=False,
                        days_remaining=days_left,
                        grace_days_remaining=0,
                        message="Offline grace period expired. Connect to internet to refresh license.",
                        offline_mode=True,
                        tier=tier,
                        last_sync_utc=last_hb_str,
                        fingerprint=fp
                    )
                grace_left = max(0, math.ceil((grace_window_seconds - offline_duration) / 86400.0))
                return OfflineValidationResult(
                    status=LicensingStatus.GRACE_PERIOD,
                    is_valid=True,
                    days_remaining=days_left,
                    grace_days_remaining=grace_left,
                    message=f"On-Location Offline Mode: {days_left} Days Remaining ({grace_left}d grace left)",
                    offline_mode=True,
                    tier=tier,
                    last_sync_utc=last_hb_str,
                    fingerprint=fp
                )
            else:
                return OfflineValidationResult(
                    status=LicensingStatus.ACTIVE,
                    is_valid=True,
                    days_remaining=days_left,
                    grace_days_remaining=grace_days_config,
                    message=f"License Active: {days_left} Days Remaining",
                    offline_mode=False,
                    tier=tier,
                    last_sync_utc=last_hb_str,
                    fingerprint=fp
                )
        else:
            # License expired past expiry_dt
            return OfflineValidationResult(
                status=LicensingStatus.EXPIRED,
                is_valid=False,
                days_remaining=0,
                grace_days_remaining=0,
                message="License expired. Please renew to continue culling.",
                offline_mode=simulate_offline,
                tier=tier,
                last_sync_utc=last_hb_str,
                fingerprint=fp
            )

    def trigger_heartbeat_sync(self, remote_status_override: Optional[str] = None) -> bool:
        """
        Executes a heartbeat sync to extend the 14-day rolling window.
        Can be wired to remote Supabase/Paddle heartbeat endpoint when network is present.
        """
        try:
            if remote_status_override == "REVOKED":
                return False

            now_iso = get_utc_now().isoformat()
            self._update_heartbeat(now_iso)
            return True
        except Exception:
            return False
