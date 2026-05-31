"""测试用例的合成图像 fixtures。

不依赖真实样本，可在 CI 中运行。
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest
from PIL import Image

# 让 tests 模块可以 import 项目源码
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _make_white_canvas(w: int = 800, h: int = 600) -> np.ndarray:
    """白底 BGR 画布。"""
    return np.full((h, w, 3), 255, dtype=np.uint8)


def _draw_rect_bgr(arr: np.ndarray, x: int, y: int, w: int, h: int, color_bgr: tuple[int, int, int]) -> None:
    arr[y : y + h, x : x + w] = color_bgr


@pytest.fixture
def tmp_image_path(tmp_path):
    """工厂 fixture：保存一个 BGR 数组到临时 jpg 路径。"""
    counter = {"i": 0}

    def _save(arr: np.ndarray, name: str | None = None) -> str:
        counter["i"] += 1
        fname = name or f"img_{counter['i']}.jpg"
        full = str(tmp_path / fname)
        # BGR -> RGB -> PIL save
        from src.m1_image_engine.utils import bgr_to_pil

        bgr_to_pil(arr).save(full, "JPEG", quality=95)
        return full

    return _save


@pytest.fixture
def white_canvas():
    """800x600 全白 BGR 画布。"""
    return _make_white_canvas(800, 600)


@pytest.fixture
def canvas_with_blue_handwriting():
    """白底 + 多笔蓝色手写。"""
    arr = _make_white_canvas(800, 600)
    # 多个蓝色矩形模拟蓝笔字
    _draw_rect_bgr(arr, 100, 100, 40, 40, (200, 50, 30))   # BGR 蓝
    _draw_rect_bgr(arr, 200, 150, 30, 30, (200, 50, 30))
    _draw_rect_bgr(arr, 350, 250, 50, 50, (200, 50, 30))
    return arr


@pytest.fixture
def canvas_with_red_handwriting():
    """白底 + 红色手写。"""
    arr = _make_white_canvas(800, 600)
    # BGR red
    _draw_rect_bgr(arr, 120, 120, 40, 40, (30, 30, 200))
    _draw_rect_bgr(arr, 250, 200, 35, 35, (30, 30, 200))
    return arr


@pytest.fixture
def canvas_with_table_lines():
    """白底 + 黑色横线（模拟印刷表格线）。

    线条很长（长宽比极大），应该被识别为印刷体保留。
    """
    arr = _make_white_canvas(800, 600)
    # 三条粗黑横线
    arr[100:103, 50:750] = (0, 0, 0)
    arr[200:203, 50:750] = (0, 0, 0)
    arr[300:303, 50:750] = (0, 0, 0)
    return arr


@pytest.fixture
def canvas_with_printed_text_block():
    """白底 + 大块黑色（模拟印刷文字段落）。"""
    arr = _make_white_canvas(800, 600)
    # 一个大块连通的黑色区域 (100x100)
    arr[200:300, 200:300] = (20, 20, 20)
    return arr


@pytest.fixture
def canvas_perspective_paper(tmp_path):
    """模拟一张倾斜放置的白色纸张（以深色为背景）。

    Returns: BGR 数组
    """
    # 1200x900 深灰背景
    arr = np.full((900, 1200, 3), 40, dtype=np.uint8)
    # 中央放置一个大白色四边形：占据约 60% 面积
    pts = np.array([[200, 150], [1000, 200], [1050, 750], [150, 700]], dtype=np.int32)
    import cv2

    cv2.fillPoly(arr, [pts], (255, 255, 255))
    return arr


@pytest.fixture
def small_image():
    """很小的图像（10x10），测试边界情况。"""
    return _make_white_canvas(10, 10)


@pytest.fixture
def all_black_image():
    """全黑图像。"""
    return np.zeros((400, 400, 3), dtype=np.uint8)


@pytest.fixture
def make_canvas():
    """工厂：让测试根据需要生成尺寸不同的画布。"""

    def _f(w: int, h: int, color: tuple[int, int, int] = (255, 255, 255)) -> np.ndarray:
        arr = np.full((h, w, 3), 0, dtype=np.uint8)
        arr[:, :] = color
        return arr

    return _f
