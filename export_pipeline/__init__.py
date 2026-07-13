import os
import shutil
import json
import xml.etree.ElementTree as ET
from typing import List, Dict, Any, Tuple

def write_xmp_sidecar(image_path: str, rating: int, label: str, keywords: List[str]) -> bool:
    """
    Writes or updates a Lightroom-compatible non-destructive .xmp sidecar file.
    """
    base, _ = os.path.splitext(image_path)
    xmp_path = base + ".xmp"
    
    # Generate keywords XML block
    keywords_li = "".join(f"      <rdf:li>{kw}</rdf:li>\n" for kw in keywords)
    
    default_xmp = f"""<x:xmpmeta xmlns:x="adobe:ns:meta/" x:xmptk="Adobe XMP Core 5.6">
  <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
    <rdf:Description rdf:about=""
        xmlns:xmp="http://ns.adobe.com/xap/1.0/"
        xmlns:dc="http://purl.org/dc/elements/1.1/"
        xmp:Rating="{rating}"
        xmp:Label="{label}">
      <dc:subject>
        <rdf:Bag>
{keywords_li}        </rdf:Bag>
      </dc:subject>
    </rdf:Description>
  </rdf:RDF>
</x:xmpmeta>
"""
    try:
        if not os.path.exists(xmp_path):
            with open(xmp_path, "w", encoding="utf-8") as f:
                f.write(default_xmp)
            return True
            
        # Parse and update existing non-destructively
        with open(xmp_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            
        # Non-destructive search/replace or fallback
        if "xmp:Rating=" in content:
            import re
            content = re.sub(r'xmp:Rating="[^"]*"', f'xmp:Rating="{rating}"', content)
        else:
            content = content.replace('<rdf:Description', f'<rdf:Description xmp:Rating="{rating}"')
            
        if "xmp:Label=" in content:
            import re
            content = re.sub(r'xmp:Label="[^"]*"', f'xmp:Label="{label}"', content)
        else:
            content = content.replace('<rdf:Description', f'<rdf:Description xmp:Label="{label}"')
            
        with open(xmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"[export_pipeline] XMP write failed for {xmp_path}: {e}")
        return False

def apply_preset(photo_details: List[Dict[str, Any]], preset_name: str) -> List[Dict[str, Any]]:
    """
    Applies culling templates mapping scene/highlight types to ratings and labels.
    """
    updated = []
    for photo in photo_details:
        p_copy = photo.copy()
        scene = photo.get("scene", "General")
        is_highlight = photo.get("is_highlight", False)
        
        rating = 0
        label = "None"
        keywords = [scene]
        
        if is_highlight:
            keywords.append("Highlight")
            
        if preset_name == "Wedding":
            if is_highlight:
                rating = 5
                label = "Red"
            elif scene == "Portraits":
                rating = 4
                label = "Blue"
            elif scene == "Ceremony":
                rating = 3
                label = "Green"
            elif scene == "Reception":
                rating = 3
                label = "Yellow"
            else:
                rating = 2
        elif preset_name == "Corporate":
            if is_highlight:
                rating = 5
                label = "Blue"
            elif scene == "Portraits":
                rating = 4
                label = "None"
            else:
                rating = 3
                label = "Purple"
        elif preset_name == "Sports":
            if is_highlight:
                rating = 5
                label = "Red"
            else:
                rating = 3
                
        p_copy["rating"] = rating
        p_copy["label"] = label
        p_copy["keywords"] = keywords
        updated.append(p_copy)
        
    return updated

def generate_report(summary: Dict[str, Any], export_path: str, format_type: str) -> bool:
    """
    Generates JSON or HTML automated culling reports for client/photographer reviews.
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(export_path)), exist_ok=True)
        if format_type.lower() == "json":
            with open(export_path, "w", encoding="utf-8") as f:
                json.dump(summary, f, indent=2)
            return True
        elif format_type.lower() == "html":
            html = f"""<!DOCTYPE html>
<html>
<head>
  <title>QuantileCull Culling Summary</title>
  <style>
    body {{ font-family: sans-serif; background: #121212; color: #E0E0E0; padding: 20px; }}
    h1 {{ color: #00E5FF; }}
    .metric {{ margin: 10px 0; font-size: 1.1em; }}
  </style>
</head>
<body>
  <h1>Culling Report Summary</h1>
  <div class="metric"><b>Analyzed:</b> {summary.get("analyzed", 0)}</div>
  <div class="metric"><b>Kept:</b> {summary.get("kept", 0)}</div>
  <div class="metric"><b>Blink Recoveries Applied:</b> {summary.get("blink_recoveries", 0)}</div>
  <div class="metric"><b>Highlights Selected:</b> {summary.get("highlights_count", 0)}</div>
</body>
</html>
"""
            with open(export_path, "w", encoding="utf-8") as f:
                f.write(html)
            return True
        return False
    except Exception as e:
        print(f"[export_pipeline] Report write failed: {e}")
        return False

def prepare_delivery_folders(photo_details: List[Dict[str, Any]], base_dest: str, structure_by: str) -> bool:
    """
    Copies or structures files into subdirectories sorted by scenes, chapters, persons, or highlights.
    """
    try:
        for photo in photo_details:
            src_path = photo.get("file_path", "")
            if not src_path or not os.path.exists(src_path):
                continue
                
            subfolder = "General"
            if structure_by == "scenes":
                subfolder = photo.get("scene", "General")
            elif structure_by == "chapters":
                subfolder = photo.get("chapter", "Chapter 1")
            elif structure_by == "highlights":
                subfolder = "Highlights" if photo.get("is_highlight", False) else "Regular"
            elif structure_by == "persons":
                metrics = photo.get("metrics", {})
                faces = metrics.get("faces", [])
                if faces:
                    # Pick first resolved person name
                    subfolder = faces[0].get("person_name", "Unresolved")
                else:
                    subfolder = "No Faces"
                    
            dest_dir = os.path.join(base_dest, subfolder)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy(src_path, os.path.join(dest_dir, os.path.basename(src_path)))
        return True
    except Exception as e:
        print(f"[export_pipeline] Folder structure generation failed: {e}")
        return False

class BatchWorkflowEngine:
    """
    Maintains workflow queue states inside a local progress configuration JSON.
    """
    def __init__(self, state_file_path: str):
        self.state_path = state_file_path
        self.queue = []
        self.completed = []
        self.load_state()
        
    def load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.queue = data.get("queue", [])
                    self.completed = data.get("completed", [])
            except Exception:
                pass
                
    def save_state(self):
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump({"queue": self.queue, "completed": self.completed}, f, indent=2)
        except Exception:
            pass
            
    def add_to_queue(self, folder_path: str):
        if folder_path not in self.queue and folder_path not in self.completed:
            self.queue.append(folder_path)
            self.save_state()
            
    def mark_completed(self, folder_path: str):
        if folder_path in self.queue:
            self.queue.remove(folder_path)
        if folder_path not in self.completed:
            self.completed.append(folder_path)
        self.save_state()
        
    def get_progress(self) -> Dict[str, Any]:
        return {
            "queue_size": len(self.queue),
            "completed_size": len(self.completed),
            "next_in_queue": self.queue[0] if self.queue else None
        }
