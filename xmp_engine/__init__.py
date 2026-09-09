import os
import xml.etree.ElementTree as ET

# Register namespaces globally to ensure clean prefix output (no ns0: tags)
NAMESPACES = {
    'rdf': 'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'xmp': 'http://ns.adobe.com/xap/1.0/',
    'xmpDM': 'http://ns.adobe.com/xmp/1.0/DynamicMedia/',
    'photomechanic': 'http://ns.pixelfoundry.com/photomechanic/1.0/',
    'dc': 'http://purl.org/dc/elements/1.1/',
    'x': 'adobe:ns:meta/'
}

for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

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

def get_xmp_path(image_path: str) -> str:
    """Returns the sidecar XMP path, checking both .xmp and .EXT.xmp fallbacks."""
    base_path = os.path.splitext(image_path)[0]
    xmp_standard = base_path + ".xmp"
    xmp_appended = image_path + ".xmp"
    if os.path.exists(xmp_appended) and not os.path.exists(xmp_standard):
        return xmp_appended
    return xmp_standard

def read_xmp_metadata(image_path: str) -> dict:
    """
    Reads metadata from the photo's corresponding XMP sidecar.
    Returns a dictionary: {'rating': int, 'label': str, 'rejected': bool, 'keywords': list}
    """
    result = {
        "rating": 0,
        "label": "",
        "rejected": False,
        "keywords": []
    }
    
    xmp_path = get_xmp_path(image_path)
    if not os.path.exists(xmp_path):
        return result
        
    try:
        tree = ET.parse(xmp_path)
        root = tree.getroot()
        
        # Helper to find namespaces
        desc = root.find('.//rdf:Description', NAMESPACES)
        if desc is not None:
            # 1. Parse Rating
            rating_attr = desc.get(f"{{{NAMESPACES['xmp']}}}Rating")
            if rating_attr is not None:
                result["rating"] = int(rating_attr)
            else:
                rating_elem = desc.find('xmp:Rating', NAMESPACES)
                if rating_elem is not None and rating_elem.text:
                    result["rating"] = int(rating_elem.text)
                    
            # 2. Parse Label
            label_attr = desc.get(f"{{{NAMESPACES['xmp']}}}Label")
            if label_attr is not None:
                result["label"] = label_attr
            else:
                label_elem = desc.find('xmp:Label', NAMESPACES)
                if label_elem is not None and label_elem.text:
                    result["label"] = label_elem.text
                    
            # Fallback to photomechanic colorclass
            if not result["label"]:
                cc_attr = desc.get(f"{{{NAMESPACES['photomechanic']}}}colorclass")
                if cc_attr is not None:
                    result["label"] = REVERSE_COLOR_CLASS_MAPPING.get(cc_attr, "")
                else:
                    cc_elem = desc.find('photomechanic:colorclass', NAMESPACES)
                    if cc_elem is not None and cc_elem.text:
                        result["label"] = REVERSE_COLOR_CLASS_MAPPING.get(cc_elem.text, "")
                        
            # 3. Parse Pick / Reject Flag
            pick_attr = desc.get(f"{{{NAMESPACES['xmpDM']}}}pick")
            good_attr = desc.get(f"{{{NAMESPACES['xmpDM']}}}good")
            if pick_attr == "-1" or good_attr == "false":
                result["rejected"] = True
            else:
                pick_elem = desc.find('xmpDM:pick', NAMESPACES)
                good_elem = desc.find('xmpDM:good', NAMESPACES)
                if (pick_elem is not None and pick_elem.text == "-1") or (good_elem is not None and good_elem.text == "false"):
                    result["rejected"] = True
                    
            # 4. Parse Keywords (dc:subject)
            keywords_bag = desc.find('.//dc:subject/rdf:Bag', NAMESPACES)
            if keywords_bag is not None:
                result["keywords"] = [item.text for item in keywords_bag.findall('rdf:li', NAMESPACES) if item.text]
                
    except Exception as e:
        print(f"[xmp_engine] Failed to parse XMP sidecar {os.path.basename(xmp_path)}: {e}")
        
    return result

def write_xmp_metadata(image_path: str, rating: int, label: str, rejected: bool) -> bool:
    """
    Writes or updates rating, label, and pick/reject tags in the XMP sidecar.
    Maintains all other pre-existing XML content intact (non-destructive modification).
    """
    xmp_path = get_xmp_path(image_path)
    
    # 1. Load or construct basic template if missing
    if os.path.exists(xmp_path):
        try:
            tree = ET.parse(xmp_path)
            root = tree.getroot()
            desc = root.find('.//rdf:Description', NAMESPACES)
        except Exception as e:
            print(f"[xmp_engine] Error loading existing XMP, generating fresh: {e}")
            root, desc, tree = _create_fresh_xmp()
    else:
        root, desc, tree = _create_fresh_xmp()
        
    if desc is None:
        return False
        
    try:
        # 2. Remove any inline attributes to enforce standard element structure
        for ns in [NAMESPACES['xmp'], NAMESPACES['xmpDM'], NAMESPACES['photomechanic']]:
            for attr in list(desc.attrib.keys()):
                if attr.startswith(f"{{{ns}}}"):
                    del desc.attrib[attr]
                    
        # Helper to set or create child element
        def set_elem(ns_prefix, tag_name, value):
            full_tag = f"{{{NAMESPACES[ns_prefix]}}}{tag_name}"
            elem = desc.find(f"{ns_prefix}:{tag_name}", NAMESPACES)
            if elem is None:
                elem = ET.SubElement(desc, full_tag)
            elem.text = str(value)
            
        # 3. Write Rating
        set_elem('xmp', 'Rating', rating)
        
        # 4. Write Color Label & Photo Mechanic Color Class
        set_elem('xmp', 'Label', label)
        cc_val = COLOR_CLASS_MAPPING.get(label.lower(), "0")
        set_elem('photomechanic', 'colorclass', cc_val)
        
        # 5. Write Pick/Reject Flag
        if rejected:
            set_elem('xmpDM', 'pick', -1)
            set_elem('xmpDM', 'good', "false")
            set_elem('photomechanic', 'tagged', "False")
        else:
            # If rating >= 3, flag it as a Pick
            if rating >= 3:
                set_elem('xmpDM', 'pick', 1)
                set_elem('xmpDM', 'good', "true")
                set_elem('photomechanic', 'tagged', "True")
            else:
                set_elem('xmpDM', 'pick', 0)
                set_elem('xmpDM', 'good', "true")
                set_elem('photomechanic', 'tagged', "False")
                
        # 6. Write out XML safely
        with open(xmp_path, 'wb') as f:
            f.write(b'<?xml version="1.0" encoding="utf-8"?>\n')
            tree.write(f, encoding='utf-8', xml_declaration=False)
        return True
    except Exception as e:
        print(f"[xmp_engine] Failed to write XMP sidecar {os.path.basename(xmp_path)}: {e}")
        return False

def _create_fresh_xmp():
    """Helper to create a fresh XML tree template for XMP sidecars."""
    xmpmeta = ET.Element(f"{{{NAMESPACES['x']}}}xmpmeta")
    xmpmeta.set("x:xmptk", "Adobe XMP Core 5.6-c140")
    
    rdf = ET.SubElement(xmpmeta, f"{{{NAMESPACES['rdf']}}}RDF")
    desc = ET.SubElement(rdf, f"{{{NAMESPACES['rdf']}}}Description")
    desc.set(f"{{{NAMESPACES['rdf']}}}about", "")
    
    tree = ET.ElementTree(xmpmeta)
    return xmpmeta, desc, tree

# Backward compatible re-exports for Pillar 3 EnhancedXmpEngine
try:
    from enhanced_xmp_engine import (
        EnhancedXmpEngine,
        XmpExportProfile,
        CullDecision,
        LIGHTROOM_PROFILE,
        CAPTURE_ONE_PROFILE,
        PHOTO_MECHANIC_PROFILE,
        UNIVERSAL_PROFILE
    )
except ImportError:
    pass

