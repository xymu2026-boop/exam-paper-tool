"""擦除：根据 mask 移除手写内容。

支持两种方法：
- 'white': 白色填充，速度快，无伪影，适合白底试卷（默认）
- 'inpaint': cv2.inpaint(TELEA)，适合带网格/底纹的试卷
"""

from __future__ import annotations

import cv2
import numpy as np

from .utils import load_bgr, load_gray, save_bgr_jpeg


def _apply_mask_array(
    img_bgr: np.ndarray, mask_gray: np.ndarray, method: str = "white"
) -> np.ndarray:
    """对 BGR 数组应用 mask 擦除，返回新数组。内部使用。

    Raises:
        ValueError: method 不合法
    """
    if img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        raise ValueError("expect 3-channel BGR image")
    if mask_gray.ndim != 2:
        raise ValueError("expect single-channel mask")

    # 尺寸不匹配时 resize mask
    if mask_gray.shape[:2] != img_bgr.shape[:2]:
        mask_gray = cv2.resize(
            mask_gray,
            (img_bgr.shape[1], img_bgr.shape[0]),
            interpolation=cv2.INTER_NEAREST,
        )

    if mask_gray.dtype != np.uint8:
        mask_gray = mask_gray.astype(np.uint8)

    if method == "white":
        result = img_bgr.copy()
        result[mask_gray > 127] = (255, 255, 255)
        return result

    if method == "inpaint":
        inpaint_mask = ((mask_gray > 127).astype(np.uint8)) * 255
        return cv2.inpaint(img_bgr, inpaint_mask, 3, cv2.INPAINT_TELEA)

    raise ValueError(f"unknown method: {method!r}")


def apply_mask(
    input_path: str, mask_path: str, output_path: str, method: str = "white"
) -> bool:
    """擦除手写并保存结果。

    Args:
        input_path: 预处理后图片路径
        mask_path: mask 图片路径
        output_path: 擦除结果输出路径
        method: 'white' | 'inpaint'

    Returns:
        是否成功
    """
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


__all__ = ["apply_mask", "_apply_mask_array"]
