"""tests/m1/test_mask.py — HSV mask 生成测试。"""

from __future__ import annotations

import numpy as np

from src.m1_image_engine.mask import _generate_mask_array, generate_mask


def test_blue_pen_detected(canvas_with_blue_handwriting):
    mask = _generate_mask_array(canvas_with_blue_handwriting)
    assert mask.dtype == np.uint8
    # mask 应该有 > 0 的像素
    assert int((mask > 127).sum()) > 0
    # 蓝色矩形中心 (120, 120) 应该被标记
    assert mask[120, 120] > 127


def test_red_pen_detected(canvas_with_red_handwriting):
    mask = _generate_mask_array(canvas_with_red_handwriting)
    # 红色区域 (140, 140) 应该被标记
    assert mask[140, 140] > 127


def test_white_canvas_no_mask(white_canvas):
    mask = _generate_mask_array(white_canvas)
    # 全白画布应几乎全 0
    assert int((mask > 127).sum()) == 0


def test_table_lines_preserved(canvas_with_table_lines):
    """长黑色横线（长宽比极大）应该被识别为印刷线条保留。"""
    mask = _generate_mask_array(canvas_with_table_lines)
    # 大部分横线像素应不在 mask 中
    line_region = mask[100:103, 50:750]
    # 至少 80% 不在 mask 中
    keep_ratio = (line_region <= 127).sum() / line_region.size
    assert keep_ratio > 0.8, f"table lines were erased: keep_ratio={keep_ratio}"


def test_printed_text_block_preserved(canvas_with_printed_text_block):
    """大块黑色（印刷段落）应该被保留。"""
    mask = _generate_mask_array(canvas_with_printed_text_block)
    # 块状黑色区域大部分应不在 mask 中
    block_region = mask[200:300, 200:300]
    keep_ratio = (block_region <= 127).sum() / block_region.size
    assert keep_ratio > 0.8, f"printed block was erased: keep_ratio={keep_ratio}"


def test_mask_is_binary(canvas_with_blue_handwriting):
    """mask 值只能是 0 或 255。"""
    mask = _generate_mask_array(canvas_with_blue_handwriting)
    unique_vals = set(np.unique(mask).tolist())
    assert unique_vals.issubset({0, 255})


def test_mask_shape_matches_input(canvas_with_blue_handwriting):
    mask = _generate_mask_array(canvas_with_blue_handwriting)
    assert mask.shape == canvas_with_blue_handwriting.shape[:2]


def test_generate_mask_io(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "blue.jpg")
    out_path = str(tmp_path / "mask.png")
    ok = generate_mask(in_path, out_path)
    assert ok is True
    from src.m1_image_engine.utils import load_gray

    m = load_gray(out_path)
    assert m is not None
    assert m.shape == canvas_with_blue_handwriting.shape[:2]
    assert int((m > 127).sum()) > 0


def test_generate_mask_missing_file(tmp_path):
    ok = generate_mask("/nonexistent/file.jpg", str(tmp_path / "mask.png"))
    assert ok is False


def test_invalid_input_raises():
    """非 3 通道图像应抛错。"""
    import pytest

    bad = np.zeros((100, 100), dtype=np.uint8)
    with pytest.raises(ValueError):
        _generate_mask_array(bad)
