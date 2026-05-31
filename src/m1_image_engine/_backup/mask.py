"""阶段2: 手写 / 红笔 mask 检测。

输出两张独立 mask:
- red_mask:   LAB a* 通道检测红色批注/红圈/红字
- hw_mask:    灰度 + 形态学检测铅笔/黑笔手写

不直接改图，只生成 mask 供前端和后续擦除使用。
白色 (255) = 待擦除区域, 黑色 (0) = 保留区域。
"""

from __future__ import annotations

import cv2
import numpy as np

from .utils import load_image_pil, pil_to_bgr, save_gray

# --- LAB 红色检测（比 HSV 更稳定） ---
LAB_A_RED_LO = 130   # a* 通道，正值 = 红色方向
LAB_A_RED_HI = 200
LAB_MIN_L = 30       # 过滤过暗像素
LAB_MAX_L = 220      # 过滤过亮像素

# --- 灰度手写检测 ---
HW_GRAY_MAX = 150    # 灰度值上限（暗于150才可能是手写）
HW_GRAY_MIN = 20     # 过滤过暗（避免误伤印刷实心块）
HW_MIN_AREA = 15     # 降低最小面积门槛，捕捉小笔画
HW_MAX_AREA = 15000  # 提高上限，允许较大手写区域
HW_MAX_ASPECT = 20.0 # 放宽长宽比限制

# --- 形态学 ---
MORPH_CLOSE_SIZE = 2
MORPH_DILATE_SIZE = 2

# --- 红色擦除专用：大范围膨胀 ---
RED_DILATE_LARGE = 5


def _red_mask_lab(img_bgr: np.ndarray) -> np.ndarray:
    """使用 LAB 色彩空间检测红色区域。
    
    LAB 比 HSV 更稳定：红色始终在 a* 轴正方向，不需要 wrap-around hack。
    返回 uint8 mask (0/255)。
    """
    lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
    L = lab[:, :, 0]
    A = lab[:, :, 1]

    # a* 正值 = 红色/品红方向
    red = (A > LAB_A_RED_LO) & (L > LAB_MIN_L) & (L < LAB_MAX_L)
    return (red.astype(np.uint8)) * 255


def _handwriting_mask_gray(img_bgr: np.ndarray) -> np.ndarray:
    """基于灰度的保守手写检测。

    在灰度图中找暗色细线区域，通过连通域几何过滤印刷体。
    返回 uint8 mask (0/255)。
    """
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)

    # 候选：暗但不太暗的像素
    candidate = (gray < HW_GRAY_MAX) & (gray > HW_GRAY_MIN)
    candidate_u8 = candidate.astype(np.uint8) * 255

    # 连通域过滤
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(candidate_u8, 8)
    result = np.zeros_like(candidate, dtype=np.uint8)
    if num_labels <= 1:
        return result

    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        w = int(stats[i, cv2.CC_STAT_WIDTH])
        h = int(stats[i, cv2.CC_STAT_HEIGHT])
        if w == 0 or h == 0:
            continue

        # 太小 = 噪点，过滤
        if area < HW_MIN_AREA:
            continue
        # 太大 = 可能是印刷段落/大色块，过滤
        if area > HW_MAX_AREA:
            continue
        # 极扁/极长 = 印刷横线/表格线，过滤
        aspect = max(w, h) / max(1, min(w, h))
        if aspect > HW_MAX_ASPECT:
            continue

        result[labels == i] = 255

    return result


def generate_masks(input_path: str, output_dir: str) -> dict[str, str | None]:
    """生成 red_mask 和 handwriting_mask，保存到 output_dir。

    Args:
        input_path: 预处理后图片路径
        output_dir: 输出目录

    Returns:
        {"red_mask_path": str|None, "hw_mask_path": str|None}
        None 表示生成失败
    """
    import os
    from .utils import ensure_dir

    try:
        pil = load_image_pil(input_path)
        img_bgr = pil_to_bgr(pil)
    except Exception:
        return {"red_mask_path": None, "hw_mask_path": None}

    ensure_dir(output_dir)

    # 红色 mask
    red = _red_mask_lab(img_bgr)
    if red is not None and np.count_nonzero(red) > 0:
        # 形态学：闭运算连接断续笔画，膨胀覆盖笔画周边
        k_small = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_CLOSE_SIZE, MORPH_CLOSE_SIZE))
        k_large = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (RED_DILATE_LARGE, RED_DILATE_LARGE))
        red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, k_small)
        red = cv2.dilate(red, k_large, iterations=1)
        _, red = cv2.threshold(red, 127, 255, cv2.THRESH_BINARY)

    red_path = os.path.join(output_dir, "red_mask.jpg")
    red_ok = save_gray(red, red_path) if red is not None else False

    # 手写 mask
    hw = _handwriting_mask_gray(img_bgr)
    if hw is not None and np.count_nonzero(hw) > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_CLOSE_SIZE, MORPH_CLOSE_SIZE))
        hw = cv2.morphologyEx(hw, cv2.MORPH_CLOSE, k)
        hw = cv2.dilate(hw, k, iterations=1)
        _, hw = cv2.threshold(hw, 127, 255, cv2.THRESH_BINARY)

    hw_path = os.path.join(output_dir, "handwriting_mask.jpg")
    hw_ok = save_gray(hw, hw_path) if hw is not None else False

    # 合并 mask
    combined = np.zeros_like(red if red is not None else hw, dtype=np.uint8)
    if red is not None:
        combined = cv2.bitwise_or(combined, red)
    if hw is not None:
        combined = cv2.bitwise_or(combined, hw)
    combined_path = os.path.join(output_dir, "combined_mask.jpg")
    save_gray(combined, combined_path)

    return {
        "red_mask_path": red_path if red_ok else None,
        "hw_mask_path": hw_path if hw_ok else None,
        "combined_mask_path": combined_path,
    }


def generate_mask(input_path: str, output_path: str) -> bool:
    """兼容旧接口: 生成合并 mask 并保存。"""
    import os
    result = generate_masks(input_path, os.path.dirname(output_path))
    return result.get("combined_mask_path") is not None


__all__ = ["generate_mask", "generate_masks", "_red_mask_lab", "_handwriting_mask_gray"]
