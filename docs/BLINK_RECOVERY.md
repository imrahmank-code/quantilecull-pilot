# AI Eye Correction & Blink Recovery Specification — QuantileCull V1.2 FP7

This document specifies the eye state classification thresholds, candidate matching criteria, warping transformations, and seam blending algorithms.

---

## 1. Eye State Classifications

Eye state is determined from left and right eye openness scores:
* **Closed**: Left and right eye openness are both $<20\%$.
* **Wink**: One eye is open ($\ge 65\%$), the other is closed ($<30\%$).
* **Squint**: Both eyes are between $20\%$ and $45\%$.
* **Fully open**: Both eyes are $\ge 75\%$.
* **Partially open**: All other conditions.

---

## 2. Match Validation & Rejections

To prevent unnatural composites, candidate face replacements must satisfy these limits:
* **Head Pose**: Absolute difference in yaw, pitch, and roll all $\le 12.0^{\circ}$.
* **Expression**: Smile difference $\le 25\%$.
* **Lighting**: Mean HSV brightness difference $\le 25\%$.

---

## 3. Patch Warping & Illumination Correction

### A. Affine Transformation
Eye patches are aligned using a 2D affine warp matrix:
$$\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} 1 & 0 & dx \\ 0 & 1 & dy \end{bmatrix} \begin{bmatrix} x \\ y \\ 1 \end{bmatrix}$$
Where $dx$ and $dy$ represent the relative pixel offsets between the candidate eye center and target eye center.

### B. Illumination Adjustment
Color channels are scaled matching target patch mean and std deviation:
$$\text{out}_c = (\text{src}_c - \bar{S}_c) \cdot \frac{\sigma_{T_c}}{\sigma_{S_c}} + \bar{T}_c$$
Feather blending uses a Gaussian-blurred ellipsoid mask to smooth seam transitions.
