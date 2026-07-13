import unittest
import os
import sys

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import release_packaging.migration_engine as migration_engine
import release_packaging.auto_updater as auto_updater

class TestMigrationEngine(unittest.TestCase):
    def test_settings_migration(self):
        old_settings = {
            "cull_threshold": 80.0,
            "theme": "dark"
        }
        new_settings = migration_engine.migrate_settings(old_settings)
        
        self.assertEqual(new_settings["cull_threshold"], 80.0)
        self.assertEqual(new_settings["theme"], "dark")
        # Verify newly injected V1.2 defaults
        self.assertEqual(new_settings["eye_openness_threshold"], 75.0)
        self.assertEqual(new_settings["smile_threshold"], 50.0)
        self.assertEqual(new_settings["developer_diagnostics_enabled"], False)

    def test_auto_updater_check(self):
        manifest = {
            "latest_stable": "1.2.0",
            "latest_rc": "1.2.0-rc3",
            "download_url": "https://quantilecull.com/releases/v1.2.0.exe",
            "sha256": "abcdef"
        }
        res = auto_updater.check_for_updates("1.1.0", manifest)
        self.assertTrue(res["update_available"])
        self.assertEqual(res["latest_stable"], "1.2.0")

if __name__ == '__main__':
    unittest.main()
