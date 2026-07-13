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

class TestIdentityResolution(unittest.TestCase):
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

    def test_create_and_get_person(self):
        pid = identity_resolution.create_person("Alice", "Wedding guest")
        self.assertGreater(pid, 0)
        
        person = identity_resolution.get_person(pid)
        self.assertIsNotNone(person)
        self.assertEqual(person["name"], "Alice")
        self.assertEqual(person["notes"], "Wedding guest")

    def test_rename_person(self):
        pid = identity_resolution.create_person("Alice")
        identity_resolution.rename_person(pid, "Alice Smith")
        
        person = identity_resolution.get_person(pid)
        self.assertEqual(person["name"], "Alice Smith")

    def test_delete_person(self):
        pid = identity_resolution.create_person("Bob")
        identity_resolution.delete_person(pid)
        
        person = identity_resolution.get_person(pid)
        self.assertIsNone(person)

    def test_list_persons(self):
        identity_resolution.create_person("Charlie")
        identity_resolution.create_person("Bob")
        
        plist = identity_resolution.list_persons()
        self.assertEqual(len(plist), 2)
        # Order should be ASC by name
        self.assertEqual(plist[0]["name"], "Bob")
        self.assertEqual(plist[1]["name"], "Charlie")

if __name__ == '__main__':
    unittest.main()
