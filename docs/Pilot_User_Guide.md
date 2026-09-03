# QuantileCull V1.1 Pilot - User Guide & Reference Manual

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
- **Issue**: A top header bar displays: `"Evaluation Period Ended — Keep your local offline AI processing speed permanent."`
- **Explanation**: Your evaluation token has expired. You can continue with unlimited local AI culling by clicking **★ Unlock Lifetime Access ($59)** or entering your purchased license key under **Enter Key**.

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
