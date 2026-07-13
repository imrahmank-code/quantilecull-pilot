# Release Readiness Checklist — QuantileCull V1.2

This checklist must be executed and fully checked off prior to promoting any experimental branch (`release/v1.2-experimental`) to staging or stable production releases.

---

## Pre-Release Verification

- [ ] **1. Automated Verification**
  - Run the full test suite (regression, unit, integration tests):
    ```powershell
    .venv\Scripts\python.exe tests/run_regression_tests.py
    .venv\Scripts\python.exe -m unittest tests/test_raw_engine.py tests/test_xmp_engine.py tests/test_cache_engine.py tests/run_integration_tests.py
    ```
  - All 24 tests must pass cleanly.

- [ ] **2. Performance Benchmarks**
  - Run the benchmarking script:
    ```powershell
    .venv\Scripts\python.exe tests/benchmark_culling.py
    ```
  - Review `scratch/benchmark_results.txt`.
  - Confirm there is no regression >10% against official performance baselines.

- [ ] **3. Dependency Lock Check**
  - Confirm all packages are locked in `requirements.txt`.
  - Validate that `rawpy` and `exifread` versions are exact.

- [ ] **4. Documentation Alignment**
  - Update `docs/API_REFERENCE.md` if any signature changed.
  - Update `docs/COMPATIBILITY_MATRIX.md` if support bounds were extended.
  - Summarize achievements in `walkthrough.md`.

- [ ] **5. Branch & Version Controls**
  - Verify active development branch is `release/v1.2-experimental`.
  - Confirm version tag rules align with semantic versioning (e.g. `v1.2.0-beta1`).
  - Protect `main` and `release/v1.1` branches from force pushes.

---

## Rollback Protocol

If a release candidate exhibits critical regression in production:
1. Revert target commits on the development branch.
2. Checkout the last frozen release tag (e.g. `v1.1-stable`).
3. Build new temporary patch (e.g. `v1.1.1-hotfix`).
4. Re-verify via regression test suite.
