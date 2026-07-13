import os

def check_for_updates(current_version: str, manifest: dict) -> dict:
    """
    Checks if a newer release candidate or stable version exists in the release manifest.
    Returns details on update action required.
    """
    latest_version = manifest.get("latest_stable", "1.2.0")
    latest_rc = manifest.get("latest_rc", "1.2.0-rc1")
    download_url = manifest.get("download_url", "")
    sha256_hash = manifest.get("sha256", "")
    
    # Simple semantic tag comparison: e.g. "1.1.0" < "1.2.0"
    def parse_ver(v_str):
        clean = v_str.replace("v", "").split("-")[0]
        return [int(x) for x in clean.split(".")]
        
    curr_parsed = parse_ver(current_version)
    latest_parsed = parse_ver(latest_version)
    
    update_available = latest_parsed > curr_parsed
    
    # If same base version, check if currently on RC and stable is out
    if latest_parsed == curr_parsed and "rc" in current_version.lower() and "rc" not in latest_version.lower():
        update_available = True
        
    return {
        "update_available": update_available,
        "current_version": current_version,
        "latest_stable": latest_version,
        "latest_rc": latest_rc,
        "download_url": download_url,
        "sha256": sha256_hash
    }
