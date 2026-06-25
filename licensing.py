import os
import sys
import json
import base64
import hashlib
import hmac
import datetime
import sqlite3
import subprocess
from pathlib import Path
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding

# Resolve base directory path matching existing engine configuration
if sys.platform == "win32":
    _BASE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "QuantileCull"
else:
    _BASE_DIR = Path.home() / ".local/share/QuantileCull"

LICENSE_FILE_PATH = _BASE_DIR / "qc_license.dat"
STATE_FILE_PATH = _BASE_DIR / "qc_state.dat"
CACHE_DB_PATH = _BASE_DIR / ".quantilecull_cache.db"

SECRET_SALT = b"QuantileCull_Secure_License_Key_Salt_2026_#"
HMAC_SECRET = b"QuantileCull_HMAC_Secret_2026_$"

def get_machine_fingerprint():
    guid = ""
    bios_uuid = ""
    cpu_id = ""
    
    # 1. Get MachineGuid (Windows registry)
    if sys.platform == "win32":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography")
            guid, _ = winreg.QueryValueEx(key, "MachineGuid")
            winreg.CloseKey(key)
        except Exception:
            pass
            
    # 2. Get BIOS UUID (PowerShell / system profiler)
    try:
        if sys.platform == "win32":
            bios_uuid = subprocess.check_output(
                "powershell -Command \"(Get-CimInstance Win32_ComputerSystemProduct).UUID\"", 
                shell=True, stderr=subprocess.DEVNULL
            ).decode().strip()
        else:
            bios_uuid = subprocess.check_output(
                "ioreg -rd1 -c IOPlatformExpertDevice | grep -i UUID", 
                shell=True, stderr=subprocess.DEVNULL
            ).decode().strip()
    except Exception:
        pass
        
    # 3. Get CPU ID
    try:
        if sys.platform == "win32":
            cpu_id = subprocess.check_output(
                "powershell -Command \"(Get-CimInstance Win32_Processor).ProcessorId\"", 
                shell=True, stderr=subprocess.DEVNULL
            ).decode().strip()
    except Exception:
        pass

    # Fallback to MAC address + hostname if hardware UUID query fails
    if not (guid or bios_uuid or cpu_id):
        import uuid
        import socket
        guid = str(uuid.getnode())
        bios_uuid = socket.gethostname()
        
    raw_str = f"{guid}:{bios_uuid}:{cpu_id}"
    return hashlib.sha256(raw_str.encode('utf-8')).hexdigest()

class LicenseManager:
    def __init__(self):
        self._BASE_DIR = _BASE_DIR
        _BASE_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        try:
            conn = sqlite3.connect(str(CACHE_DB_PATH))
            with conn:
                conn.execute('''CREATE TABLE IF NOT EXISTS license_state (
                                key TEXT PRIMARY KEY,
                                value TEXT)''')
            conn.close()
        except Exception as e:
            print(f"[Licensing] Failed to initialize database: {e}")

    def _get_db_value(self, key, default=None):
        try:
            conn = sqlite3.connect(str(CACHE_DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM license_state WHERE key=?", (key,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else default
        except Exception:
            return default

    def _set_db_value(self, key, value):
        try:
            conn = sqlite3.connect(str(CACHE_DB_PATH))
            with conn:
                conn.execute("INSERT OR REPLACE INTO license_state (key, value) VALUES (?, ?)", (key, value))
            conn.close()
        except Exception as e:
            print(f"[Licensing] Failed to save {key} in DB: {e}")

    def _get_last_run_time(self):
        # Fetch from DB and check file fallback
        db_time_str = self._get_db_value("last_run_time")
        file_time_str = None
        if STATE_FILE_PATH.exists():
            try:
                with open(STATE_FILE_PATH, "r") as f:
                    file_time_str = f.read().strip()
            except Exception:
                pass
        
        # Compare and return maximum or fallback
        times = []
        for t_str in (db_time_str, file_time_str):
            if t_str:
                try:
                    times.append(datetime.datetime.fromisoformat(t_str))
                except ValueError:
                    pass
        return max(times) if times else None

    def _update_last_run_time(self, dt):
        dt_str = dt.isoformat()
        self._set_db_value("last_run_time", dt_str)
        try:
            with open(STATE_FILE_PATH, "w") as f:
                f.write(dt_str)
        except Exception:
            pass

    def derive_aes_key(self, fingerprint: str) -> bytes:
        h = hashlib.sha256()
        h.update(fingerprint.encode('utf-8'))
        h.update(SECRET_SALT)
        return h.digest()

    def sign_payload(self, payload: dict) -> str:
        payload_copy = payload.copy()
        payload_copy.pop("signature", None)
        serialized = json.dumps(payload_copy, sort_keys=True).encode('utf-8')
        return hmac.new(HMAC_SECRET, serialized, hashlib.sha256).hexdigest()

    def verify_signature(self, payload: dict) -> bool:
        if "signature" not in payload:
            return False
        expected = self.sign_payload(payload)
        return hmac.compare_digest(payload["signature"], expected)

    def encrypt_license(self, payload: dict, fingerprint: str) -> str:
        key = self.derive_aes_key(fingerprint)
        payload["signature"] = self.sign_payload(payload)
        
        data = json.dumps(payload).encode('utf-8')
        
        # AES PKCS7 padding
        padder = padding.PKCS7(128).padder()
        padded = padder.update(data) + padder.finalize()
        
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        
        combined = iv + ciphertext
        return base64.b64encode(combined).decode('utf-8')

    def decrypt_license(self, encrypted_str: str, fingerprint: str) -> dict:
        try:
            key = self.derive_aes_key(fingerprint)
            combined = base64.b64decode(encrypted_str.encode('utf-8'))
            if len(combined) < 16:
                raise ValueError("Data block too small")
            
            iv = combined[:16]
            ciphertext = combined[16:]
            
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
            decryptor = cipher.decryptor()
            padded = decryptor.update(ciphertext) + decryptor.finalize()
            
            unpadder = padding.PKCS7(128).unpadder()
            data = unpadder.update(padded) + unpadder.finalize()
            
            payload = json.loads(data.decode('utf-8'))
            return payload
        except Exception as e:
            raise ValueError(f"Decryption failed: {str(e)}")

    def install_license(self, encrypted_str: str) -> bool:
        try:
            # Test decryption first to verify it fits current fingerprint
            fingerprint = get_machine_fingerprint()
            payload = self.decrypt_license(encrypted_str, fingerprint)
            
            if not self.verify_signature(payload):
                print("[Licensing] Invalid signature on installer payload.")
                return False
                
            # Write to file
            with open(LICENSE_FILE_PATH, "w") as f:
                f.write(encrypted_str)
            
            # Set last_run_time to now
            self._update_last_run_time(datetime.datetime.now())
            return True
        except Exception as e:
            print(f"[Licensing] Failed to install license: {e}")
            return False

    def validate_license(self) -> dict:
        # Returns status information
        fingerprint = get_machine_fingerprint()
        
        if not LICENSE_FILE_PATH.exists():
            return {"status": "unactivated", "days_remaining": 0, "message": "Unactivated"}
            
        try:
            with open(LICENSE_FILE_PATH, "r") as f:
                encrypted_str = f.read().strip()
            
            payload = self.decrypt_license(encrypted_str, fingerprint)
            
            if not self.verify_signature(payload):
                return {"status": "tampered", "days_remaining": 0, "message": "License Verification Failed"}
                
            if payload.get("fingerprint") != fingerprint:
                return {"status": "tampered", "days_remaining": 0, "message": "License Verification Failed"}
                
            expiry_str = payload.get("expiry_date")
            activation_str = payload.get("activation_date")
            
            expiry_dt = datetime.datetime.fromisoformat(expiry_str)
            activation_dt = datetime.datetime.fromisoformat(activation_str)
            now = datetime.datetime.now()
            
            # Clock tampering detection
            last_run = self._get_last_run_time()
            if last_run and now < last_run - datetime.timedelta(minutes=15):
                print(f"[Licensing] Clock rollback detected! Current: {now}, Last seen: {last_run}")
                return {"status": "tampered", "days_remaining": 0, "message": "License Verification Failed"}
                
            # Update last run time to now
            self._update_last_run_time(max(now, last_run) if last_run else now)
            
            if now > expiry_dt:
                return {"status": "expired", "days_remaining": 0, "message": "License Verification Failed"}
                
            days_remaining = (expiry_dt - now).days
            if days_remaining < 0:
                days_remaining = 0
            # Return active trial info
            return {
                "status": "active",
                "days_remaining": days_remaining,
                "message": f"Trial: {days_remaining} Days Remaining"
            }
            
        except Exception as e:
            print(f"[Licensing] License validation encountered exception: {e}")
            return {"status": "tampered", "days_remaining": 0, "message": "License Verification Failed"}

    def get_usage_metrics(self) -> dict:
        try:
            return {
                "images_processed": int(self._get_db_value("images_processed", "0")),
                "duplicates_removed": int(self._get_db_value("duplicates_removed", "0")),
                "best_shots_selected": int(self._get_db_value("best_shots_selected", "0")),
                "processing_time": float(self._get_db_value("processing_time", "0.0")),
                "sessions": int(self._get_db_value("sessions", "0"))
            }
        except Exception:
            return {
                "images_processed": 0,
                "duplicates_removed": 0,
                "best_shots_selected": 0,
                "processing_time": 0.0,
                "sessions": 0
            }

    def increment_metric(self, name: str, amount=1):
        try:
            if name == "processing_time":
                val = float(self._get_db_value(name, "0.0"))
            else:
                val = int(self._get_db_value(name, "0"))
            val += amount
            self._set_db_value(name, str(val))
        except Exception as e:
            print(f"[Licensing] Failed to increment metric {name}: {e}")

    def sync_usage_metrics(self):
        # Return metric payload and target server url
        metrics = self.get_usage_metrics()
        server_url = self._get_db_value("server_url", "https://quantilecull-pilot.onrender.com")
        metrics["machine_id"] = get_machine_fingerprint()
        return metrics, f"{server_url}/usage"

