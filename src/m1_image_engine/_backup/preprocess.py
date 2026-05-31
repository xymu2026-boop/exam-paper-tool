"""阶段1: 轻量预处理。

只做：EXIF修正 -> 长边缩放 -> 裁掉黑边 -> 轻微去阴影。
不做：强二值化、锐化、对比度增强。
保留灰度细节，背景不能比原图更脏。
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

MAX_LONG_EDGE = 3000
CLAHE_CLIP_LIMIT = 1.2        # 从 2.0 降到 1.2，更温和
CLAHE_TILE_SIZE = (16, 16)     # 从 8x8 放大到 16x16，减少局部过增强
BORDER_CROP_MARGIN = 5         # 裁边像素


def exif_transpose(img: Image.Image) -> Image.Image:
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def resize_long_edge(img: Image.Image, max_size: int = MAX_LONG_EDGE) -> Image.Image:
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= max_size:
        return img
    scale = max_size / float(long_edge)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return img.resize((new_w, new_h), Image.LANCZOS)


def crop_black_border(img_bgr: np.ndarray, margin: int = BORDER_CROP_MARGIN) -> np.ndarray:
    """裁掉四周纯黑/近黑边缘（手机拍照黑边）。"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 15, 255, cv2.THRESH_BINARY)
    coords = cv2.findNonZero(thresh)
    if coords is None:
        return img_bgr
    x, y, w, h = cv2.boundingRect(coords)
    x = max(0, x - margin)
    y = max(0, y - margin)
    w = min(img_bgr.shape[1] - x, w + 2 * margin)
    h = min(img_bgr.shape[0] - y, h + 2 * margin)
    return img_bgr[y:y+h, x:x+w]


def remove_shadow_mild(img_bgr: np.ndarray) -> np.ndarray:
    """LAB L通道 CLAHE，大tile + 低clip，温和去阴影不引入噪点。"""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
    L2 = clahe.apply(L)
    return cv2.cvtColor(cv2.merge([L2, A, B]), cv2.COLOR_LAB2BGR)


def preprocess_pipeline(input_path: str) -> tuple[Optional[np.ndarray], list[str], Optional[str]]:
    """轻量预处理管线。

    Returns:
        (bgr_image, warnings, error)
    """
    from .utils import HEIC_SUPPORTED, is_heic, load_image_pil, pil_to_bgr

    warnings: list[str] = []

    # Step 1: 加载
    try:
        pil = load_image_pil(input_path)
    except FileNotFoundError as e:
        return None, warnings, f"load_failed: {e}"
    except RuntimeError as e:
        return None, warnings, str(e)
    except Exception as e:
        return None, warnings, f"load_failed: {e}"

    if is_heic(input_path) and not HEIC_SUPPORTED:
        return None, warnings, "HEIC not supported: install pillow-heif"

    # Step 2: EXIF
    try:
        pil = exif_transpose(pil)
    except Exception as e:
        warnings.append(f"exif_failed: {e}")

    # Step 3: 缩放
    pil = resize_long_edge(pil, MAX_LONG_EDGE)

    img = pil_to_bgr(pil)

    # Step 4: 裁黑边
    try:
        img = crop_black_border(img)
    except Exception as e:
        warnings.append(f"crop_border_failed: {e}")

    # Step 5: 温和去阴影（不增强对比度，不二值化）
    try:
        img = remove_shadow_mild(img)
    except Exception as e:
        warnings.append(f"shadow_removal_failed: {e}")

    return img, warnings, None


__all__ = [
    "MAX_LONG_EDGE", "CLAHE_CLIP_LIMIT", "CLAHE_TILE_SIZE",
    "exif_transpose", "resize_long_edge", "crop_black_border",
    "remove_shadow_mild", "preprocess_pipeline",
]
