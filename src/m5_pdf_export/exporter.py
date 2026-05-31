"""M5 PDF exporter — public entry point.

The export pipeline:

    1. Validate inputs (image_paths non-empty, ensure output parent dir).
    2. Normalise config (None -> default ExportConfig).
    3. Load + EXIF-correct + landscape-rotate each image via utils.
    4. Compute placement instructions in :mod:`layout`.
    5. Render a (optional) title page, then iterate placements and call
       ``pdf.image(...)`` for each one.
    6. Persist the PDF to disk; return success boolean.
"""

from __future__ import annotations

import io
import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from fpdf import FPDF
from PIL import Image

from .layout import ImageMeta, LayoutItem, calculate_layout
from .utils import (
    SUPPORTED_EXTENSIONS,
    PAGE_SIZES,
    ensure_parent_dir,
    load_and_orient_image,
)

logger = logging.getLogger(__name__)


VALID_LAYOUTS = {"one_per_page", "two_per_page", "compact"}
# Regex covering CJK Unified Ideographs + a few common extension blocks.
# Used to decide whether the title needs a Unicode-capable font.
_CJK_RE = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")


@dataclass
class ExportConfig:
    """Export configuration.

    Field names and defaults MUST match INTERFACE-CONTRACT.md section 4.5
    exactly; do not rename or reorder.
    """

    layout: str = "one_per_page"  # 'one_per_page' | 'two_per_page' | 'compact'
    page_size: str = "A4"  # 'A4' | 'A3'
    margin_mm: int = 15  # page margin
    spacing_mm: int = 20  # gap below each image for handwritten answers
    title: str = ""  # optional first-page title
    show_number: bool = True  # render question numbers in the corner


def _has_cjk(text: str) -> bool:
    return bool(text) and bool(_CJK_RE.search(text))


def _make_pdf(config: ExportConfig) -> FPDF:
    """Create an FPDF instance configured per the export options."""
    page_w, page_h = PAGE_SIZES[config.page_size]
    pdf = FPDF(orientation="P", unit="mm", format=(page_w, page_h))
    # We manage page breaks manually based on layout output.
    pdf.set_auto_page_break(auto=False, margin=0)
    pdf.set_margins(config.margin_mm, config.margin_mm, config.margin_mm)
    return pdf


def _render_title(pdf: FPDF, config: ExportConfig) -> None:
    """Render the title at the top of the current page.

    fpdf2's built-in fonts only cover Latin-1. For CJK titles we attempt to
    load a bundled font under ``src/m5_pdf_export/fonts/`` (e.g. Noto Sans
    SC). If that font is unavailable, we fall back to Helvetica which will
    render CJK characters as boxes — the test suite documents this
    limitation rather than masking it.
    """
    if _has_cjk(config.title):
        # Try to load a bundled Unicode font for CJK rendering.
        import os

        font_dir = os.path.join(os.path.dirname(__file__), "fonts")
        font_candidates = [
            "NotoSansSC-Regular.ttf",
            "NotoSansSC-Regular.otf",
            "SourceHanSans-Regular.otf",
        ]
        loaded = False
        for fname in font_candidates:
            fpath = os.path.join(font_dir, fname)
            if os.path.isfile(fpath):
                try:
                    pdf.add_font("CJK", "", fpath)
                    pdf.set_font("CJK", size=20)
                    loaded = True
                    break
                except Exception as exc:  # pragma: no cover - defensive
                    logger.warning("Failed to load CJK font %s: %s", fpath, exc)
        if not loaded:
            # Fallback: best-effort with Helvetica; CJK glyphs will be tofu.
            logger.warning(
                "No CJK font available; title may render as boxes. "
                "Drop a Noto Sans SC TTF into src/m5_pdf_export/fonts/."
            )
            pdf.set_font("Helvetica", size=20)
    else:
        pdf.set_font("Helvetica", size=20)

    pdf.set_y(config.margin_mm)
    try:
        pdf.cell(0, 12, config.title, align="C", new_x="LMARGIN", new_y="NEXT")
    except UnicodeEncodeError:
        # Helvetica path with non-latin characters: best-effort fallback.
        safe = config.title.encode("latin-1", errors="replace").decode("latin-1")
        pdf.cell(0, 12, safe, align="C", new_x="LMARGIN", new_y="NEXT")


def _pil_to_png_bytes(img: Image.Image) -> io.BytesIO:
    """Encode a PIL image to a PNG byte stream for fpdf2 consumption."""
    # fpdf2 can accept a file-like PNG buffer directly.
    if img.mode not in ("RGB", "L", "RGBA"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def export_pdf(
    image_paths: List[str],
    output_path: str,
    config: Optional[ExportConfig] = None,
) -> bool:
    """Export a list of mistake images to a printable PDF.

    Args:
        image_paths: Absolute paths to JPG/PNG images, in display order.
        output_path: Absolute path where the PDF should be written.
        config: Export configuration. Defaults to ``ExportConfig()`` when None.

    Returns:
        True on success (at least one image was rendered and the file was
        written). False on validation errors, empty/all-invalid input lists,
        or write failures.
    """
    if config is None:
        config = ExportConfig()

    # --- Configuration validation -------------------------------------------
    if config.layout not in VALID_LAYOUTS:
        logger.error("Invalid layout: %r", config.layout)
        return False
    if config.page_size not in PAGE_SIZES:
        logger.error("Invalid page size: %r", config.page_size)
        return False

    # --- Input validation ----------------------------------------------------
    if not image_paths:
        logger.error("export_pdf called with empty image_paths")
        return False

    # --- Load images (streaming-style: one at a time during render too) -----
    # First pass: just collect metadata so layout can pre-compute pages.
    loaded: List[tuple[str, ImageMeta]] = []
    for path in image_paths:
        img = load_and_orient_image(path)
        if img is None:
            continue
        meta = ImageMeta(pixel_width=img.width, pixel_height=img.height)
        # We close here and reopen during render to keep peak memory low.
        img.close()
        loaded.append((path, meta))

    if not loaded:
        logger.error("No valid images to export; aborting.")
        return False

    # --- Output path prep ----------------------------------------------------
    try:
        ensure_parent_dir(output_path)
    except OSError as exc:
        logger.error("Cannot create output directory: %s", exc)
        return False

    # --- PDF construction ----------------------------------------------------
    pdf = _make_pdf(config)

    title_offset = 0
    if config.title:
        pdf.add_page()
        _render_title(pdf, config)
        title_offset = 1

    metas = [m for _, m in loaded]
    placements: List[LayoutItem] = calculate_layout(
        metas, config, start_page=1 + title_offset
    )

    # --- Render images -------------------------------------------------------
    # Number questions across the document regardless of layout.
    for idx, ((path, _meta), (page_no, x, y, w, h)) in enumerate(
        zip(loaded, placements)
    ):
        while pdf.page_no() < page_no:
            pdf.add_page()

        # Reload the image so we can pass a fresh, oriented buffer to fpdf2.
        img = load_and_orient_image(path)
        if img is None:  # pragma: no cover - already filtered above
            continue
        try:
            buf = _pil_to_png_bytes(img)
            pdf.image(buf, x=x, y=y, w=w, h=h)
            if config.show_number:
                pdf.set_font("Helvetica", size=10)
                pdf.set_xy(x, max(0.0, y - 6))
                try:
                    pdf.cell(20, 5, f"{idx + 1}.")
                except UnicodeEncodeError:  # pragma: no cover - ascii only
                    pass
        finally:
            img.close()

    # --- Persist -------------------------------------------------------------
    try:
        pdf.output(output_path)
    except (OSError, RuntimeError) as exc:
        logger.error("Failed to write PDF %s: %s", output_path, exc)
        return False

    return True


__all__ = ["ExportConfig", "export_pdf", "SUPPORTED_EXTENSIONS"]
