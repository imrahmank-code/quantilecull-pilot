import os
import exifread
import rawpy
from datetime import datetime

def extract_raw_metadata(path: str) -> dict:
    """
    Extracts shooting metadata (EXIF) from a RAW photo.
    Returns a dictionary of structured metadata values.
    """
    metadata = {
        "camera_make": "Unknown",
        "camera_model": "Unknown",
        "lens": "Unknown",
        "date_taken": None,
        "iso": None,
        "shutter_speed": "Unknown",
        "aperture": None,
        "width": 0,
        "height": 0
    }
    
    if not os.path.exists(path):
        return metadata
        
    # 1. Use rawpy to get raw dimensions (extremely reliable and fast)
    try:
        with rawpy.imread(path) as raw:
            metadata["width"] = raw.sizes.width
            metadata["height"] = raw.sizes.height
    except Exception as e:
        print(f"[metadata_engine] failed to read raw sizes from {os.path.basename(path)}: {e}")

    # 2. Use exifread to extract standard photographic parameters
    try:
        with open(path, 'rb') as f:
            tags = exifread.process_file(f, details=False)
            
            # Camera details
            if 'Image Make' in tags:
                metadata["camera_make"] = str(tags['Image Make']).strip()
            if 'Image Model' in tags:
                metadata["camera_model"] = str(tags['Image Model']).strip()
                
            # Lens model
            for lens_tag in ['EXIF LensModel', 'Image LensModel', 'EXIF LensName']:
                if lens_tag in tags:
                    metadata["lens"] = str(tags[lens_tag]).strip()
                    break
                    
            # Date taken
            for date_tag in ['EXIF DateTimeOriginal', 'Image DateTime', 'EXIF DateTimeDigitized']:
                if date_tag in tags:
                    date_str = str(tags[date_tag]).strip()
                    try:
                        # Standard EXIF date format is YYYY:MM:DD HH:MM:SS
                        parsed_date = datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
                        metadata["date_taken"] = parsed_date.isoformat()
                        break
                    except ValueError:
                        pass
            
            # ISO
            if 'EXIF ISOSpeedRatings' in tags:
                try:
                    metadata["iso"] = int(str(tags['EXIF ISOSpeedRatings']))
                except ValueError:
                    pass
            elif 'EXIF ISOSpeed' in tags:
                try:
                    metadata["iso"] = int(str(tags['EXIF ISOSpeed']))
                except ValueError:
                    pass
                    
            # Aperture
            if 'EXIF FNumber' in tags:
                try:
                    val_str = str(tags['EXIF FNumber'])
                    if '/' in val_str:
                        num, denom = map(float, val_str.split('/'))
                        metadata["aperture"] = round(num / denom, 1)
                    else:
                        metadata["aperture"] = round(float(val_str), 1)
                except ValueError:
                    pass
                    
            # Shutter speed / Exposure time
            if 'EXIF ExposureTime' in tags:
                metadata["shutter_speed"] = str(tags['EXIF ExposureTime']).strip()
                
    except Exception as e:
        print(f"[metadata_engine] Failed to parse EXIF tags for {os.path.basename(path)}: {e}")
        
    return metadata
