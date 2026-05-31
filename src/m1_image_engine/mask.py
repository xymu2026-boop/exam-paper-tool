"""手写 mask 生成。

策略：HSV 颜色分割（蓝/红）+ 保守的黑色/灰色启发式过滤。
输出：单通道灰度 mask，白色 (255) = 手写区域，黑色 (0) = 保留区域。

关键不变量：**宁可漏擦，不可误删**。
对于不确定是否为印刷文字的区域，必须保留（mask=0）。
"""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from .utils import load_image_pil, pil_to_bgr, save_gray

# --- HSV 阈值 ---
BLUE_HUE_LO, BLUE_HUE_HI = 100, 130
RED_HUE_LO_1, RED_HUE_HI_1 = 0, 10
RED_HUE_LO_2, RED_HUE_HI_2 = 170, 180
MIN_SATURATION = 50
MIN_VALUE = 50

# --- 黑色/灰色过滤 ---
GRAY_MAX_SATURATION = 80
GRAY_MAX_VALUE = 200
GRAY_MIN_VALUE = 30

# --- 印刷体过滤启发式 ---
MIN_HANDWRITING_AREA = 20       # < 此面积视为噪点
MAX_HANDWRITING_AREA = 5000     # > 此面积疑似印刷文字段落
MAX_ASPECT_RATIO = 15.0         # 长宽比过大视为表格线/印刷横线
THIN_STROKE_AREA_THRESH = 1000  # 大面积细笔画疑似印刷体

# --- 形态学 ---
MORPH_KERNEL_SIZE = 3


def _color_mask_hsv(hsv: np.ndarray) -> np.ndarray:
    """生成蓝色 + 红色笔迹 mask（bool）。"""
    H = hsv[:, :, 0]
    S = hsv[:, :, 1]
    V = hsv[:, :, 2]

    sv_ok = (S > MIN_SATURATION) & (V > MIN_VALUE)
    blue = (H >= BLUE_HUE_LO) & (H <= BLUE_HUE_HI) & sv_ok
    red1 = (H >= RED_HUE_LO_1) & (H <= RED_HUE_HI_1) & sv_ok
    red2 = (H >= RED_HUE_LO_2) & (H <= RED_HUE_HI_2) & sv_ok
    return blue | red1 | red2


def _estimate_stroke_width(component_mask: np.ndarray) -> float:
    """估算连通域笔画宽度：area / skeleton_length 近似 = 2 * dist_transform_max。

    使用距离变换 (distanceTransform) 求最大值的两倍作为笔画宽度估计。
    """
    if component_mask.sum() == 0:
        return 0.0
    dist = cv2.distanceTransform(component_mask.astype(np.uint8), cv2.DIST_L2, 3)
    return float(dist.max() * 2.0)


def _gray_handwriting_mask(img_bgr: np.ndarray, hsv: np.ndarray) -> np.ndarray:
    """保守的黑/灰手写 mask（bool）。

    通过连通域几何特征过滤掉印刷文字、表格线、噪点。
    """
    S = hsv[:, :, 1]
    V = hsv[:, :, 2]

    # 候选：低饱和度、中等亮度（深色但非纯黑）
    candidate = (S < GRAY_MAX_SATURATION) & (V < GRAY_MAX_VALUE) & (V > GRAY_MIN_VALUE)
    candidate_u8 = candidate.astype(np.uint8) * 255

    # 连通域分析
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(candidate_u8, 8)

    result = np.zeros_like(candidate, dtype=bool)
    if num_labels <= 1:
        return result

    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        width = int(stats[i, cv2.CC_STAT_WIDTH])
        height = int(stats[i, cv2.CC_STAT_HEIGHT])
        if width == 0 or height == 0:
            continue

        # 过滤 1: 太小 -> 噪点
        if area < MIN_HANDWRITING_AREA:
            continue
        # 过滤 2: 太大 -> 印刷段落 / 大色块
        if area > MAX_HANDWRITING_AREA:
            continue
        # 过滤 3: 长宽比极大 -> 表格线、印刷横线
        aspect = max(width, height) / max(1, min(width, height))
        if aspect > MAX_ASPECT_RATIO:
            continue
        # 过滤 4: 细笔画 + 大面积 -> 印刷体
        component = labels == i
        stroke_w = _estimate_stroke_width(component)
        if stroke_w < 1.5 and area > THIN_STROKE_AREA_THRESH:
            continue

        result |= component

    return result


def _generate_mask_array(img_bgr: np.ndarray) -> np.ndarray:
    """从 BGR 数组生成 mask（uint8, 0/255）。内部使用。"""
    if img_bgr.ndim != 3 or img_bgr.shape[2] != 3:
        raise ValueError("expect 3-channel BGR image")

    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    color = _color_mask_hsv(hsv)
    gray_hw = _gray_handwriting_mask(img_bgr, hsv)

    combined = (color | gray_hw).astype(np.uint8) * 255

    # 形态学后处理：闭运算 + 膨胀
    k = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE, (MORPH_KERNEL_SIZE, MORPH_KERNEL_SIZE)
    )
    combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, k)
    combined = cv2.dilate(combined, k, iterations=1)
    # 二值化保证只有 0 / 255
    _, combined = cv2.threshold(combined, 127, 255, cv2.THRESH_BINARY)
    return combined


def generate_mask(input_path: str, output_path: str) -> bool:
    """生成手写 mask 并保存到 output_path。

    Args:
        input_path: 预处理后图片路径
        output_path: mask 输出路径（白色=手写，黑色=保留）

    Returns:
        是否成功
    """
    try:
        pil = load_image_pil(input_path)
        img_bgr = pil_to_bgr(pil)
        mask = _generate_mask_array(img_bgr)
        return save_gray(mask, output_path)
    except Exception:
        return False


__all__ = [
    "generate_mask",
    "_generate_mask_array",
    "BLUE_HUE_LO",
    "BLUE_HUE_HI",
    "RED_HUE_LO_1",
    "RED_HUE_HI_1",
    "RED_HUE_LO_2",
    "RED_HUE_HI_2",
    "MIN_SATURATION",
    "MIN_VALUE",
]
