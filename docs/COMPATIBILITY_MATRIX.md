# Compatibility Matrix — QuantileCull V1.2

This document details the software, hardware, file formats, and metadata standards supported by QuantileCull V1.2.

---

## 1. Operating Systems

| Operating System | Version | Architecture | Status | Notes |
| :--- | :--- | :--- | :---: | :--- |
| **Windows 10** | 1909 or newer | x64 | **Supported** | Main production target. |
| **Windows 11** | 21H2 or newer | x64 | **Supported** | Main production target. |
| **macOS** | Catalina or newer | Intel / Apple Silicon | *Planned* | Postponed for V1.3. |
| **Linux** | Ubuntu 22.04 LTS | x64 | *Planned* | Postponed for V1.3. |

---

## 2. Python Runtimes

* **Python 3.10**: Compatible (Verified by regression suite).
* **Python 3.11**: **Recommended** (Primary production and development version).
* **Python 3.12**: Compatible.

---

## 3. RAW Image Formats

QuantileCull recognizes and decodes RAW assets from major camera vendors:

| Format Extension | Camera Vendor | Decoded Engine | Preview Type | Status |
| :---: | :--- | :---: | :---: | :---: |
| **CR2** | Canon | `rawpy` | JPEG Preview | **Supported** |
| **CR3** | Canon | `rawpy` | JPEG Preview | **Supported** |
| **NEF** | Nikon | `rawpy` | JPEG Preview | **Supported** |
| **NRW** | Nikon | `rawpy` | JPEG Preview | **Supported** |
| **ARW** | Sony | `rawpy` | JPEG Preview | **Supported** |
| **ORF** | Olympus | `rawpy` | JPEG Preview | **Supported** |
| **RAF** | Fujifilm | `rawpy` | JPEG Preview | **Supported** |
| **RW2** | Panasonic | `rawpy` | JPEG Preview | **Supported** |
| **DNG** | Leica / Adobe / Mobile | `rawpy` | JPEG Preview | **Supported** |
| **PEF** | Pentax | `rawpy` | JPEG Preview | **Supported** |
| **X3F** | Sigma | `rawpy` | JPEG Preview | **Supported** |

---

## 4. Metadata & Sidecar Standards

* **XMP Standard**: Adobe Extensible Metadata Platform schema definition version 2020.
* **Metadata Fields Written**:
  * `xmp:Rating` (0 - 5 stars)
  * `xmp:Label` (Red, Orange, Yellow, Green, Blue, Purple, Grey)
  * `photoshop:Urgency` (Numeric mapping corresponding to Lightroom Classic color label styles)
  * `val:Rejected` (Custom boolean flag indicating user select rejection status)

---

## 5. Software Interoperability

QuantileCull reads and writes XMP sidecars in a completely non-destructive format compatible with:

* **Adobe Lightroom Classic** (Ver 12.0 or newer)
* **Adobe Bridge** (Ver 2023 or newer)
* **Adobe Camera Raw (ACR)** (Ver 15.0 or newer)
* **Phase One Capture One Pro** (Ver 23 or newer - sidecar sync enabled)
* **Darktable** (Ver 4.2 or newer)
