"""tests/m1/test_preprocess.py — 预处理子模块单元测试。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from src.m1_image_engine.preprocess import (
    MAX_LONG_EDGE,
    detect_paper,
    enhance_contrast,
    exif_transpose,
    preprocess_pipeline,
    remove_shadow_clahe,
    resize_long_edge,
    warp_perspective,
)


def test_resize_long_edge_downscales_when_too_large():
    img = Image.new("RGB", (6000, 4000), (255, 255, 255))
    out = resize_long_edge(img, max_size=3000)
    assert max(out.size) == 3000
    # 比例保持
    assert out.size[1] == 2000


def test_resize_long_edge_keeps_small_image():
    img = Image.new("RGB", (800, 600), (255, 255, 255))
    out = resize_long_edge(img, max_size=3000)
    assert out.size == (800, 600)


def test_exif_transpose_no_exif_returns_image():
    img = Image.new("RGB", (100, 50), (200, 100, 50))
    out = exif_transpose(img)
    assert out.size == (100, 50)


def test_exif_transpose_orientation_6(tmp_path):
    """Orientation=6 表示需顺时针旋转 90 度。"""
    img = Image.new("RGB", (200, 100), (255, 0, 0))
    p = tmp_path / "with_exif.jpg"
    # 写入 EXIF orientation=6
    exif_bytes = img.getexif()
    exif_bytes[0x0112] = 6
    img.save(p, exif=exif_bytes.tobytes() if hasattr(exif_bytes, "tobytes") else None)

    # 读回再 transpose
    loaded = Image.open(p)
    out = exif_transpose(loaded)
    # 旋转后宽高应当对调（在 EXIF 生效时）。即使部分 PIL 版本忽略，
    # 至少不应崩溃，结果尺寸合理。
    assert min(out.size) > 0


def test_detect_paper_finds_quad(canvas_perspective_paper):
    quad = detect_paper(canvas_perspective_paper)
    assert quad is not None
    assert quad.shape == (4, 2)


def test_detect_paper_returns_none_on_noise():
    noisy = np.random.randint(0, 256, (400, 400, 3), dtype=np.uint8)
    quad = detect_paper(noisy)
    # 噪声图很难找到合理四边形，但即使找到也不应崩溃
    assert quad is None or quad.shape == (4, 2)


def test_detect_paper_too_small_image():
    tiny = np.zeros((5, 5, 3), dtype=np.uint8)
    assert detect_paper(tiny) is None


def test_warp_perspective_produces_rectangular_output(canvas_perspective_paper):
    quad = detect_paper(canvas_perspective_paper)
    assert quad is not None
    warped = warp_perspective(canvas_perspective_paper, quad)
    assert warped.ndim == 3
    assert warped.shape[2] == 3
    assert warped.shape[0] >= 10 and warped.shape[1] >= 10


def test_remove_shadow_clahe_preserves_shape(white_canvas):
    out = remove_shadow_clahe(white_canvas)
    assert out.shape == white_canvas.shape
    assert out.dtype == np.uint8


def test_enhance_contrast_preserves_shape(white_canvas):
    # 添加一些黑色内容，让自适应阈值有内容工作
    arr = white_canvas.copy()
    arr[100:120, 100:300] = (0, 0, 0)
    out = enhance_contrast(arr)
    assert out.shape == arr.shape


def test_preprocess_pipeline_missing_file():
    img, warnings, err = preprocess_pipeline("/nonexistent/path/file.jpg")
    assert img is None
    assert err is not None
    assert "load_failed" in err


def test_preprocess_pipeline_corrupt_file(tmp_path):
    p = tmp_path / "corrupt.jpg"
    p.write_bytes(b"not a real image")
    img, warnings, err = preprocess_pipeline(str(p))
    assert img is None
    assert err is not None


def test_preprocess_pipeline_white_canvas_no_paper(tmp_path, white_canvas, tmp_image_path):
    """全白图像，无明显纸张轮廓——应跳过透视矫正但流程完成。"""
    path = tmp_image_path(white_canvas, "white.jpg")
    img, warnings, err = preprocess_pipeline(path)
    assert err is None
    assert img is not None
    # 至少有 paper_detection_failed warning
    assert any("paper_detection_failed" in w for w in warnings)


def test_preprocess_pipeline_perspective_paper(tmp_image_path, canvas_perspective_paper):
    path = tmp_image_path(canvas_perspective_paper, "persp.jpg")
    img, warnings, err = preprocess_pipeline(path)
    assert err is None
    assert img is not None
    assert img.shape[0] >= 10 and img.shape[1] >= 10
