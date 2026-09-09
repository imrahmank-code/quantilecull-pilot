"""
Unit tests for EnhancedXmpEngine (Pillar 3).
Tests granular sidecar generation, multi-application export profiles (Lightroom Classic,
Capture One, Photo Mechanic), non-destructive tag preservation, and batch tagging.
"""

import unittest
import os
import sys
import tempfile
import shutil
import xml.etree.ElementTree as ET

# Ensure repository root is on sys.path
workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

from enhanced_xmp_engine import (
    EnhancedXmpEngine,
    XmpExportProfile,
    CullDecision,
    LIGHTROOM_PROFILE,
    CAPTURE_ONE_PROFILE,
    PHOTO_MECHANIC_PROFILE,
    UNIVERSAL_PROFILE,
    NAMESPACES
)


class TestEnhancedXmpEngine(unittest.TestCase):
    """Test suite for EnhancedXmpEngine."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.engine = EnhancedXmpEngine(default_profile=UNIVERSAL_PROFILE)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _create_dummy_image(self, filename: str) -> str:
        """Creates a dummy photo file to test sidecar pairing."""
        path = os.path.join(self.test_dir, filename)
        with open(path, "wb") as f:
            f.write(b"MOCK_PHOTO_DATA")
        return path

    def test_cull_decision_resolution(self):
        """Verify translation of CullDecision enum to rating and color label under profiles."""
        # Universal Profile
        r_pick, l_pick, rej_pick = self.engine.resolve_cull_decision(CullDecision.PICK)
        self.assertEqual(r_pick, 5)
        self.assertEqual(l_pick, "Green")
        self.assertFalse(rej_pick)

        r_var, l_var, rej_var = self.engine.resolve_cull_decision(CullDecision.VARIANT)
        self.assertEqual(r_var, 4)
        self.assertEqual(l_var, "Yellow")
        self.assertFalse(rej_var)

        r_rev, l_rev, rej_rev = self.engine.resolve_cull_decision(CullDecision.REVIEW)
        self.assertEqual(r_rev, 3)
        self.assertEqual(l_rev, "Blue")
        self.assertFalse(rej_rev)

        r_rej, l_rej, rej_rej = self.engine.resolve_cull_decision(CullDecision.REJECT)
        self.assertEqual(r_rej, 1)
        self.assertEqual(l_rej, "Red")
        self.assertTrue(rej_rej)

    def test_lightroom_profile_tagging(self):
        """Verify Lightroom Classic specific tags (Rating, SidecarForExtension, photoshop:ColorLabel)."""
        img_path = self._create_dummy_image("ceremony_001.CR3")
        res = self.engine.write_xmp(
            image_path=img_path,
            rating=5,
            label="Green",
            rejected=False,
            profile=LIGHTROOM_PROFILE
        )
        self.assertTrue(res.success)
        self.assertTrue(os.path.exists(res.xmp_path))

        # Inspect XML directly
        tree = ET.parse(res.xmp_path)
        root = tree.getroot()
        desc = root.find('.//rdf:Description', NAMESPACES)

        # Rating = 5
        rating = desc.find('xmp:Rating', NAMESPACES)
        self.assertIsNotNone(rating)
        self.assertEqual(rating.text, "5")

        # Label = Green
        label = desc.find('xmp:Label', NAMESPACES)
        self.assertIsNotNone(label)
        self.assertEqual(label.text, "Green")

        # photoshop:SidecarForExtension = CR3
        sidecar = desc.find('photoshop:SidecarForExtension', NAMESPACES)
        self.assertIsNotNone(sidecar)
        self.assertEqual(sidecar.text, "CR3")

        # photoshop:ColorLabel = Green
        ps_color = desc.find('photoshop:ColorLabel', NAMESPACES)
        self.assertIsNotNone(ps_color)
        self.assertEqual(ps_color.text, "Green")

    def test_photo_mechanic_profile_tagging(self):
        """Verify Photo Mechanic numeric colorclass (4 for Green) and tagged flag."""
        img_path = self._create_dummy_image("reception_002.NEF")
        res = self.engine.write_xmp(
            image_path=img_path,
            rating=5,
            label="Green",
            rejected=False,
            profile=PHOTO_MECHANIC_PROFILE
        )
        self.assertTrue(res.success)

        tree = ET.parse(res.xmp_path)
        root = tree.getroot()
        desc = root.find('.//rdf:Description', NAMESPACES)

        # Photo Mechanic colorclass for Green is '4'
        pm_cc = desc.find('photomechanic:colorclass', NAMESPACES)
        self.assertIsNotNone(pm_cc)
        self.assertEqual(pm_cc.text, "4")

        # Photo Mechanic tagged flag
        pm_tagged = desc.find('photomechanic:tagged', NAMESPACES)
        self.assertIsNotNone(pm_tagged)
        self.assertEqual(pm_tagged.text, "True")

    def test_rejection_tagging(self):
        """Verify reject tags (pick=-1, good=false, tagged=False)."""
        img_path = self._create_dummy_image("blurry_003.ARW")
        res = self.engine.write_xmp(
            image_path=img_path,
            rating=1,
            label="Red",
            rejected=True,
            profile=UNIVERSAL_PROFILE
        )
        self.assertTrue(res.success)

        read_data = self.engine.read_xmp(img_path)
        self.assertEqual(read_data["rating"], 1)
        self.assertEqual(read_data["label"], "Red")
        self.assertTrue(read_data["rejected"])

        # Check raw XML tags
        tree = ET.parse(res.xmp_path)
        desc = tree.getroot().find('.//rdf:Description', NAMESPACES)
        self.assertEqual(desc.find('xmpDM:pick', NAMESPACES).text, "-1")
        self.assertEqual(desc.find('xmpDM:good', NAMESPACES).text, "false")
        self.assertEqual(desc.find('photomechanic:tagged', NAMESPACES).text, "False")

    def test_non_destructive_modification(self):
        """
        Verify that existing develop settings (e.g. Camera Raw / Lightroom adjustments)
        are preserved intact when QuantileCull updates ratings and labels.
        """
        img_path = self._create_dummy_image("portrait_004.DNG")
        xmp_path = os.path.splitext(img_path)[0] + ".xmp"

        # Pre-populate XMP with custom Lightroom Develop and camera calibration tags
        custom_xmp_content = """<?xml version="1.0" encoding="utf-8"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:crs="http://ns.adobe.com/camera-raw-settings/1.0/"
        xmlns:xmp="http://ns.adobe.com/xap/1.0/">
      <crs:Exposure2012>+0.75</crs:Exposure2012>
      <crs:Contrast2012>+15</crs:Contrast2012>
      <crs:Temperature>5600</crs:Temperature>
      <xmp:Rating>0</xmp:Rating>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
"""
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(custom_xmp_content)

        # Update via EnhancedXmpEngine
        res = self.engine.write_xmp(
            image_path=img_path,
            rating=5,
            label="Green",
            rejected=False
        )
        self.assertTrue(res.success)

        # Re-parse and assert develop parameters survived!
        tree = ET.parse(xmp_path)
        desc = tree.getroot().find('.//rdf:Description', NAMESPACES)

        # Updated rating
        self.assertEqual(desc.find('xmp:Rating', NAMESPACES).text, "5")
        self.assertEqual(desc.find('xmp:Label', NAMESPACES).text, "Green")

        # PRESERVED camera raw tags!
        ns_crs = {'crs': 'http://ns.adobe.com/camera-raw-settings/1.0/'}
        exp = desc.find('crs:Exposure2012', ns_crs)
        self.assertIsNotNone(exp, "CRS Exposure tag was destroyed!")
        self.assertEqual(exp.text, "+0.75")

        temp = desc.find('crs:Temperature', ns_crs)
        self.assertIsNotNone(temp, "CRS Temperature tag was destroyed!")
        self.assertEqual(temp.text, "5600")

    def test_keywords_tagging(self):
        """Verify keywords are written into standard dc:subject Bag."""
        img_path = self._create_dummy_image("speech_005.CR3")
        keywords = ["Father of the Bride", "Speech", "Highlight", "QuantileCull"]

        res = self.engine.write_xmp(
            image_path=img_path,
            rating=4,
            label="Yellow",
            keywords=keywords
        )
        self.assertTrue(res.success)

        data = self.engine.read_xmp(img_path)
        self.assertEqual(data["keywords"], keywords)

    def test_batch_tagging(self):
        """Verify batch tagging across multiple candidate images."""
        batch_items = [
            {"path": self._create_dummy_image("batch_1.jpg"), "decision": "PICK"},
            {"path": self._create_dummy_image("batch_2.jpg"), "decision": "VARIANT"},
            {"path": self._create_dummy_image("batch_3.jpg"), "decision": "REJECT"},
        ]

        results = self.engine.batch_tag(batch_items)
        self.assertEqual(len(results), 3)
        self.assertTrue(all(r.success for r in results))

        # Check outcomes
        self.assertEqual(results[0].rating, 5)
        self.assertEqual(results[0].color_label, "Green")
        self.assertFalse(results[0].rejected)

        self.assertEqual(results[1].rating, 4)
        self.assertEqual(results[1].color_label, "Yellow")
        self.assertFalse(results[1].rejected)

        self.assertEqual(results[2].rating, 1)
        self.assertEqual(results[2].color_label, "Red")
        self.assertTrue(results[2].rejected)


if __name__ == "__main__":
    unittest.main()
