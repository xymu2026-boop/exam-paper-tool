"""M5 layout algorithms.

Pure functions that, given a list of image metadata and an ExportConfig,
produce a list of placement instructions: (page_number, x_mm, y_mm,
width_mm, height_mm). The exporter then renders these instructions onto
an FPDF document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .utils import get_page_size


# (page_number_1based, x_mm, y_mm, width_mm, height_mm)
LayoutItem = Tuple[int, float, float, float, float]


@dataclass(frozen=True)
class ImageMeta:
    """Lightweight description of an image for layout calculations."""

    pixel_width: int
    pixel_height: int

    @property
    def aspect(self) -> float:
        """Height divided by width; safe for zero-width inputs."""
        if self.pixel_width <= 0:
            return 1.0
        return self.pixel_height / self.pixel_width


COMPACT_GAP_MM = 10.0
ONE_PER_PAGE_MAX_HEIGHT_RATIO = 0.6
COMPACT_DPI = 96.0
MM_PER_INCH = 25.4


def _natural_size_mm(meta: ImageMeta) -> Tuple[float, float]:
    """Convert pixel dimensions to mm at COMPACT_DPI."""
    w_mm = meta.pixel_width / COMPACT_DPI * MM_PER_INCH
    h_mm = meta.pixel_height / COMPACT_DPI * MM_PER_INCH
    return w_mm, h_mm


def _scale_to_width(meta: ImageMeta, width_mm: float) -> Tuple[float, float]:
    """Return (display_w, display_h) for an image scaled to ``width_mm``."""
    return width_mm, width_mm * meta.aspect


def _layout_one_per_page(
    metas: List[ImageMeta],
    page_w: float,
    page_h: float,
    margin: float,
    spacing: float,
    start_page: int,
) -> List[LayoutItem]:
    """Each image gets its own page, scaled to fit width and height limits."""
    avail_w = page_w - 2 * margin
    avail_h = page_h - 2 * margin
    # 60 % cap measured against full page height (per task card).
    max_h = page_h * ONE_PER_PAGE_MAX_HEIGHT_RATIO
    # Also leave at least ``spacing`` of answer space below the image.
    max_h = min(max_h, avail_h - spacing)
    if max_h <= 0:
        max_h = avail_h

    items: List[LayoutItem] = []
    for i, meta in enumerate(metas):
        disp_w, disp_h = _scale_to_width(meta, avail_w)
        if disp_h > max_h:
            disp_h = max_h
            disp_w = disp_h / meta.aspect if meta.aspect > 0 else avail_w
        # Center horizontally; keep top edge anchored at the top margin.
        x = (page_w - disp_w) / 2
        y = margin
        items.append((start_page + i, x, y, disp_w, disp_h))
    return items


def _layout_two_per_page(
    metas: List[ImageMeta],
    page_w: float,
    page_h: float,
    margin: float,
    spacing: float,
    start_page: int,
) -> List[LayoutItem]:
    """Split each page into two halves; promote oversized images to full pages."""
    avail_w = page_w - 2 * margin
    half_h = (page_h - 2 * margin - spacing) / 2

    items: List[LayoutItem] = []
    page = start_page
    slot = 0  # 0 = top half of current page, 1 = bottom half

    for meta in metas:
        disp_w, disp_h = _scale_to_width(meta, avail_w)

        if disp_h > half_h:
            # Promote to a full page (single image layout for this one).
            if slot == 1:
                # Finish the current page even if its bottom slot is unused.
                page += 1
                slot = 0
            full = _layout_one_per_page(
                [meta], page_w, page_h, margin, spacing, page
            )
            items.extend(full)
            page += 1
            slot = 0
            continue

        if slot == 0:
            y = margin
            slot = 1
        else:
            y = margin + half_h + spacing
            slot = 0

        x = (page_w - disp_w) / 2
        items.append((page, x, y, disp_w, disp_h))

        if slot == 0:
            page += 1

    return items


def _layout_compact(
    metas: List[ImageMeta],
    page_w: float,
    page_h: float,
    margin: float,
    start_page: int,
) -> List[LayoutItem]:
    """Greedy top-to-bottom packing with a fixed 10 mm gap between images.

    Sizing rule: take the smaller of (natural size at 96 DPI) and (width-fit).
    This keeps small thumbnail-style crops compact rather than blowing them
    up to fill the entire page width.
    """
    avail_w = page_w - 2 * margin
    avail_h = page_h - 2 * margin

    items: List[LayoutItem] = []
    page = start_page
    cursor = margin
    placed_on_page = False

    for meta in metas:
        natural_w, natural_h = _natural_size_mm(meta)
        if natural_w <= avail_w:
            disp_w, disp_h = natural_w, natural_h
        else:
            disp_w, disp_h = _scale_to_width(meta, avail_w)

        if disp_h > avail_h:
            disp_h = avail_h
            disp_w = disp_h / meta.aspect if meta.aspect > 0 else avail_w

        remaining = (page_h - margin) - cursor
        if placed_on_page and remaining < disp_h:
            page += 1
            cursor = margin
            placed_on_page = False

        x = (page_w - disp_w) / 2
        y = cursor
        items.append((page, x, y, disp_w, disp_h))
        cursor = y + disp_h + COMPACT_GAP_MM
        placed_on_page = True

    return items


def calculate_layout(
    metas: List[ImageMeta],
    config,
    start_page: int = 1,
) -> List[LayoutItem]:
    """Dispatch to the correct layout algorithm based on config.layout.

    Args:
        metas: Image metadata in display order.
        config: An ExportConfig-like object with ``layout``, ``page_size``,
            ``margin_mm`` and ``spacing_mm`` attributes.
        start_page: 1-based page number where the first image should appear.
            Use a value > 1 when a title page precedes the layout.

    Returns:
        A list of LayoutItem tuples, one per input image, in the same order.

    Raises:
        ValueError: when config.layout is not a recognised mode.
    """
    page_w, page_h = get_page_size(config.page_size)
    margin = float(config.margin_mm)
    spacing = float(config.spacing_mm)

    if not metas:
        return []

    mode = config.layout
    if mode == "one_per_page":
        return _layout_one_per_page(
            metas, page_w, page_h, margin, spacing, start_page
        )
    if mode == "two_per_page":
        return _layout_two_per_page(
            metas, page_w, page_h, margin, spacing, start_page
        )
    if mode == "compact":
        return _layout_compact(metas, page_w, page_h, margin, start_page)

    raise ValueError(f"Unsupported layout: {mode!r}")
