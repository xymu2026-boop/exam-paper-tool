"""质量评分。

三维加权综合：
- erase_coverage (0.3): mask 区域被擦白的比例
- text_preservation (0.5): 非 mask 区域的像素未被破坏的比例（最关键）
- cleanliness (0.2): 擦除后视觉干净度（白色占比 + 噪点数）

总分 0.0~1.0，>= 0.6 视为可打印。
"""

from __future__ import annotations

import cv2
import numpy as np

ERASE_COVERAGE_WEIGHT = 0.30
TEXT_PRESERVATION_WEIGHT = 0.50
CLEANLINESS_WEIGHT = 0.20

NOISE_AREA_THRESH = 50
NOISE_COUNT_NORMALIZER = 500.0


def _compute_erase_coverage(cleaned_bgr: np.ndarray, mask_gray: np.ndarray) -> float:
    mask_bool = mask_gray > 127
    total = int(mask_bool.sum())
    if total == 0:
        return 1.0
    cleaned_white = np.all(cleaned_bgr >= 240, axis=2)
    erased = int((mask_bool & cleaned_white).sum())
    return erased / float(total)


def _compute_text_preservation(
    original_bgr: np.ndarray, cleaned_bgr: np.ndarray, mask_gray: np.ndarray
) -> float:
    mask_bool = mask_gray > 127
    keep_bool = ~mask_bool
    total_keep = int(keep_bool.sum())
    if total_keep == 0:
        return 0.0
    diff = cv2.absdiff(original_bgr, cleaned_bgr)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    changed = int(((diff_gray > 15) & keep_bool).sum())
    change_ratio = changed / float(total_keep)
    # 每 10% 误改 -> 1.0 分降到 0
    return max(0.0, 1.0 - change_ratio * 10.0)


def _compute_cleanliness(cleaned_bgr: np.ndarray) -> float:
    gray = cv2.cvtColor(cleaned_bgr, cv2.COLOR_BGR2GRAY)
    # 白色占比
    white_ratio = float((gray >= 250).sum()) / float(gray.size)

    # 孤立噪点：反转后二值化 + 连通域统计小面积块数
    inverted = 255 - gray
    _, binary = cv2.threshold(inverted, 15, 255, cv2.THRESH_BINARY)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    noise_count = 0
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < NOISE_AREA_THRESH:
            noise_count += 1
    noise_score = max(0.0, 1.0 - noise_count / NOISE_COUNT_NORMALIZER)

    return 0.6 * white_ratio + 0.4 * noise_score


def score_quality(
    original_bgr: np.ndarray, cleaned_bgr: np.ndarray, mask_gray: np.ndarray
) -> float:
    """计算综合质量分。

    Args:
        original_bgr: 预处理后的图像（擦除前）
        cleaned_bgr: 擦除后的图像
        mask_gray: 手写 mask (单通道 uint8)

    Returns:
        综合分 0.0~1.0
    """
    if original_bgr.shape != cleaned_bgr.shape:
        return 0.0
    if mask_gray.shape[:2] != original_bgr.shape[:2]:
        return 0.0

    erase = _compute_erase_coverage(cleaned_bgr, mask_gray)
    preserve = _compute_text_preservation(original_bgr, cleaned_bgr, mask_gray)
    clean = _compute_cleanliness(cleaned_bgr)

    score = (
        ERASE_COVERAGE_WEIGHT * erase
        + TEXT_PRESERVATION_WEIGHT * preserve
        + CLEANLINESS_WEIGHT * clean
    )
    return float(np.clip(score, 0.0, 1.0))


__all__ = [
    "score_quality",
    "ERASE_COVERAGE_WEIGHT",
    "TEXT_PRESERVATION_WEIGHT",
    "CLEANLINESS_WEIGHT",
]
