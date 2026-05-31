"""Edge-case tests for M5 export pipeline."""

from __future__ import annotations

import os

from src.m5_pdf_export import ExportConfig, export_pdf


def _is_pdf(path) -> bool:
    p = str(path)
    if not os.path.isfile(p):
        return False
    with open(p, "rb") as fh:
        return fh.read(5) == b"%PDF-"


def test_empty_image_list_returns_false(tmp_path):
    out = tmp_path / "nope.pdf"
    assert export_pdf([], str(out)) is False
    assert not out.exists()


def test_single_image_all_layouts(single_image, tmp_path):
    for layout in ("one_per_page", "two_per_page", "compact"):
        out = tmp_path / f"single_{layout}.pdf"
        config = ExportConfig(layout=layout)
        assert export_pdf([single_image], str(out), config) is True, layout
        assert _is_pdf(out), layout


def test_only_invalid_paths_returns_false(tmp_path):
    out = tmp_path / "x.pdf"
    bad = ["/no/such/a.jpg", "/no/such/b.jpg"]
    assert export_pdf(bad, str(out)) is False
    assert not out.exists()


def test_invalid_layout_returns_false(single_image, tmp_path):
    out = tmp_path / "y.pdf"
    config = ExportConfig(layout="bogus")
    assert export_pdf([single_image], str(out), config) is False


def test_invalid_page_size_returns_false(single_image, tmp_path):
    out = tmp_path / "y.pdf"
    config = ExportConfig(page_size="A99")
    assert export_pdf([single_image], str(out), config) is False


def test_corrupt_image_is_skipped_with_others(corrupt_image, single_image, tmp_path):
    out = tmp_path / "mixed.pdf"
    assert export_pdf([corrupt_image, single_image], str(out)) is True
    assert _is_pdf(out)


def test_corrupt_image_only_returns_false(corrupt_image, tmp_path):
    out = tmp_path / "broken.pdf"
    assert export_pdf([corrupt_image], str(out)) is False


def test_very_tall_image(tall_image, tmp_path):
    out = tmp_path / "tall.pdf"
    config = ExportConfig(layout="one_per_page")
    assert export_pdf([tall_image], str(out), config) is True
    assert _is_pdf(out)


def test_very_wide_image_rotated(wide_image, tmp_path):
    out = tmp_path / "wide.pdf"
    config = ExportConfig(layout="one_per_page")
    assert export_pdf([wide_image], str(out), config) is True
    assert _is_pdf(out)


def test_many_images_compact(many_images, tmp_path, pdf_page_counter):
    out = tmp_path / "many.pdf"
    config = ExportConfig(layout="compact")
    assert export_pdf(many_images, str(out), config) is True
    pages = pdf_page_counter(str(out))
    assert pages >= 1
    assert pages < len(many_images)


def test_unsupported_extension_skipped(tmp_path, single_image):
    bogus = tmp_path / "thing.bmp"
    bogus.write_bytes(b"whatever")
    out = tmp_path / "filtered.pdf"
    assert export_pdf([str(bogus), single_image], str(out)) is True
    assert _is_pdf(out)


def test_two_per_page_with_one_image(single_image, tmp_path, pdf_page_counter):
    out = tmp_path / "two_one.pdf"
    config = ExportConfig(layout="two_per_page")
    assert export_pdf([single_image], str(out), config) is True
    pages = pdf_page_counter(str(out))
    assert pages == 1
