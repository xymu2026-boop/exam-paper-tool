"""图像预处理管线。

按顺序：EXIF 修正 -> 长边缩放 -> 纸张检测 -> 透视矫正 -> CLAHE 去阴影 -> 自适应阈值增强。
所有非致命错误以 warning 形式返回，调用方决定如何展示。
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

# --- 常量 ---
MAX_LONG_EDGE = 3000
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)
ADAPTIVE_THRESH_BLOCK = 11
ADAPTIVE_THRESH_C = 2
MIN_PAPER_AREA_RATIO = 0.30


def exif_transpose(img: Image.Image) -> Image.Image:
    """根据 EXIF Orientation 旋转/镜像图片。"""
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        # 极少数情况下 EXIF 解析失败，退回原图
        return img


def resize_long_edge(img: Image.Image, max_size: int = MAX_LONG_EDGE) -> Image.Image:
    """长边超过 max_size 时按比例缩放，否则原样返回。"""
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= max_size:
        return img
    scale = max_size / float(long_edge)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return img.resize((new_w, new_h), Image.LANCZOS)


def _order_quad(pts: np.ndarray) -> np.ndarray:
    """将四个点排序为 [tl, tr, br, bl]。"""
    pts = pts.reshape(4, 2).astype(np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]  # top-left
    rect[2] = pts[np.argmax(s)]  # bottom-right
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]  # top-right
    rect[3] = pts[np.argmax(diff)]  # bottom-left
    return rect


def detect_paper(img_bgr: np.ndarray) -> Optional[np.ndarray]:
    """检测最大的四边形轮廓。

    返回 4x2 float32 数组（已排序 tl/tr/br/bl），未找到时返回 None。
    """
    try:
        h, w = img_bgr.shape[:2]
        if h < 10 or w < 10:
            return None
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        # 闭运算填补断裂的边
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None
        # 按面积降序，尝试前 5 个
        contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]
        img_area = float(h * w)
        for cnt in contours:
            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
            if len(approx) == 4 and cv2.isContourConvex(approx):
                area = cv2.contourArea(approx)
                if area / img_area >= MIN_PAPER_AREA_RATIO:
                    return _order_quad(approx)
        return None
    except Exception:
        return None


def warp_perspective(img_bgr: np.ndarray, quad: np.ndarray) -> np.ndarray:
    """对四边形区域做透视矫正。"""
    rect = quad.astype(np.float32)
    (tl, tr, br, bl) = rect
    width_top = np.linalg.norm(tr - tl)
    width_bottom = np.linalg.norm(br - bl)
    height_left = np.linalg.norm(bl - tl)
    height_right = np.linalg.norm(br - tr)
    max_w = int(max(width_top, width_bottom))
    max_h = int(max(height_left, height_right))
    if max_w < 10 or max_h < 10:
        return img_bgr
    dst = np.array(
        [[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]],
        dtype=np.float32,
    )
    M = cv2.getPerspectiveTransform(rect, dst)
    return cv2.warpPerspective(img_bgr, M, (max_w, max_h))


def remove_shadow_clahe(img_bgr: np.ndarray) -> np.ndarray:
    """LAB 色彩空间中对 L 通道应用 CLAHE 去除不均匀光照。"""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
    L2 = clahe.apply(L)
    return cv2.cvtColor(cv2.merge([L2, A, B]), cv2.COLOR_LAB2BGR)


def enhance_contrast(img_bgr: np.ndarray) -> np.ndarray:
    """二值化增强：用自适应阈值生成的灰度图与原图做软合并，提升印刷文字对比度。

    返回仍为 BGR uint8 图像（保留色彩信息），仅整体对比度增强。
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    # 自适应阈值得到“文字 mask”
    block = ADAPTIVE_THRESH_BLOCK if ADAPTIVE_THRESH_BLOCK % 2 == 1 else ADAPTIVE_THRESH_BLOCK + 1
    binary = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        block,
        ADAPTIVE_THRESH_C,
    )
    # 软合并：原图 + 文字深化
    # 在 binary==0 (文字) 的区域适度加深；其余保持原色
    dark_mask = (binary == 0).astype(np.uint8)
    # 增强系数 0.8 表示文字区域亮度降到原来 80%
    enhanced = img_bgr.copy()
    enhanced[dark_mask == 1] = (enhanced[dark_mask == 1].astype(np.int32) * 0.8).astype(np.uint8)
    return enhanced


def preprocess_pipeline(input_path: str) -> tuple[Optional[np.ndarray], list[str], Optional[str]]:
    """主预处理管线。

    Returns:
        (bgr_image, warnings, error)
        - bgr_image 为 None 时表示致命错误
        - warnings 为非致命问题列表
        - error 为致命错误描述（成功时为 None）
    """
    from .utils import HEIC_SUPPORTED, is_heic, load_image_pil, pil_to_bgr

    warnings: list[str] = []

    # Step 1: 加载
    try:
        pil = load_image_pil(input_path)
    except FileNotFoundError as e:
        return None, warnings, f"load_failed: {e}"
    except RuntimeError as e:
        # HEIC 不支持的情况
        return None, warnings, str(e)
    except Exception as e:
        return None, warnings, f"load_failed: {e}"

    if is_heic(input_path) and not HEIC_SUPPORTED:  # 双保险
        return None, warnings, "HEIC not supported: install pillow-heif"

    # Step 2: EXIF
    try:
        pil = exif_transpose(pil)
    except Exception as e:
        warnings.append(f"exif_failed: {e}")

    # Step 3: 缩放
    pil = resize_long_edge(pil, MAX_LONG_EDGE)

    img = pil_to_bgr(pil)

    # Step 4-5: 纸张检测 + 透视矫正（容错）
    quad = detect_paper(img)
    if quad is not None:
        try:
            warped = warp_perspective(img, quad)
            if warped.shape[0] >= 10 and warped.shape[1] >= 10:
                img = warped
            else:
                warnings.append(
                    "paper_detection_failed: warped result too small, skipped"
                )
        except Exception as e:
            warnings.append(f"perspective_failed: {e}")
    else:
        warnings.append("paper_detection_failed: skipped perspective correction")

    # Step 6: 去阴影
    try:
        img = remove_shadow_clahe(img)
    except Exception as e:
        warnings.append(f"shadow_removal_failed: {e}")

    # Step 7: 二值化增强
    try:
        img = enhance_contrast(img)
    except Exception as e:
        warnings.append(f"contrast_enhancement_failed: {e}")

    return img, warnings, None


__all__ = [
    "MAX_LONG_EDGE",
    "MIN_PAPER_AREA_RATIO",
    "exif_transpose",
    "resize_long_edge",
    "detect_paper",
    "warp_perspective",
    "remove_shadow_clahe",
    "enhance_contrast",
    "preprocess_pipeline",
]
