"""tests/m1/test_eraser.py — 擦除方法测试。"""

from __future__ import annotations

import numpy as np
import pytest

from src.m1_image_engine.eraser import _apply_mask_array, apply_mask
from src.m1_image_engine.utils import load_bgr, save_gray


def _make_mask(h: int, w: int, x0: int, y0: int, mw: int, mh: int) -> np.ndarray:
    mask = np.zeros((h, w), dtype=np.uint8)
    mask[y0 : y0 + mh, x0 : x0 + mw] = 255
    return mask


def test_white_fill_method():
    img = np.full((100, 100, 3), 50, dtype=np.uint8)  # 深灰
    mask = _make_mask(100, 100, 20, 20, 40, 40)
    out = _apply_mask_array(img, mask, method="white")
    # mask 区域应当是 (255,255,255)
    assert np.all(out[30, 30] == 255)
    # mask 外保持原色
    assert np.all(out[5, 5] == 50)
    # 原图未被修改
    assert np.all(img[30, 30] == 50)


def test_inpaint_method_no_crash():
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    mask = _make_mask(100, 100, 20, 20, 40, 40)
    out = _apply_mask_array(img, mask, method="inpaint")
    assert out.shape == img.shape
    assert out.dtype == np.uint8


def test_invalid_method_raises():
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    mask = _make_mask(100, 100, 20, 20, 40, 40)
    with pytest.raises(ValueError):
        _apply_mask_array(img, mask, method="blur")


def test_mask_size_mismatch_resized():
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    small_mask = np.full((50, 50), 255, dtype=np.uint8)
    out = _apply_mask_array(img, small_mask, method="white")
    # 整图应被擦白
    assert np.all(out == 255)


def test_apply_mask_io(tmp_path, tmp_image_path):
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    in_path = tmp_image_path(img, "in.jpg")

    mask = _make_mask(100, 100, 20, 20, 40, 40)
    mask_path = str(tmp_path / "m.png")
    save_gray(mask, mask_path)

    out_path = str(tmp_path / "out.jpg")
    ok = apply_mask(in_path, mask_path, out_path, method="white")
    assert ok is True

    cleaned = load_bgr(out_path)
    assert cleaned is not None
    # JPEG 有损，允许 ±15 范围
    assert cleaned[30, 30, 0] > 240


def test_apply_mask_invalid_method_returns_false(tmp_path, tmp_image_path):
    img = np.full((100, 100, 3), 50, dtype=np.uint8)
    in_path = tmp_image_path(img, "in.jpg")
    mask = _make_mask(100, 100, 20, 20, 40, 40)
    mask_path = str(tmp_path / "m.png")
    save_gray(mask, mask_path)

    out_path = str(tmp_path / "out.jpg")
    ok = apply_mask(in_path, mask_path, out_path, method="zzz")
    assert ok is False


def test_apply_mask_missing_input(tmp_path):
    ok = apply_mask("/nope.jpg", "/nope.png", str(tmp_path / "out.jpg"))
    assert ok is False


def test_apply_mask_default_method_is_white(tmp_path, tmp_image_path):
    img = np.full((50, 50, 3), 100, dtype=np.uint8)
    in_path = tmp_image_path(img, "in.jpg")
    mask = np.full((50, 50), 255, dtype=np.uint8)
    mask_path = str(tmp_path / "m.png")
    save_gray(mask, mask_path)
    out_path = str(tmp_path / "out.jpg")
    # 默认 method 应当为 'white'
    ok = apply_mask(in_path, mask_path, out_path)
    assert ok is True
    cleaned = load_bgr(out_path)
    assert cleaned is not None
    # 应当变白
    assert cleaned[25, 25, 0] > 240
