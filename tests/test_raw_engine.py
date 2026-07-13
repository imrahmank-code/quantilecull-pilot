import unittest
import os
import numpy as np
from unittest.mock import patch, MagicMock
from raw_engine import is_raw_file, load_raw_image

class TestRawEngine(unittest.TestCase):
    def test_is_raw_file(self):
        # 1. Supported extensions should return True (case-insensitive)
        self.assertTrue(is_raw_file("photo.CR2"))
        self.assertTrue(is_raw_file("PHOTO.NEF"))
        self.assertTrue(is_raw_file("image.dng"))
        self.assertTrue(is_raw_file("image.cr3"))
        self.assertTrue(is_raw_file("image.arw"))
        
        # 2. Unsupported extensions should return False
        self.assertFalse(is_raw_file("photo.jpg"))
        self.assertFalse(is_raw_file("photo.png"))
        self.assertFalse(is_raw_file("photo.txt"))

    @patch('raw_engine.rawpy.imread')
    def test_load_raw_image_success(self, mock_imread):
        # Mock rawpy reading and postprocessing
        mock_raw = MagicMock()
        mock_raw.postprocess.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
        mock_imread.return_value.__enter__.return_value = mock_raw
        
        # Create a temp file path (needs to exist on disk for the exists check)
        temp_path = "dummy_existing_photo.NEF"
        with open(temp_path, "wb") as f:
            f.write(b"DUMMY_RAW_HEADER_DATA")
            
        try:
            img = load_raw_image(temp_path, half_size=True)
            self.assertIsNotNone(img)
            self.assertEqual(img.shape, (100, 100, 3))
            mock_raw.postprocess.assert_called_once()
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_load_raw_image_corrupted(self):
        # A file with corrupted/empty raw data should be caught gracefully and return None
        temp_path = "corrupted_photo.CR2"
        with open(temp_path, "wb") as f:
            f.write(b"CORRUPTED_RAW_BODY")
            
        try:
            img = load_raw_image(temp_path)
            self.assertIsNone(img)  # Should handle the rawpy.LibRawError gracefully
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == '__main__':
    unittest.main()
