"""阶段3: 擦除与修复。
默认 inpaint 修复, 大面积红色用背景色填充。
"""

from __future__ import annotations

import cv2
import numpy as np

from .utils import load_bgr, load_gray, save_bgr_jpeg


def _sample_background_color(img_bgr, mask, sample_radius=20):
    mask_bool = mask > 127
    if mask_bool.sum() == 0:
        return img_bgr.copy()
    result = img_bgr.copy()
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (sample_radius, sample_radius))
    dilated = cv2.dilate((mask_bool.astype(np.uint8)) * 255, k)
    ring = (dilated > 127) & (~mask_bool)
    if ring.sum() == 0:
        inpaint_mask = (mask_bool.astype(np.uint8)) * 255
        return cv2.inpaint(img_bgr, inpaint_mask, 5, cv2.INPAINT_TELEA)
    bg_b = int(np.median(img_bgr[:, :, 0][ring]))
    bg_g = int(np.median(img_bgr[:, :, 1][ring]))
    bg_r = int(np.median(img_bgr[:, :, 2][ring]))
    result[mask_bool] = (bg_b, bg_g, bg_r)
    return result


def _apply_mask_array(img_bgr, mask_gray, method="inpaint"):
    if mask_gray.shape[:2] != img_bgr.shape[:2]:
        mask_gray = cv2.resize(mask_gray, (img_bgr.shape[1], img_bgr.shape[0]),
                               interpolation=cv2.INTER_NEAREST)
    if mask_gray.dtype != np.uint8:
        mask_gray = mask_gray.astype(np.uint8)

    if method == "white":
        result = img_bgr.copy()
        result[mask_gray > 127] = (255, 255, 255)
        return result
    if method == "bgfill":
        return _sample_background_color(img_bgr, mask_gray)
    inpaint_mask = ((mask_gray > 127).astype(np.uint8)) * 255
    return cv2.inpaint(img_bgr, inpaint_mask, 5, cv2.INPAINT_TELEA)


def apply_mask(input_path, mask_path, output_path, method="inpaint"):
    try:
        img = load_bgr(input_path)
        if img is None:
            return False
        mask = load_gray(mask_path)
        if mask is None:
            return False
        cleaned = _apply_mask_array(img, mask, method=method)
        return save_bgr_jpeg(cleaned, output_path)
    except Exception:
        return False


def apply_masks_separately(preprocessed_path, red_mask_path, hw_mask_path, output_path):
    try:
        img = load_bgr(preprocessed_path)
        if img is None:
            return False

        if red_mask_path is not None:
            red_mask = load_gray(red_mask_path)
            if red_mask is not None and red_mask.any():
                img = _apply_mask_array(img, red_mask, method="bgfill")

        if hw_mask_path is not None:
            hw_mask = load_gray(hw_mask_path)
            if hw_mask is not None and hw_mask.any():
                img = _apply_mask_array(img, hw_mask, method="inpaint")

        return save_bgr_jpeg(img, output_path)
    except Exception:
        return False


__all__ = ["apply_mask", "apply_masks_separately", "_apply_mask_array"]
