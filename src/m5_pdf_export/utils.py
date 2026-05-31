"""M5 utility helpers: image loading, orientation, page-size constants.

This module is intentionally free of any project-internal imports so that
M5 can be used as a standalone PDF-export library.
"""

from __future__ import annotations

import logging
import os
from typing import Optional, Tuple

from PIL import Image, ImageOps, UnidentifiedImageError

logger = logging.getLogger(__name__)


# Page sizes in millimetres (width, height) for portrait orientation.
PAGE_SIZES: dict[str, Tuple[int, int]] = {
    "A4": (210, 297),
    "A3": (297, 420),
}

# Supported input image extensions (lowercase, including leading dot).
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Aspect ratio threshold above which a landscape image is auto-rotated 90 deg
# (i.e. width / height > LANDSCAPE_RATIO_THRESHOLD => rotate to portrait).
LANDSCAPE_RATIO_THRESHOLD = 1.2


def get_page_size(name: str) -> Tuple[int, int]:
    """Return (width_mm, height_mm) for a named page size.

    Args:
        name: 'A4' or 'A3'.

    Returns:
        Tuple of (width_mm, height_mm).

    Raises:
        ValueError: when the name is not a supported page size.
    """
    key = name.upper() if isinstance(name, str) else ""
    if key not in PAGE_SIZES:
        raise ValueError(f"Unsupported page size: {name!r}")
    return PAGE_SIZES[key]


def is_supported_image(path: str) -> bool:
    """Check whether the path points to a supported image type by extension."""
    if not path:
        return False
    _, ext = os.path.splitext(path)
    return ext.lower() in SUPPORTED_EXTENSIONS


def load_and_orient_image(path: str) -> Optional[Image.Image]:
    """Load an image and apply orientation corrections.

    Pipeline:
        1. Open via Pillow.
        2. Apply EXIF transpose to honor the camera orientation tag.
        3. If the image is clearly landscape (width / height > threshold),
           rotate it 90 degrees clockwise so it fits a portrait page better.

    Args:
        path: Absolute path to a JPG/PNG file.

    Returns:
        A PIL Image object in RGB mode, or None if the file is missing,
        unreadable, corrupt, or of an unsupported type.
    """
    if not path or not os.path.isfile(path):
        logger.warning("Skipping missing image: %s", path)
        return None

    if not is_supported_image(path):
        logger.warning("Skipping unsupported image type: %s", path)
        return None

    try:
        img = Image.open(path)
        img.load()  # force the decoder to actually read the file now
    except (OSError, UnidentifiedImageError) as exc:
        logger.warning("Skipping unreadable image %s: %s", path, exc)
        return None

    # Honor EXIF orientation. exif_transpose returns a new image when needed.
    try:
        img = ImageOps.exif_transpose(img)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("EXIF transpose failed for %s: %s", path, exc)

    # Convert to RGB so PDF embedding is consistent regardless of source mode.
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Auto-rotate clearly landscape images for portrait page layouts.
    width, height = img.size
    if height > 0 and (width / height) > LANDSCAPE_RATIO_THRESHOLD:
        img = img.rotate(-90, expand=True)

    return img


def ensure_parent_dir(output_path: str) -> None:
    """Create the parent directory of ``output_path`` if it does not exist."""
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
