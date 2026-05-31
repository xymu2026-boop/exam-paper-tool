"""图像预处理管线 — V2: 轻量化预处理。

按顺序：
  1. EXIF 旋转修正
  2. 长边缩放 (max 3000px)
  3. 自动纠偏 (基于边缘主方向)
  4. 裁掉四周黑边 (保守阈值, 不切内容)
  5. 纸张检测 + 透视矫正 (保留原有逻辑但更容错)
  6. 轻量去阴影 (CLAHE tile 16x16, clip 1.2)
  7. ~~不再做二值化/自适应增强~~ ← V2 关键变更

目标: 保留灰度细节, 不做过度增强, 让后续 mask 检测在接近原始画质上工作。
"""

from __future__ import annotations

import math
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageOps

# --- 常量 ---
MAX_LONG_EDGE = 3000
CLAHE_CLIP_LIMIT = 1.2  # 从 2.0 降到 1.2, 避免放大纸纹理
CLAHE_TILE_SIZE = (16, 16)  # 从 8x8 扩到 16x16, 减少局部过增强
MIN_PAPER_AREA_RATIO = 0.30
# 去黑边: 灰度值 < 阈值 且 该行/列占比 > 比例则裁切
BORDER_DARK_THRESH = 40
BORDER_DARK_RATIO = 0.85


def exif_transpose(img: Image.Image) -> Image.Image:
    """根据 EXIF Orientation 旋转/镜像图片。"""
    try:
        return ImageOps.exif_transpose(img)
    except Exception:
        return img


def resize_long_edge(img: Image.Image, max_size: int = MAX_LONG_EDGE) -> Image.Image:
    """长边超过 max_size 时按比例缩放。"""
    w, h = img.size
    long_edge = max(w, h)
    if long_edge <= max_size:
        return img
    scale = max_size / float(long_edge)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return img.resize((new_w, new_h), Image.LANCZOS)


# --- 自动纠偏 (deskew) ---

def _compute_skew_angle(gray: np.ndarray) -> float:
    """用边缘检测 + HoughLines 估计旋转角度。返回角度(度), 正=逆时针。"""
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return 0.0
    angles = []
    for rho_theta in lines:
        rho, theta = rho_theta[0]
        # 只统计接近水平/垂直的线
        deg = math.degrees(theta)
        # 水平线: 接近 0° 或 180°
        if deg < 2 or deg > 178:
            angles.append(0.0)
            continue
        # 垂直线: 接近 90°
        if 88 < deg < 92:
            continue
        # 近水平线: 取与水平线的夹角
        if deg < 45:
            angles.append(deg)
        elif deg > 135:
            angles.append(deg - 180)
        # 其他角度忽略
    if not angles:
        return 0.0
    # 取中位数, 限制在 ±5°
    median_angle = float(np.median(angles))
    return max(-5.0, min(5.0, median_angle))


def deskew(img_bgr: np.ndarray) -> np.ndarray:
    """自动纠偏, 返回旋转后的 BGR 图像。"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    angle = _compute_skew_angle(gray)
    if abs(angle) < 0.3:
        return img_bgr
    h, w = img_bgr.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        img_bgr, M, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


# --- 裁掉黑边 ---

def crop_dark_borders(img_bgr: np.ndarray) -> np.ndarray:
    """裁掉四周接近全黑的边 (扫描仪黑边)。保守: 只裁明显全黑区域。"""
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # 从上往下找第一行非黑
    top = 0
    for y in range(h):
        dark_count = int((gray[y] < BORDER_DARK_THRESH).sum())
        if dark_count / w < BORDER_DARK_RATIO:
            top = y
            break

    # 从下往上
    bottom = h - 1
    for y in range(h - 1, -1, -1):
        dark_count = int((gray[y] < BORDER_DARK_THRESH).sum())
        if dark_count / w < BORDER_DARK_RATIO:
            bottom = y + 1
            break

    # 从左
    left = 0
    for x in range(w):
        dark_count = int((gray[:, x] < BORDER_DARK_THRESH).sum())
        if dark_count / h < BORDER_DARK_RATIO:
            left = x
            break

    # 从右
    right = w - 1
    for x in range(w - 1, -1, -1):
        dark_count = int((gray[:, x] < BORDER_DARK_THRESH).sum())
        if dark_count / h < BORDER_DARK_RATIO:
            right = x + 1
            break

    # 保守: 至少保留 80% 的原始尺寸
    if bottom - top < h * 0.8 or right - left < w * 0.8:
        return img_bgr
    if top == 0 and bottom == h and left == 0 and right == w:
        return img_bgr
    return img_bgr[top:bottom, left:right]


# --- 纸张检测 (保留原逻辑) ---

def _order_quad(pts: np.ndarray) -> np.ndarray:
    """将四个点排序为 [tl, tr, br, bl]。"""
    pts = pts.reshape(4, 2).astype(np.float32)
    rect = np.zeros((4, 2), dtype=np.float32)
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def detect_paper(img_bgr: np.ndarray) -> Optional[np.ndarray]:
    """检测最大的四边形轮廓。返回 4x2 float32 数组或 None。"""
    try:
        h, w = img_bgr.shape[:2]
        if h < 10 or w < 10:
            return None
        gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(
            edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        if not contours:
            return None
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


# --- 去阴影 (轻量) ---

def remove_shadow_clahe(img_bgr: np.ndarray) -> np.ndarray:
    """LAB 色彩空间中对 L 通道应用轻度 CLAHE。"""
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    L, A, B = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP_LIMIT, tileGridSize=CLAHE_TILE_SIZE)
    L2 = clahe.apply(L)
    return cv2.cvtColor(cv2.merge([L2, A, B]), cv2.COLOR_LAB2BGR)


# --- 主管线 ---

def preprocess_pipeline(input_path: str) -> tuple[Optional[np.ndarray], list[str], Optional[str]]:
    """V2 预处理管线。

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

    # Step 4: 自动纠偏
    try:
        img = deskew(img)
    except Exception as e:
        warnings.append(f"deskew_failed: {e}")

    # Step 5: 裁黑边
    try:
        img = crop_dark_borders(img)
    except Exception as e:
        warnings.append(f"border_crop_failed: {e}")

    # Step 6: 纸张检测 + 透视矫正 (容错)
    quad = detect_paper(img)
    if quad is not None:
        try:
            warped = warp_perspective(img, quad)
            if warped.shape[0] >= 10 and warped.shape[1] >= 10:
                img = warped
            else:
                warnings.append("paper_detection_failed: warped result too small")
        except Exception as e:
            warnings.append(f"perspective_failed: {e}")
    else:
        warnings.append("paper_detection_failed: skipped perspective correction")

    # Step 7: 轻量去阴影
    try:
        img = remove_shadow_clahe(img)
    except Exception as e:
        warnings.append(f"shadow_removal_failed: {e}")

    # V2 关键: 不再做 enhance_contrast (自适应阈值增强)
    # 保留图像的灰度细节, 给后续 mask 检测一个干净的输入

    return img, warnings, None


__all__ = [
    "MAX_LONG_EDGE",
    "MIN_PAPER_AREA_RATIO",
    "exif_transpose",
    "resize_long_edge",
    "deskew",
    "crop_dark_borders",
    "detect_paper",
    "warp_perspective",
    "remove_shadow_clahe",
    "preprocess_pipeline",
]
