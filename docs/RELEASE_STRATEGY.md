# QuantileCull Release Strategy & Release Engineering Manual

This document governs all release engineering, deployment, and version management operations for QuantileCull.

---

## 1. Branching Strategy

QuantileCull follows a structured branch model designed to isolate active development, stabilize release candidates, and protect the production master branch.

```
main (Production Baseline)
  ▲
  │ (Merge Release / Tag vX.Y.Z-stable)
release/vX.Y (Stable Version Branches)
  ▲
  │ (Merge Release Candidate after QA approval)
release/vX.Y-experimental (Development Integration)
  ▲
  │ (Merge Feature Branch after passing all tests)
feature/* (Isolated Feature Development)
```

### Branch Definitions
* **`main`**: The absolute source of truth representing production-ready stable baselines. Direct pushes are forbidden.
* **`release/vX.Y`**: Stable release tracking branches (e.g., [release/v1.1](file:///E:/Antigravity%20Projects/Photo%20Cleaner%20App/release/v1.1)). These branches are frozen from new features. Only critical hotfixes are permitted.
* **`release/vX.Y-experimental`**: Active integration branch for the current cycle (e.g., [release/v1.2-experimental](file:///E:/Antigravity%20Projects/Photo%20Cleaner%20App/release/v1.2-experimental)). All features merge here first.
* **`feature/*`**: Short-lived branches dedicated to single tasks (e.g., `feature/xmp-support`). Created from and merged back to the experimental branch.

---

## 2. Pull Request & Merge Policy

1. **No Direct Pushes**: Pushing directly to `main` or active release branches is strictly prohibited.
2. **Review Requirements**: All merges into `release/vX.Y-experimental` require a formal pull request review and sign-off.
3. **Automated Status Checks**: Pull requests will not be merged unless:
   * The regression test suite passes 100% cleanly.
   * The code builds successfully into a standalone executable.
4. **Fast-Forward vs. Squash Merge**:
   * Feature branches are **squashed** into `release/vX.Y-experimental` to maintain a clean linear history.
   * `release/vX.Y-experimental` is merged into `release/vX.Y` via a **non-fast-forward merge (`--no-ff`)** to preserve release boundaries.

---

## 3. Versioning & Tagging Conventions

QuantileCull adheres to **Semantic Versioning 2.0.0 (SemVer)**:
* Format: **`vMAJOR.MINOR.PATCH`**
  * **MAJOR**: Architectural overhauls, major rewrites (e.g., switching UI frameworks).
  * **MINOR**: New backward-compatible features (e.g., RAW photo support, Lightroom sync).
  * **PATCH**: Backward-compatible bug/security hotfixes.

### Git Tagging Convention
* Releases are tagged on the target stable branch.
* Production tag format: **`vX.Y.Z-stable`** (e.g., `v1.1.0-stable`).
* Hotfix tag format: **`vX.Y.Z-hotfix`** (e.g., `v1.1.1-hotfix`).

---

## 4. Hotfix Process

When a critical bug is discovered in production:
1. Branch out from the affected release tag:
   ```bash
   git checkout -b hotfix/bug-description v1.1.0-stable
   ```
2. Implement the fix and add dedicated regression tests.
3. Run the complete regression test suite.
4. Merge the hotfix branch back into:
   * The active release branch (`release/v1.1`)
   * The active development integration branch (`release/v1.2-experimental`)
5. Tag the release branch with `v1.1.1-hotfix` and build a new package.

---

## 5. Release Checklist (Definition of Ready to Ship)

Before compiling the production setup installer (`QuantileCull_Setup.exe`):
- [ ] **Regression Verification**: Run all 15+ engine regression tests on a clean virtual environment.
- [ ] **Golden Dataset Audit**: Validate quality scores, duplicate ratios, and culling speed against validation datasets (`Conference_01`, `Expo_01`, etc.).
- [ ] **Performance Assessment**: Verify scan and export times are within 10% of baseline thresholds. Peak memory usage must be recorded.
- [ ] **Licensing Server Handshake**: Confirm local activations validate against the production API.
- [ ] **Update Manifest**: Ensure `latest-version` payload on the server matches the new build.
- [ ] **Release Notes Updated**: Finalize user-facing release notes detailing enhancements and limits.

---

## 6. Rollback & Recovery Procedures

If a deployed release contains a breaking issue:
1. **Immediate Reversion**: Revert the production branch to the previous stable tag:
   ```bash
   git checkout release/v1.1
   git reset --hard v1.1.0-stable
   git push origin release/v1.1 --force
   ```
2. **Re-publish Installer**: Re-build the installer package using the reverted source code and upload.
3. **Database Migration Fallback**: If a database schema modification occurred, restore the backup SQLite database from the automated snapshot folder.

---

## 7. Backup Policy

* **Source Control**: GitHub acts as the primary cloud backup.
* **Workspace Backups**: Standard backups of the development environment are compressed and saved to the root folder (e.g., `E:\Antigravity Projects\HDD_Backup_Pre_V11_Merge.zip`) before any major version integration.
* **Local User Data**: Database caches and licensing data are stored in a dedicated directory:
  * Windows: `%LOCALAPPDATA%\QuantileCull\`
  * macOS: `~/.local/share/QuantileCull/`
  These files are preserved during app upgrades.
