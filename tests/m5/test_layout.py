"""Layout-algorithm unit tests.

These tests target the pure layout logic in ``src/m5_pdf_export/layout.py``
without involving fpdf2 or actual PDF generation.
"""

from __future__ import annotations

from src.m5_pdf_export.exporter import ExportConfig
from src.m5_pdf_export.layout import ImageMeta, calculate_layout


def _meta(w: int, h: int) -> ImageMeta:
    return ImageMeta(pixel_width=w, pixel_height=h)


def test_one_per_page_assigns_unique_pages():
    metas = [_meta(800, 600), _meta(800, 600), _meta(800, 600)]
    config = ExportConfig(layout="one_per_page")
    items = calculate_layout(metas, config)
    pages = [p for p, *_ in items]
    assert pages == [1, 2, 3]


def test_one_per_page_fits_within_page():
    page_w, page_h = 210, 297
    metas = [_meta(800, 600)]
    config = ExportConfig(layout="one_per_page", margin_mm=15, spacing_mm=20)
    (page, x, y, w, h), = calculate_layout(metas, config)
    assert page == 1
    assert x >= 0 and y >= config.margin_mm
    assert x + w <= page_w + 1e-6
    assert y + h <= page_h - config.margin_mm + 1e-6


def test_one_per_page_caps_tall_image_at_60_percent():
    page_h = 297
    metas = [_meta(200, 2000)]  # extremely tall
    config = ExportConfig(layout="one_per_page")
    (_, _, _, _, h), = calculate_layout(metas, config)
    assert h <= page_h * 0.6 + 1e-6


def test_two_per_page_packs_two_into_one_page():
    metas = [_meta(800, 400), _meta(800, 400)]
    config = ExportConfig(layout="two_per_page")
    items = calculate_layout(metas, config)
    assert {p for p, *_ in items} == {1}
    assert items[0][2] < items[1][2]


def test_two_per_page_four_images_two_pages():
    metas = [_meta(800, 400)] * 4
    config = ExportConfig(layout="two_per_page")
    items = calculate_layout(metas, config)
    pages = [p for p, *_ in items]
    assert pages == [1, 1, 2, 2]


def test_two_per_page_promotes_tall_to_full_page():
    metas = [_meta(800, 600), _meta(200, 4000), _meta(800, 600)]
    config = ExportConfig(layout="two_per_page")
    items = calculate_layout(metas, config)
    pages = [p for p, *_ in items]
    assert len(set(pages)) >= 2
    assert pages[1] != pages[0] or pages[1] != pages[2]


def test_compact_uses_fewer_pages_than_count():
    metas = [_meta(800, 200) for _ in range(6)]
    config = ExportConfig(layout="compact")
    items = calculate_layout(metas, config)
    pages = {p for p, *_ in items}
    assert len(pages) < len(metas)


def test_compact_paginates_when_page_full():
    metas = [_meta(800, 800) for _ in range(5)]
    config = ExportConfig(layout="compact")
    items = calculate_layout(metas, config)
    pages = [p for p, *_ in items]
    assert max(pages) >= 2


def test_compact_no_overlap():
    metas = [_meta(800, 400) for _ in range(4)]
    config = ExportConfig(layout="compact")
    items = calculate_layout(metas, config)
    by_page: dict[int, list] = {}
    for page, x, y, w, h in items:
        by_page.setdefault(page, []).append((y, h))
    for placements in by_page.values():
        placements.sort()
        for (y1, h1), (y2, _h2) in zip(placements, placements[1:]):
            assert y2 >= y1 + h1


def test_start_page_offset_shifts_all_pages():
    metas = [_meta(800, 600), _meta(800, 600)]
    config = ExportConfig(layout="one_per_page")
    items_no_offset = calculate_layout(metas, config, start_page=1)
    items_offset = calculate_layout(metas, config, start_page=3)
    assert [p for p, *_ in items_offset] == [3, 4]
    assert [p for p, *_ in items_no_offset] == [1, 2]


def test_empty_metas_returns_empty_layout():
    config = ExportConfig(layout="one_per_page")
    assert calculate_layout([], config) == []


def test_invalid_layout_raises():
    import pytest

    config = ExportConfig(layout="invalid_mode")
    with pytest.raises(ValueError):
        calculate_layout([_meta(800, 600)], config)
