"""tests/m1/test_quality.py — 三维质量评分测试。"""

from __future__ import annotations

import numpy as np

from src.m1_image_engine.quality import score_quality


def test_perfect_clean_empty_mask():
    """无手写 mask，cleaned 完全等于 original，应接近满分。"""
    img = np.full((100, 100, 3), 255, dtype=np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    score = score_quality(img, img, mask)
    assert 0.9 <= score <= 1.0


def test_poor_erase_score():
    """mask 全白但 cleaned 未变化 -> erase_coverage = 0。"""
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    mask = np.full((100, 100), 255, dtype=np.uint8)
    # cleaned 与 original 完全一样
    score = score_quality(img, img, mask)
    # erase = 0, preserve = 1.0 (no diff), cleanliness 低（没有白）
    # 总分应较低
    assert score < 0.6


def test_perfect_erase_score():
    """完美擦除：mask 全白，cleaned 全白。"""
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    mask = np.full((100, 100), 255, dtype=np.uint8)
    cleaned = np.full((100, 100, 3), 255, dtype=np.uint8)
    score = score_quality(img, cleaned, mask)
    # erase=1, preserve=N/A(全 mask), cleanliness 高
    # 注意：全 mask 时 keep_bool 为空 -> preserve=0
    # 总分约 0.3 * 1.0 + 0.5 * 0.0 + 0.2 * ~1.0 ≈ 0.5
    assert 0.4 < score < 0.7


def test_text_damage_score():
    """大量非 mask 区域被改 -> preserve 低。"""
    original = np.full((100, 100, 3), 100, dtype=np.uint8)
    cleaned = np.full((100, 100, 3), 200, dtype=np.uint8)  # 整体大变
    mask = np.zeros((100, 100), dtype=np.uint8)  # 无手写
    score = score_quality(original, cleaned, mask)
    # preserve 维度被严重惩罚
    assert score < 0.5


def test_score_range_clipped():
    """任何情况下分数都在 [0, 1] 范围。"""
    img = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
    cleaned = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
    mask = np.random.randint(0, 2, (50, 50), dtype=np.uint8) * 255
    score = score_quality(img, cleaned, mask)
    assert 0.0 <= score <= 1.0


def test_score_shape_mismatch_returns_zero():
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    cleaned = np.full((50, 50, 3), 50, dtype=np.uint8)
    mask = np.zeros((100, 100), dtype=np.uint8)
    score = score_quality(img, cleaned, mask)
    assert score == 0.0


def test_realistic_blue_handwriting_score(canvas_with_blue_handwriting):
    """真实场景：白底蓝字 -> 擦除后应得到合理分数。"""
    from src.m1_image_engine.eraser import _apply_mask_array
    from src.m1_image_engine.mask import _generate_mask_array

    original = canvas_with_blue_handwriting
    mask = _generate_mask_array(original)
    cleaned = _apply_mask_array(original, mask, method="white")
    score = score_quality(original, cleaned, mask)
    # 这种简单场景，分数应该比较高
    assert score >= 0.6, f"realistic score too low: {score}"


def test_returns_float():
    img = np.full((50, 50, 3), 200, dtype=np.uint8)
    mask = np.zeros((50, 50), dtype=np.uint8)
    score = score_quality(img, img, mask)
    assert isinstance(score, float)
