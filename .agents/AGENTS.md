# QuantileCull V1.1 Development Charter Rules

These project-scoped rules govern all development and maintenance activities during the QuantileCull V1.1 cycle.

---

## 1. Protect V1.0 Gold Master (Rule 1)
* **Immutable Deliverables**: Never modify, overwrite, or delete:
  - `release/V1.0.0/`
  - `QuantileCull_V1.0.exe` (or spec specs for V1.0)
  - V1.0 release documentation
  - Archived validation reports
* **Safety Principle**: Treat V1.0 deliverables as frozen and read-only.

---

## 2. Development Branch (Rule 2)
* **V1.1 Scope**: All future work belongs to the V1.1 development cycle.
* **Compatibility**: New features must not break V1.0 functionality or degrade existing metrics.

---

## 3. Mandatory Validation (Rule 3)
* **Required Actions per Change**: Every code change must include:
  1. Implementation summary.
  2. Validation procedure.
  3. Regression execution.
  4. Risk assessment.
  5. Updated walkthrough and task documentation.
* **Required Regression Command**:
  ```powershell
  .venv\Scripts\python.exe tests/run_regression_tests.py
  ```
  All 15 regression tests must pass cleanly before any code is marked as complete.
* **Golden Dataset Rule**: All modifications affecting selection, duplicate detection, storytelling, hero extraction, or export behavior MUST be validated against the permanent production validation datasets before completion. Regression tests alone are insufficient.
  - *Mandatory Validation Datasets*: `Conference_01`, `Conference_02`, `Expo_01`, `Networking_01`, `Awards_01`.
* **Performance Regression Rule**: Any modification affecting duplicate detection, thumbnail generation, image scoring, export pipeline, or the cache subsystem must record:
  1. Scan time
  2. Export time
  3. Peak memory usage
  4. Thumbnail cache hit rate (if applicable)
  against at least one Golden Dataset. Performance regressions >10% require explicit approval.

---

## 4. Workspace Hygiene (Rule 4)
* **Preserved Directories**: Always preserve `archive/`, `release/`, `docs/`, and `tests/`.
* **Root Cleanliness**: Never create clutter or temporary files in the project root.
* **Temporary Assets**: All scratch files, debugging scripts, and temporary logs must reside under:
  ```text
  scratch/
  ```

---

## 5. Production Stability First (Rule 5)
* **Priority Order**:
  1. Stability
  2. Accuracy
  3. Performance
  4. User Experience
* **Architecture**: Avoid large architectural rewrites unless explicitly approved by the user.

---

## 6. Forbidden Operations without Approval
Do NOT perform any of the following without explicit approval:
* Rewrite the duplicate engine.
* Replace the `pywebview` framework.
* Replace the `MediaPipe`/`OpenCV` processing stack.
* Redesign the export architecture.
* Modify production release artifacts.

---

## 7. Required Deliverables for Every Task
Each development task must produce:
1. **Implementation Report**.
2. **Validation Report**.
3. **Updated `walkthrough.md`**.
4. **Updated `task.md`**.
5. **Final Production Impact Assessment**.

---

## 8. External HDD Portability & Drive Auto-Detection (Rule 8)
* **Strict "External HDD Only" Policy**: All repositories, caches, databases, models, scratchpad assets, and logs must be stored on the personal external HDD. The local system folders (`C:\Users\<User>\OneDrive`, `Desktop`, `Documents`, `AppData\Local`) are strictly read-only or must be completely ignored.
* **Dynamic Drive Auto-Detection**:
  - Do NOT hardcode drive letters (`C:`, `D:`, `E:`, `F:`) in code, settings, or instructions.
  - If the IDE metadata or workspace configuration references a local path or OneDrive path (e.g. `C:\Users\Khalifat\OneDrive...`), the AI assistant MUST ignore the drive letter `C:` and look for the folder structure `Antigravity Projects\Photo Cleaner App` on other drives (`D:\`, `E:\`, `F:\`, etc.) to locate the active external HDD workspace.
  - All command invocations, file editing, and test executions must run against the detected external HDD drive letter workspace.
  - In code, use path-relative directory resolution (e.g. `Path(__file__).resolve().parent`) to dynamically adapt paths at runtime, regardless of the PC's assigned drive letter.

---

## 9. External Workspace Verification (Rule 9)
Before performing any file operation, the AI assistant MUST:
1. Locate `AGY_WORKSPACE.json` on all mounted drives.
2. Use the discovered drive as `WORKSPACE_ROOT`.
3. Refuse to create repositories, logs, models, cache, exports, or backups outside `WORKSPACE_ROOT`.
4. Ignore OneDrive, Desktop, Documents, Downloads, AppData, and temporary folders unless explicitly instructed.
5. If `AGY_WORKSPACE.json` is not found, stop execution and request workspace verification.

The external HDD is the authoritative source of truth for all Antigravity projects.

---

## 10. Unified Installer Build & Deployment Automation (Rule 10)
* **Single Source of Truth**: The latest compiled installer executable is always generated at:
  `E:\Antigravity Projects\Photo Cleaner App\dist\QuantileCull_Setup.exe`
* **Build Automation Script**: Always use the PowerShell build script:
  `E:\Antigravity Projects\Photo Cleaner App\build_installer.ps1`
  to compile the PyInstaller app executable and build the Inno Setup installer package in one command.
* **Build Execution Steps**:
  1. Open PowerShell inside the `Photo Cleaner App` directory.
  2. Run the script:
     ```powershell
     .\build_installer.ps1
     ```
  3. The script will automatically locate Inno Setup 6, clean intermediate directories, compile the binary, and build the final `QuantileCull_Setup.exe`.
* **Deployment/Distribution**:
  - The website's dynamic redirect (`api/download.js`) points to Filebin: `https://filebin.net/quantilecull-v11/QuantileCull_Setup.zip`.
  - When changes are made, zip the new setup file, upload it to the Filebin path, and redeploy to Vercel via `npx vercel --prod --yes`.



