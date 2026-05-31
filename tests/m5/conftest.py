"""Test fixtures for M5: synthetic image generation.

We avoid using real photos so the suite stays deterministic, fast, and
self-contained. Each fixture returns absolute paths under ``tmp_path``.
"""

from __future__ import annotations

import os
from typing import List

import pytest
from PIL import Image


# (width, height, color, filename)
SAMPLE_SPECS = [
    (800, 600, "red", "img_0.png"),
    (1200, 900, "blue", "img_1.png"),
    (600, 800, "green", "img_2.png"),
    (1000, 1000, "yellow", "img_3.png"),
    (1600, 1200, "purple", "img_4.png"),  # landscape — exercises auto-rotate
]


def _make_image(path: str, width: int, height: int, color: str) -> str:
    Image.new("RGB", (width, height), color).save(path)
    return path


@pytest.fixture
def sample_images(tmp_path) -> List[str]:
    """Five images of mixed orientations and sizes."""
    paths: List[str] = []
    for w, h, color, fname in SAMPLE_SPECS:
        p = tmp_path / fname
        _make_image(str(p), w, h, color)
        paths.append(str(p))
    return paths


@pytest.fixture
def single_image(tmp_path) -> str:
    p = tmp_path / "single.png"
    _make_image(str(p), 800, 600, "red")
    return str(p)


@pytest.fixture
def tall_image(tmp_path) -> str:
    """Very tall image — should trigger height-cap logic."""
    p = tmp_path / "tall.png"
    _make_image(str(p), 200, 2000, "orange")
    return str(p)


@pytest.fixture
def wide_image(tmp_path) -> str:
    """Very wide image — should trigger landscape auto-rotation."""
    p = tmp_path / "wide.png"
    _make_image(str(p), 2000, 200, "cyan")
    return str(p)


@pytest.fixture
def many_images(tmp_path) -> List[str]:
    """Ten small portrait images for compact-mode tests.

    Aspect ratio is kept below ``LANDSCAPE_RATIO_THRESHOLD`` so they don't
    get auto-rotated; pixel size is small so several fit on one page.
    """
    paths: List[str] = []
    for i in range(10):
        p = tmp_path / f"many_{i}.png"
        _make_image(str(p), 300, 300, "magenta")
        paths.append(str(p))
    return paths


@pytest.fixture
def corrupt_image(tmp_path) -> str:
    """File with image-like extension but invalid contents."""
    p = tmp_path / "broken.jpg"
    p.write_bytes(b"not an image at all")
    return str(p)


def count_pdf_pages(pdf_path: str) -> int:
    """Tiny PDF page counter using a regex over ``/Type /Page`` objects.

    Avoids pulling in PyMuPDF / pdfplumber as test deps. Matches Page (but
    not Pages) with any amount of whitespace between ``/Type`` and the name.
    """
    import re

    if not os.path.isfile(pdf_path):
        return 0
    with open(pdf_path, "rb") as fh:
        data = fh.read()
    # /Type/Page followed by a non-letter so we don't catch /Pages.
    return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


@pytest.fixture
def pdf_page_counter():
    return count_pdf_pages
