"""End-to-end exporter tests covering all three layout modes."""

from __future__ import annotations

import os

from src.m5_pdf_export import ExportConfig, export_pdf


def _is_pdf(path: str) -> bool:
    if not os.path.isfile(path):
        return False
    with open(path, "rb") as fh:
        head = fh.read(5)
    return head == b"%PDF-"


def test_export_one_per_page(sample_images, tmp_path, pdf_page_counter):
    out = tmp_path / "out_one.pdf"
    config = ExportConfig(layout="one_per_page")
    assert export_pdf(sample_images, str(out), config) is True
    assert _is_pdf(str(out))
    assert pdf_page_counter(str(out)) == len(sample_images)


def test_export_two_per_page(sample_images, tmp_path, pdf_page_counter):
    out = tmp_path / "out_two.pdf"
    config = ExportConfig(layout="two_per_page")
    assert export_pdf(sample_images, str(out), config) is True
    assert _is_pdf(str(out))
    pages = pdf_page_counter(str(out))
    assert 1 <= pages <= len(sample_images)


def test_export_compact(sample_images, tmp_path, pdf_page_counter):
    out = tmp_path / "out_compact.pdf"
    config = ExportConfig(layout="compact")
    assert export_pdf(sample_images, str(out), config) is True
    assert _is_pdf(str(out))
    pages = pdf_page_counter(str(out))
    assert pages >= 1
    assert pages <= len(sample_images)


def test_export_default_config(sample_images, tmp_path):
    out = tmp_path / "default.pdf"
    assert export_pdf(sample_images, str(out)) is True
    assert _is_pdf(str(out))


def test_export_with_title(sample_images, tmp_path, pdf_page_counter):
    out = tmp_path / "titled.pdf"
    config = ExportConfig(
        layout="one_per_page", title="K1 Math Mistakes 2026-05-31"
    )
    assert export_pdf(sample_images, str(out), config) is True
    pages = pdf_page_counter(str(out))
    assert pages == len(sample_images) + 1


def test_export_a3_page_size(sample_images, tmp_path):
    out = tmp_path / "a3.pdf"
    config = ExportConfig(layout="one_per_page", page_size="A3")
    assert export_pdf(sample_images, str(out), config) is True
    assert _is_pdf(str(out))


def test_export_creates_parent_directories(sample_images, tmp_path):
    out = tmp_path / "nested" / "deeper" / "x.pdf"
    assert export_pdf(sample_images, str(out)) is True
    assert _is_pdf(str(out))


def test_export_partial_with_missing_paths(sample_images, tmp_path):
    out = tmp_path / "partial.pdf"
    paths = sample_images[:2] + ["/nonexistent/totally/missing.png"] + sample_images[2:]
    assert export_pdf(paths, str(out)) is True
    assert _is_pdf(str(out))


def test_export_no_number_flag(sample_images, tmp_path):
    out = tmp_path / "nonum.pdf"
    config = ExportConfig(show_number=False)
    assert export_pdf(sample_images, str(out), config) is True
    assert _is_pdf(str(out))


def test_export_landscape_image_does_not_overflow(wide_image, tmp_path):
    out = tmp_path / "wide.pdf"
    config = ExportConfig(layout="one_per_page")
    assert export_pdf([wide_image], str(out), config) is True
    assert _is_pdf(str(out))
