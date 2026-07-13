# QuantileCull V1.1 Performance Baselines

This document establishes the official baseline metrics for the QuantileCull V1.0 release against the permanent production Golden Datasets. All V1.1 optimizations must be benchmarked against these baselines.

---

## 1. Baseline Performance Metrics

| Dataset | Images | Scan Time | Export Time | Peak RAM | Cache Hit Rate | Retention | Version | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Conference_01** | 1,950 | TBD | TBD | TBD | TBD | 25.0% | V1.0.0 | Standard single-track baseline |
| **Conference_02** | 2,412 | TBD | TBD | TBD | TBD | 31.0% | V1.0.0 | Large scale multi-track baseline |
| **Expo_01** | TBD | TBD | TBD | TBD | TBD | TBD | V1.0.0 | Crowd and tradeshow floor |
| **Networking_01** | TBD | TBD | TBD | TBD | TBD | TBD | V1.0.0 | Reception and low-light reception |
| **Awards_01** | TBD | TBD | TBD | TBD | TBD | TBD | V1.0.0 | Stage lighting and keynotes ceremony |

---

## 2. Benchmark Protocol
To ensure measurements are comparable, benchmarks must be conducted under the following standardized conditions:
1. **Hardware**: Record system CPU, GPU, RAM, and storage type (SSD/HDD) in any validation report.
2. **State**: Clear the local cache database `.quantilecull_cache.db` before executing the initial scan (cold cache).
3. **Execution**:
   - Run the scan and note the overall scan time.
   - Re-run the scan (warm cache) to measure database retrieval and cache hit rate.
   - Run a full export to best/hero subfolders and note the export time.
   - Record peak memory usage using a process monitor script (e.g., `psutil` wrapper).
