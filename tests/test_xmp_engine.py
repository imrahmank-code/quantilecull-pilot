import unittest
import os
import xml.etree.ElementTree as ET
from xmp_engine import read_xmp_metadata, write_xmp_metadata, get_xmp_path, NAMESPACES

class TestXmpEngine(unittest.TestCase):
    def setUp(self):
        self.image_path = "test_image.JPG"
        self.xmp_path = "test_image.xmp"
        # Ensure clean state
        self._cleanup()

    def tearDown(self):
        self._cleanup()

    def _cleanup(self):
        for p in [self.image_path, self.xmp_path]:
            if os.path.exists(p):
                os.remove(p)

    def test_get_xmp_path(self):
        self.assertEqual(get_xmp_path(self.image_path), self.xmp_path)

    def test_read_missing_xmp(self):
        res = read_xmp_metadata(self.image_path)
        self.assertEqual(res["rating"], 0)
        self.assertEqual(res["label"], "")
        self.assertFalse(res["rejected"])
        self.assertEqual(res["keywords"], [])

    def test_write_and_read_fresh_xmp(self):
        # 1. Write XMP metadata
        success = write_xmp_metadata(self.image_path, rating=4, label="Yellow", rejected=True)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(self.xmp_path))
        
        # 2. Read XMP metadata back
        res = read_xmp_metadata(self.image_path)
        self.assertEqual(res["rating"], 4)
        self.assertEqual(res["label"], "Yellow")
        self.assertTrue(res["rejected"])

    def test_non_destructive_xmp_write(self):
        # 1. Create a dummy XMP file with pre-existing unrelated tags
        xml_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"
    xmlns:tiff="http://ns.adobe.com/tiff/1.0/">
   <tiff:Model>Canon EOS R5</tiff:Model>
   <tiff:Make>Canon</tiff:Make>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
"""
        with open(self.xmp_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
            
        # 2. Write metadata using our engine
        success = write_xmp_metadata(self.image_path, rating=5, label="Green", rejected=False)
        self.assertTrue(success)
        
        # 3. Read it back and verify new tags exist
        res = read_xmp_metadata(self.image_path)
        self.assertEqual(res["rating"], 5)
        self.assertEqual(res["label"], "Green")
        self.assertFalse(res["rejected"])
        
        # 4. Verify original tiff:Model tag is still preserved!
        tree = ET.parse(self.xmp_path)
        root = tree.getroot()
        desc = root.find('.//rdf:Description', NAMESPACES)
        self.assertIsNotNone(desc)
        
        tiff_model = desc.find('{http://ns.adobe.com/tiff/1.0/}Model')
        self.assertIsNotNone(tiff_model)
        self.assertEqual(tiff_model.text, "Canon EOS R5")

if __name__ == '__main__':
    unittest.main()
