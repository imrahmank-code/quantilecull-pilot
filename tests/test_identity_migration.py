import unittest
import os
import sys
import tempfile
import shutil

# Add workspace dir to path to import local modules
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, workspace_dir)

import cache_engine
import identity_resolution

class TestIdentityMigration(unittest.TestCase):
    def setUp(self):
        self._test_dir = tempfile.mkdtemp()
        self._orig_db = cache_engine.DB_FILE
        self._test_db = os.path.join(self._test_dir, 'test_cache.db')
        cache_engine.DB_FILE = self._test_db
        cache_engine._init_cache()

    def tearDown(self):
        cache_engine.DB_FILE = self._orig_db
        try:
            shutil.rmtree(self._test_dir, ignore_errors=True)
        except Exception:
            pass

    def test_migrate_unresolved_identities(self):
        import sqlite3
        conn = sqlite3.connect(self._test_db)
        # Create un-named cluster
        conn.execute("INSERT INTO identity_clusters (cluster_id, status) VALUES (?, ?)", (10, "active"))
        conn.execute("INSERT INTO identity_clusters (cluster_id, status) VALUES (?, ?)", (11, "active"))
        conn.commit()
        conn.close()

        resolved = identity_resolution.migrate_unresolved_identities()
        self.assertEqual(resolved, 2)

        # Check that they got unique names
        plist = identity_resolution.list_persons()
        self.assertEqual(len(plist), 2)
        self.assertEqual(plist[0]["name"], "Person 1")
        self.assertEqual(plist[1]["name"], "Person 2")

if __name__ == '__main__':
    unittest.main()
