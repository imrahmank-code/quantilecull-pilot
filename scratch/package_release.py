import os
import zipfile
import shutil

project_root = r"E:\Antigravity Projects\Photo Cleaner App"
docs_dir = os.path.join(project_root, "docs")
os.makedirs(docs_dir, exist_ok=True)

# 1. Write docs/Quick_Start_Guide.txt
quick_start_content = """========================================================================
             QuantileCull V1.1 Pilot - Quick Start Guide
========================================================================

Welcome to the QuantileCull V1.1 Pilot! This quick start guide will help
you get up and running on Windows 10 or 11 in less than 2 minutes.

------------------------------------------------------------------------
1. INSTALLATION & SETUP (PORTABLE RUN)
------------------------------------------------------------------------
Since this is a pilot validation build, it is packaged as a portable
executable. No complex installation is required.

Steps:
1. Extract the contents of this ZIP file (QuantileCull_V1.1_Portable.zip)
   to a folder on your local drive (e.g., C:\\QuantileCull or E:\\Apps).
2. Double-click "QuantileCull_V1.1.exe" to launch the application.

*Note: On first launch, Windows Defender SmartScreen might display a
warning ("Windows protected your PC") because this is a private pilot
build. Click "More info" and then click "Run anyway".

------------------------------------------------------------------------
2. REGISTRATION & ACTIVATION
------------------------------------------------------------------------
Upon first launch, a dark registration and activation overlay will appear:
1. Enter your Full Name and Email Address.
2. Enter your Organization / Studio name and Country (optional).
3. Select your main Photography Type (e.g., Event, Wedding, Sports).
4. Enter your unique 12-character Activation License Key provided in your
   pilot email (format: QC-XXXX-XXXX-XXXX).
5. Leave the Advanced Server Endpoint as default (or set it to the URL
   provided by the administrator).
6. Click "Activate Now". The app will contact the activation server,
   install the local license key, and unlock immediately.

------------------------------------------------------------------------
3. PHOTO CULLING IN 3 EASY STEPS
------------------------------------------------------------------------
1. Select Folder: Click "Select Directory" and browse to your shoot folder
   containing RAW or JPEG images.
2. Adjust Parameters: Set the duplicate similarity threshold (default: 85%)
   and specify the top N% selection fraction if you want aggressive culling.
3. Run Culling Scan: Click "Analyze Directory". The offline AI engine will
   automatically detect exact duplicates, group similar shots, evaluate
   sharpness, and penalize closed eyes/blinks.
4. Export: Review recommendations in the dual-grid or split-compare viewer,
   tweak selection flags, and click "Export" to copy best shots to a 
   subfolder or backup local duplicates.

------------------------------------------------------------------------
4. PILOT FEEDBACK & TELEMETRY
------------------------------------------------------------------------
- Feedback Button: Click the "Feedback" button in the app header at any time
  to rate your satisfaction and submit comments.
- Request Feature: Click the "Request Feature" button next to it to suggest
  new workflows or features directly to our product tracker.
- Anonymous Telemetry: The app silently logs culling counts and run times on
  scan completion. No image data or paths are ever transmitted.
- Crash Reports: If the app closes unexpectedly, it will ask for your consent
  on next boot to upload a diagnostic stack trace.

Need help? Contact support at support@quantilecull.com
========================================================================
"""

quick_start_path = os.path.join(docs_dir, "Quick_Start_Guide.txt")
with open(quick_start_path, "w", encoding="utf-8") as f:
    f.write(quick_start_content)
print(f"Created {quick_start_path}")


# 2. Write docs/Pilot_User_Guide.md
user_guide_content = """# QuantileCull V1.1 Pilot - User Guide & Reference Manual

Welcome to the **QuantileCull V1.1 Pilot Release**. QuantileCull is a high-performance, offline-first photo culling and selection desktop application designed for professional wedding, event, and sports photographers.

---

## 1. System Requirements

### Recommended Hardware
- **Operating System**: Windows 10 or Windows 11 (64-bit).
- **Processor**: Intel Core i5/i7/i9 (8th Gen or newer) or AMD Ryzen 5/7/9.
- **Memory (RAM)**: 8 GB minimum (16 GB or higher recommended for large shoots >5,000 photos).
- **Storage**: Solid State Drive (SSD) with at least 500 MB free space for application models, cache database, and temporary execution logs.

### Supported File Formats
- **Metadata Reading**: Standard EXIF and IPTC data.
- **Image Formats**: JPEG, PNG, TIFF, and common RAW formats (CR2, CR3, NEF, ARW) supported via local system codecs.
- *Note: For optimal performance, culling against high-resolution JPEG previews embedded in RAW files is recommended.*

---

## 2. Step-by-Step Activation

QuantileCull operates completely offline after a one-time activation handshake.

1. Ensure your PC is connected to the internet.
2. Launch `QuantileCull_V1.1.exe`.
3. Fill out the **Registration Card** with your professional details. This demographic data maps key usage to specific pilot photographer segments.
4. Input your unique **Activation License Key** (e.g. `QC-7H2D-KQ9P-XM4T`).
5. Click **Activate Now**. Once verified, a local encrypted file `qc_license.dat` is saved in your Local AppData folder, and the application unlocks. You may now disconnect from the internet; the app will continue to run completely offline.

---

## 3. Explaining Culling Modes and Parameters

QuantileCull offers dual culling metrics:

1. **Duplicate Detection Threshold (default: 85%)**:
   - Compares image hashes to identify sequential bursts or duplicate poses. 
   - Increase this threshold (e.g., 90%) to group only identical frames.
   - Decrease this threshold (e.g., 75%) to group wider, similar poses.
2. **Aggressive Culling Fraction (Top N%)**:
   - Automatically selects only the highest-scored photos in each burst. If set to 30%, only the top 30% sharpest, best-composed, open-eyed photos in each burst group will be marked as "Keep".

---

## 4. Troubleshooting & FAQ

### SmartScreen Blocked Launch
- **Issue**: Windows Defender flags the portable binary as unsigned.
- **Solution**: Click **More Info** on the SmartScreen dialog, then click **Run Anyway**.

### Expiry Bar Warning
- **Issue**: A top warning bar displays: `"Trial Ended. Contact QuantileCull for an Extended Evaluation License."`
- **Explanation**: Your 30-day evaluation token has expired. The application has entered **Read-Only Mode**. You can still browse folders, view grids, and inspect historical culling scores. Running new scans or exporting photos is blocked until you click **Renew License** and input a fresh token.

### Clock rollback detected warning
- **Issue**: A red warning bar blocks the UI with `"License Verification Failed (System Clock Rollback Detected)"`.
- **Explanation**: The app's tamper-protection detected that the system time was set backward to bypass the 30-day expiration check. The app will remain locked in Read-Only Mode until the system clock is synchronized to the current local time.

---

## 5. Contact & Bug Reporting

To report a bug:
1. Relaunch the application. If a crash occurred, the app will display a prompt: `"Unexpected Crash Detected. Would you like to send a crash report?"`
2. Click **Send Crash Report** to upload the stack trace to our logs.
3. Alternatively, click the **Feedback** button in the header, describe your workflow, and click **Submit**.
4. Support email: `support@quantilecull.com`.
"""

user_guide_path = os.path.join(docs_dir, "Pilot_User_Guide.md")
with open(user_guide_path, "w", encoding="utf-8") as f:
    f.write(user_guide_content)
print(f"Created {user_guide_path}")


# 3. Write docs/Pilot_Feedback_Package.md
feedback_pkg_content = """# QuantileCull V1.1 Pilot - Feedback & Bug Reporting Instructions

Your feedback is the most critical asset of this V1.1 pilot validation. Please use the following instructions to report bugs, suggest features, and evaluate the culling engine's accuracy.

---

## 1. Culling Accuracy Evaluation Template

When evaluating QuantileCull's selections against your manual culling, please record:

1. **False Positives (Kept Discards)**: Did the app select photos that had motion blur, out-of-focus subjects, or closed eyes?
2. **False Negatives (Discarded Keepers)**: Did the app discard your hero shots or select a poorer pose in a burst group?
3. **Focal Heatmap Check**: Did the face overlay bounding boxes and eye-openness landmark highlights align correctly with your subject's features?

---

## 2. Standard Bug Reporting Workflow

If you encounter an error, UI freeze, or engine failure:

1. **Consent-Based Crash Sync**: Relaunch the application. The system will detect the crash, read `crash.json`, and prompt you to upload it. Click **Send Crash Report** to sync the logs instantly.
2. **Manual Form Submission**: Click the **Feedback** button in the app header and input:
   - Event type you were culling (e.g. Wedding, Sports).
   - Exact error message, visual behavior, or step where the app froze.
   - Size of the image set (number of files and size in GB).
3. **Direct Email**: You can also email your log file located at `%%LOCALAPPDATA%%\\QuantileCull\\Logs\\debug.log` to **support@quantilecull.com** with a description of the issue.

---

## 3. Submitting Feature Requests

We are actively designing the V2 release. To request a new tool:
1. Click the **Request Feature** button in the header of the app.
2. Fill in the **Proposed Feature** title.
3. Choose a **Priority Level**:
   - *Low*: Nice to have.
   - *Medium*: Would improve workflow.
   - *High*: Essential addition.
   - *Critical*: Cannot work without it.
4. Explain the **Workflow Impact** (e.g. "Adding smart filter presets would save 15 minutes of culling time per event").
5. Click **Submit**.
"""

feedback_pkg_path = os.path.join(docs_dir, "Pilot_Feedback_Package.md")
with open(feedback_pkg_path, "w", encoding="utf-8") as f:
    f.write(feedback_pkg_content)
print(f"Created {feedback_pkg_path}")


# 4. Create E:\Antigravity Projects\Photo Cleaner App\dist\QuantileCull_V1.1_Portable.zip
dist_dir = os.path.join(project_root, "dist")
exe_name = "QuantileCull_V1.1.exe"
exe_path = os.path.join(dist_dir, exe_name)
zip_path = os.path.join(dist_dir, "QuantileCull_V1.1_Portable.zip")

if os.path.exists(exe_path):
    print(f"\nPackaging {zip_path}...")
    pdf_user_guide_path = os.path.join(docs_dir, "Pilot_User_Guide.pdf")
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_f:
        # Add executable in root of ZIP
        zip_f.write(exe_path, arcname=exe_name)
        # Add guides in root of ZIP for client convenience
        zip_f.write(quick_start_path, arcname="Quick_Start_Guide.txt")
        zip_f.write(pdf_user_guide_path, arcname="Pilot_User_Guide.pdf")
        zip_f.write(feedback_pkg_path, arcname="Pilot_Feedback_Package.md")
    print(f"Successfully created pilot package ZIP at {zip_path}")
else:
    print(f"\nERROR: Compiled executable {exe_path} not found. Build must be run first.")
