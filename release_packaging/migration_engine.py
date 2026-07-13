def migrate_settings(old_settings: dict) -> dict:
    """
    Migrates user settings and configurations from V1.1 formats to V1.2.
    Adds default settings for new V1.2 Expression Intelligence, Eye Correction, and Export Presets.
    """
    new_settings = old_settings.copy()
    
    # 1. Expression default limits
    if "eye_openness_threshold" not in new_settings:
        new_settings["eye_openness_threshold"] = 75.0
    if "smile_threshold" not in new_settings:
        new_settings["smile_threshold"] = 50.0
        
    # 2. Eye Correction defaults
    if "auto_eye_correction" not in new_settings:
        new_settings["auto_eye_correction"] = True
    if "pose_alignment_tolerance" not in new_settings:
        new_settings["pose_alignment_tolerance"] = 12.0
        
    # 3. Export preset settings
    if "default_export_preset" not in new_settings:
        new_settings["default_export_preset"] = "Wedding"
        
    # 4. Diagnostic Developer mode
    if "developer_diagnostics_enabled" not in new_settings:
        new_settings["developer_diagnostics_enabled"] = False
        
    return new_settings
