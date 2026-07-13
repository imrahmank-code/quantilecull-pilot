# QuantileCull Developer Reference Guide

This reference guide establishes the coding standards, repository layout, testing processes, and code policies required for all developers contributing to QuantileCull.

---

## 1. Repository Architecture

QuantileCull is structured to keep backend logic, frontend assets, AI models, and deployment configurations modular and decoupled.

```text
QuantileCull/
 ├── .agents/                    # Workspace configuration & project rules
 ├── brand/                      # Icon files and corporate assets
 ├── build/                      # Temporary build targets generated during compilation
 ├── dist/                       # Compiled executables and setup files
 ├── docs/                       # Project guides, strategies, and developer manuals
 ├── models/                     # OpenCV DNN face detection weights and metadata
 ├── release/                    # Frozen artifacts from previous versions
 ├── scratch/                    # Temporary assets, scripts, and logs (excluded from commits)
 ├── scripts/                    # Utility scripts (licensing server, export tools)
 ├── static/                     # Frontend static assets (js, css, images)
 ├── templates/                  # Frontend HTML templates (if server-rendered)
 ├── tests/                      # Python unit tests and regression suites
 ├── app.py                      # Flask desktop application entry point & API routes
 ├── image_analyzer.py           # Core computer-vision image scoring and analysis module
 ├── licensing.py                # Local licensing encryption and verification module
 ├── requirements.txt            # Package manifest for Python environment
 └── setup.iss                   # Inno Setup compiler compilation script
```

---

## 2. Coding Standards & Conventions

### Branch Naming Conventions
Always name feature branches with a clear prefix:
* `feature/<short-description>`: New functionality (e.g., `feature/xmp-rating`).
* `bugfix/<issue-description>`: Fixing a defect (e.g., `bugfix/exif-orientation-fix`).
* `hotfix/<patch-version>`: Emergency patch for production (e.g., `hotfix/v1.1.1`).
* `perf/<speedup-description>`: Performance optimization (e.g., `perf/hash-speedup`).

### Commit Message Standards
We follow basic Conventional Commits guidelines to ensure an readable git log:
* **Format**: `type(scope): description`
* **Types**:
  * `feat`: A new user-facing feature.
  * `fix`: A bug fix.
  * `perf`: Code changes that improve execution speed or memory usage.
  * `docs`: Documentation updates.
  * `test`: Adding or modifying tests.
  * `refactor`: Structural code cleanup without changing behavior.
* **Example**:
  ```text
  feat(xmp): add support for writing ratings to Lightroom sidecar files
  ```

---

## 3. Testing Workflow & Regression Suite

Every developer must run tests locally before proposing changes:

### 1. Licensing Handshake Verification
Validates state decryption, hardware ID matching, and clocks rollback lockout:
```powershell
.venv\Scripts\python.exe tests/run_licensing_tests.py
```

### 2. Engine Regression Suite
Runs the culling engine against the baseline metrics to detect scoring or grouping drifts:
```powershell
.venv\Scripts\python.exe tests/run_regression_tests.py
```

---

## 4. Feature Flag Policy

For large or experimental features (e.g., face recognition models):
* Implement feature flags in the environment variable layer.
* Check flags in the backend (e.g., `os.environ.get("ENABLE_EXPERIMENTAL_FACE_RECOG", "0") == "1"`).
* Keeps experimental features off by default in stable builds while allowing in-place integration testing.

---

## 5. Code Review & Performance Benchmarks

### Review Checklist
* [ ] No hardcoded absolute file system paths.
* [ ] Proper try-except handling around file and socket IO.
* [ ] Clean logging statements using the built-in system instead of raw prints.
* [ ] HTML IDs and CSS classes follow naming guidelines.

### Performance Benchmarks
Any changes to image processing, file reading, or caching must record the following metrics on a Golden Dataset:
1. **Scan Time**: Processing time per image (target: < 10ms/image on SSD).
2. **Peak Memory Consumption**: Monitor RAM spikes during batch loading.
3. **Database Write Speed**: Query speed on cached image sets.

---

## 6. Definition of Done (DoD)

A task is considered **Done** only when it satisfies these conditions:
1. **Source Code**: Clean, formatted, commented, and decoupled from local machine profiles.
2. **Local Tests**: 100% pass on both `run_licensing_tests.py` and `run_regression_tests.py`.
3. **Packaging**: Compiled binary (`QuantileCull_V1.X.exe`) builds without errors.
4. **Documentation**: Necessary manuals, guides, or readme files are updated.
5. **PR Review**: Code has been reviewed, approved, and integrated into the active development branch.
