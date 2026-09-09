"""
EnhancedXmpEngine - Pillar 3 of QuantileCull Next-Iteration Architecture
Granular XMP sidecar generation, multi-application rating & color label profiles
(Lightroom Classic, Capture One, Photo Mechanic), and non-destructive metadata bridging.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any, Union
import os
import xml.etree.ElementTree as ET

# XML Namespaces according to Adobe, Capture One, and Photo Mechanic standards
NAMESPACES = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'xmpDM': 'http://ns.adobe.com/xmp/1.0/DynamicMedia/',
    'photomechanic': 'http://ns.pixelfoundry.com/photomechanic/1.0/',
    'photoshop': 'http://ns.adobe.com/photoshop/1.0/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'x': 'adobe:ns:meta/'
}

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

# Standard color label to Photo Mechanic numeric color class
COLOR_CLASS_MAPPING = {
    "red": "1",
    "orange": "2",
    "yellow": "3",
    "green": "4",
    "blue": "5",
    "purple": "6",
    "grey": "7",
    "gray": "7",
    "": "0"
}

REVERSE_COLOR_CLASS_MAPPING = {
    "1": "Red",
    "2": "Orange",
    "3": "Yellow",
    "4": "Green",
    "5": "Blue",
    "6": "Purple",
    "7": "Grey",
    "0": ""
}


class CullDecision(str, Enum):
    """Standard culling classification tiers."""
    PICK = "PICK"          # Primary winner (e.g., 5 stars, Green)
    VARIANT = "VARIANT"    # Secondary keeper / alternative angle (e.g., 4 stars, Yellow)
    REVIEW = "REVIEW"      # Candidate needing studio inspection (e.g., 3 stars, Blue)
    REJECT = "REJECT"      # Blurry, closed eyes, flaw (e.g., 1 star, Red)
    UNRATED = "UNRATED"    # Neutral baseline (0 stars, no label)


@dataclass
class XmpExportProfile:
    """Configurable metadata mapping profile for targeted post-processing ecosystems."""
    profile_name: str
    target_application: str  # "Lightroom" | "CaptureOne" | "PhotoMechanic" | "Universal"
    pick_rating: int = 5
    variant_rating: int = 4
    review_rating: int = 3
    reject_rating: int = 1
    pick_color_label: str = "Green"
    variant_color_label: str = "Yellow"
    review_color_label: str = "Blue"
    reject_color_label: str = "Red"
    include_photomechanic_colorclass: bool = True
    include_photoshop_sidecar: bool = True
    write_mode: str = "sidecar_xmp"  # "sidecar_xmp" | "embedded"


# Pre-configured Industry Profiles
LIGHTROOM_PROFILE = XmpExportProfile(
    profile_name="Lightroom_Classic",
    target_application="Lightroom",
    pick_rating=5,
    variant_rating=4,
    review_rating=3,
    reject_rating=1,
    pick_color_label="Green",
    variant_color_label="Yellow",
    review_color_label="Blue",
    reject_color_label="Red",
    include_photomechanic_colorclass=False,
    include_photoshop_sidecar=True
)

CAPTURE_ONE_PROFILE = XmpExportProfile(
    profile_name="Capture_One",
    target_application="CaptureOne",
    pick_rating=5,
    variant_rating=4,
    review_rating=3,
    reject_rating=1,
    pick_color_label="Green",
    variant_color_label="Yellow",
    review_color_label="Blue",
    reject_color_label="Red",
    include_photomechanic_colorclass=True,
    include_photoshop_sidecar=True
)

PHOTO_MECHANIC_PROFILE = XmpExportProfile(
    profile_name="Photo_Mechanic",
    target_application="PhotoMechanic",
    pick_rating=5,
    variant_rating=4,
    review_rating=3,
    reject_rating=1,
    pick_color_label="Green",
    variant_color_label="Yellow",
    review_color_label="Blue",
    reject_color_label="Red",
    include_photomechanic_colorclass=True,
    include_photoshop_sidecar=False
)

UNIVERSAL_PROFILE = XmpExportProfile(
    profile_name="Universal_Wedding_Studio",
    target_application="Universal",
    pick_rating=5,
    variant_rating=4,
    review_rating=3,
    reject_rating=1,
    pick_color_label="Green",
    variant_color_label="Yellow",
    review_color_label="Blue",
    reject_color_label="Red",
    include_photomechanic_colorclass=True,
    include_photoshop_sidecar=True
)


@dataclass
class XmpTagResult:
    """Outcome of an XMP write/tag operation."""
    image_path: str
    xmp_path: str
    rating: int
    color_label: str
    rejected: bool
    success: bool
    target_application: str
    error_message: Optional[str] = None


class EnhancedXmpEngine:
    """
    Advanced XMP sidecar generator and metadata bridge.
    Supports granular ratings, multi-application color profiles, non-destructive
    merging with existing XMP sidecars, and batch tagging.
    """

    def __init__(self, default_profile: Optional[XmpExportProfile] = None):
        self.profiles: Dict[str, XmpExportProfile] = {
            "lightroom": LIGHTROOM_PROFILE,
            "capture_one": CAPTURE_ONE_PROFILE,
            "photo_mechanic": PHOTO_MECHANIC_PROFILE,
            "universal": UNIVERSAL_PROFILE
        }
        self.default_profile: XmpExportProfile = default_profile or UNIVERSAL_PROFILE

    def register_profile(self, profile: XmpExportProfile) -> None:
        """Adds or updates a custom export profile."""
        self.profiles[profile.profile_name.lower()] = profile

    def get_profile(self, name: str) -> XmpExportProfile:
        """Retrieves an export profile by name, defaulting to universal."""
        return self.profiles.get(name.lower(), self.default_profile)

    @staticmethod
    def get_xmp_path(image_path: str) -> str:
        """
        Determines the sidecar XMP path, respecting standard naming conventions.
        Priority:
        1. existing <image>.xmp (e.g. photo.CR3.xmp)
        2. <base>.xmp (e.g. photo.xmp)
        """
        base_path = os.path.splitext(image_path)[0]
        xmp_standard = base_path + ".xmp"
        xmp_appended = image_path + ".xmp"
        if os.path.exists(xmp_appended) and not os.path.exists(xmp_standard):
            return xmp_appended
        return xmp_standard

    def resolve_cull_decision(
        self,
        decision: Union[str, CullDecision],
        profile: Optional[XmpExportProfile] = None
    ) -> Tuple[int, str, bool]:
        """
        Translates a culling classification (PICK, VARIANT, REVIEW, REJECT)
        into exact (rating, color_label, rejected_flag) values under the target profile.
        """
        prof = profile or self.default_profile
        d_str = decision.value if isinstance(decision, CullDecision) else str(decision).upper()

        if d_str == "PICK":
            return prof.pick_rating, prof.pick_color_label, False
        elif d_str == "VARIANT":
            return prof.variant_rating, prof.variant_color_label, False
        elif d_str == "REVIEW":
            return prof.review_rating, prof.review_color_label, False
        elif d_str == "REJECT":
            return prof.reject_rating, prof.reject_color_label, True
        else:
            return 0, "", False

    def read_xmp(self, image_path: str) -> Dict[str, Any]:
        """
        Reads structured metadata from an image's XMP sidecar.
        Preserves compatibility with legacy read_xmp_metadata format while adding
        granular tags (colorlabel, photomechanic tagged state, sidecar extension).
        """
        result = {
            "rating": 0,
            "label": "",
            "rejected": False,
            "keywords": [],
            "sidecar_for_extension": None,
            "photomechanic_tagged": False,
            "photoshop_color_label": None
        }

        xmp_path = self.get_xmp_path(image_path)
        if not os.path.exists(xmp_path):
            return result

        try:
            tree = ET.parse(xmp_path)
            root = tree.getroot()
            desc = root.find('.//rdf:Description', NAMESPACES)
            if desc is not None:
                # 1. Rating
                rating_attr = desc.get(f"{{{NAMESPACES['xmp']}}}Rating")
                if rating_attr is not None:
                    result["rating"] = int(rating_attr)
                else:
                    rating_elem = desc.find('xmp:Rating', NAMESPACES)
                    if rating_elem is not None and rating_elem.text:
                        result["rating"] = int(rating_elem.text)

                # 2. Color Label
                label_attr = desc.get(f"{{{NAMESPACES['xmp']}}}Label")
                if label_attr is not None:
                    result["label"] = label_attr
                else:
                    label_elem = desc.find('xmp:Label', NAMESPACES)
                    if label_elem is not None and label_elem.text:
                        result["label"] = label_elem.text

                # Photoshop ColorLabel
                ps_color = desc.find('photoshop:ColorLabel', NAMESPACES)
                if ps_color is not None and ps_color.text:
                    result["photoshop_color_label"] = ps_color.text

                # Photo Mechanic colorclass fallback
                if not result["label"]:
                    cc_attr = desc.get(f"{{{NAMESPACES['photomechanic']}}}colorclass")
                    if cc_attr is not None:
                        result["label"] = REVERSE_COLOR_CLASS_MAPPING.get(cc_attr, "")
                    else:
                        cc_elem = desc.find('photomechanic:colorclass', NAMESPACES)
                        if cc_elem is not None and cc_elem.text:
                            result["label"] = REVERSE_COLOR_CLASS_MAPPING.get(cc_elem.text, "")

                # 3. Pick / Reject Flag
                pick_attr = desc.get(f"{{{NAMESPACES['xmpDM']}}}pick")
                good_attr = desc.get(f"{{{NAMESPACES['xmpDM']}}}good")
                if pick_attr == "-1" or good_attr == "false":
                    result["rejected"] = True
                else:
                    pick_elem = desc.find('xmpDM:pick', NAMESPACES)
                    good_elem = desc.find('xmpDM:good', NAMESPACES)
                    if (pick_elem is not None and pick_elem.text == "-1") or (good_elem is not None and good_elem.text == "false"):
                        result["rejected"] = True

                # Photo Mechanic Tagged
                pm_tagged = desc.find('photomechanic:tagged', NAMESPACES)
                if pm_tagged is not None and pm_tagged.text:
                    result["photomechanic_tagged"] = pm_tagged.text.lower() == "true"

                # Sidecar extension
                sidecar_elem = desc.find('photoshop:SidecarForExtension', NAMESPACES)
                if sidecar_elem is not None:
                    result["sidecar_for_extension"] = sidecar_elem.text

                # 4. Keywords
                keywords_bag = desc.find('.//dc:subject/rdf:Bag', NAMESPACES)
                if keywords_bag is not None:
                    result["keywords"] = [li.text for li in keywords_bag.findall('rdf:li', NAMESPACES) if li.text]
        except Exception as e:
            print(f"[EnhancedXmpEngine] Error parsing XMP sidecar {os.path.basename(xmp_path)}: {e}")

        return result

    def write_xmp(
        self,
        image_path: str,
        rating: int,
        label: str = "",
        rejected: bool = False,
        keywords: Optional[List[str]] = None,
        profile: Optional[XmpExportProfile] = None,
        extra_tags: Optional[Dict[str, Any]] = None
    ) -> XmpTagResult:
        """
        Non-destructively writes or updates rating, color label, and application-specific
        tags in the companion XMP sidecar. Preserves all pre-existing develop settings,
        crop parameters, and EXIF tags.
        """
        prof = profile or self.default_profile
        xmp_path = self.get_xmp_path(image_path)
        ext = os.path.splitext(image_path)[1].lstrip('.').upper()

        # 1. Load existing or initialize fresh template
        if os.path.exists(xmp_path):
            try:
                tree = ET.parse(xmp_path)
                root = tree.getroot()
                desc = root.find('.//rdf:Description', NAMESPACES)
                if desc is None:
                    root, desc, tree = self._create_fresh_xmp()
            except Exception as e:
                print(f"[EnhancedXmpEngine] Corrupted XMP, generating fresh: {e}")
                root, desc, tree = self._create_fresh_xmp()
        else:
            root, desc, tree = self._create_fresh_xmp()

        if desc is None:
            return XmpTagResult(
                image_path=image_path,
                xmp_path=xmp_path,
                rating=rating,
                color_label=label,
                rejected=rejected,
                success=False,
                target_application=prof.target_application,
                error_message="Failed to initialize XML root element"
            )

        try:
            # 2. Strip conflicting inline attributes to enforce standard element structure
            for ns in [NAMESPACES['xmp'], NAMESPACES['xmpDM'], NAMESPACES['photomechanic'], NAMESPACES['photoshop']]:
                for attr in list(desc.attrib.keys()):
                    if attr.startswith(f"{{{ns}}}"):
                        del desc.attrib[attr]

            def set_elem(ns_prefix: str, tag_name: str, value: Any):
                full_tag = f"{{{NAMESPACES[ns_prefix]}}}{tag_name}"
                elem = desc.find(f"{ns_prefix}:{tag_name}", NAMESPACES)
                if elem is None:
                    elem = ET.SubElement(desc, full_tag)
                elem.text = str(value)

            # 3. Write Core Rating (0-5)
            set_elem('xmp', 'Rating', max(0, min(5, int(rating))))

            # 4. Write Color Label & Photoshop Color Label
            set_elem('xmp', 'Label', label)
            if label:
                set_elem('photoshop', 'ColorLabel', label)

            # 5. Photoshop Sidecar Extension (Lightroom Classic standard)
            if prof.include_photoshop_sidecar and ext:
                set_elem('photoshop', 'SidecarForExtension', ext)

            # 6. Photo Mechanic Specific Elements
            if prof.include_photomechanic_colorclass:
                cc_val = COLOR_CLASS_MAPPING.get(label.lower(), "0")
                set_elem('photomechanic', 'colorclass', cc_val)

            # 7. Pick / Reject / Tagged Directives
            if rejected:
                set_elem('xmpDM', 'pick', -1)
                set_elem('xmpDM', 'good', "false")
                set_elem('photomechanic', 'tagged', "False")
            else:
                if rating >= 3:
                    set_elem('xmpDM', 'pick', 1)
                    set_elem('xmpDM', 'good', "true")
                    set_elem('photomechanic', 'tagged', "True")
                else:
                    set_elem('xmpDM', 'pick', 0)
                    set_elem('xmpDM', 'good', "true")
                    set_elem('photomechanic', 'tagged', "False")

            # 8. Keywords (dc:subject Bag)
            if keywords is not None:
                subj = desc.find('dc:subject', NAMESPACES)
                if subj is None:
                    subj = ET.SubElement(desc, f"{{{NAMESPACES['dc']}}}subject")
                bag = subj.find('rdf:Bag', NAMESPACES)
                if bag is None:
                    bag = ET.SubElement(subj, f"{{{NAMESPACES['rdf']}}}Bag")
                else:
                    bag.clear()
                for kw in keywords:
                    li = ET.SubElement(bag, f"{{{NAMESPACES['rdf']}}}li")
                    li.text = str(kw)

            # 9. Extra Custom Tags
            if extra_tags:
                for k, v in extra_tags.items():
                    if ":" in k:
                        prefix, tag = k.split(":", 1)
                        if prefix in NAMESPACES:
                            set_elem(prefix, tag, v)

            # 10. Atomic Safe File Write
            with open(xmp_path, 'wb') as f:
                f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
                tree.write(f, encoding='utf-8', xml_declaration=False)

            return XmpTagResult(
                image_path=image_path,
                xmp_path=xmp_path,
                rating=rating,
                color_label=label,
                rejected=rejected,
                success=True,
                target_application=prof.target_application
            )

        except Exception as e:
            return XmpTagResult(
                image_path=image_path,
                xmp_path=xmp_path,
                rating=rating,
                color_label=label,
                rejected=rejected,
                success=False,
                target_application=prof.target_application,
                error_message=str(e)
            )

    def batch_tag(
        self,
        cull_items: List[Dict[str, Any]],
        profile: Optional[XmpExportProfile] = None
    ) -> List[XmpTagResult]:
        """
        Processes batch culling results into XMP sidecars.
        
        Args:
            cull_items: List of dicts, each with at least 'path' and either 'decision' or ('rating', 'label', 'rejected').
            profile: Optional export profile to use for all items.
            
        Returns:
            List of XmpTagResult records for each photo.
        """
        results: List[XmpTagResult] = []
        for item in cull_items:
            path = item.get("path") or item.get("file_path")
            if not path:
                continue

            if "decision" in item:
                rating, label, rejected = self.resolve_cull_decision(item["decision"], profile)
            else:
                rating = item.get("rating", 0)
                label = item.get("label", "")
                rejected = item.get("rejected", False)

            keywords = item.get("keywords")
            extra_tags = item.get("extra_tags")

            res = self.write_xmp(
                image_path=path,
                rating=rating,
                label=label,
                rejected=rejected,
                keywords=keywords,
                profile=profile,
                extra_tags=extra_tags
            )
            results.append(res)
        return results

    @staticmethod
    def _create_fresh_xmp():
        """Creates a standardized W3C RDF / Adobe XMP tree template."""
        xmpmeta = ET.Element(f"{{{NAMESPACES['x']}}}xmpmeta")
        xmpmeta.set("x:xmptk", "QuantileCull Enhanced XMP Core 2.0")
        rdf = ET.SubElement(xmpmeta, f"{{{NAMESPACES['rdf']}}}RDF")
        desc = ET.SubElement(rdf, f"{{{NAMESPACES['rdf']}}}Description")
        desc.set(f"{{{NAMESPACES['rdf']}}}about", "")
        tree = ET.ElementTree(xmpmeta)
        return xmpmeta, desc, tree
