# QuantileCull V1.1 Pilot - Feedback & Bug Reporting Instructions

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
3. **Direct Email**: You can also email your log file located at `%%LOCALAPPDATA%%\QuantileCull\Logs\debug.log` to **support@quantilecull.com** with a description of the issue.

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
