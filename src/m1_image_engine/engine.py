"""M1 main pipeline: 3 stages with 6 debug outputs."""

from __future__ import annotations

import os, shutil
from dataclasses import dataclass, field
from typing import Optional

from .preprocess import preprocess_pipeline
from .mask import generate_masks
from .eraser import apply_masks_separately
from .quality import score_quality
from .utils import ensure_dir, save_bgr_jpeg, load_bgr, load_gray

JPEG_QUALITY = 95
QUALITY_THRESHOLD = 0.60


@dataclass
class ProcessResult:
    success: bool
    processed_path: Optional[str] = None
    cleaned_path: Optional[str] = None
    quality_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    original_path: Optional[str] = None
    red_mask_path: Optional[str] = None
    hw_mask_path: Optional[str] = None
    combined_mask_path: Optional[str] = None


def process_paper(input_path: str, output_dir: str) -> ProcessResult:
    if not input_path or not output_dir:
        return ProcessResult(success=False, error="input_path or output_dir is empty")
    try:
        ensure_dir(output_dir)
    except Exception as e:
        return ProcessResult(success=False, error=f"mkdir_failed: {e}")

    warnings = []

    original_path = os.path.join(output_dir, "original.jpg")
    try:
        shutil.copy2(input_path, original_path)
    except Exception as e:
        warnings.append(f"copy_original_failed: {e}")

    processed, pw, err = preprocess_pipeline(input_path)
    warnings.extend(pw)
    if err is not None or processed is None:
        return ProcessResult(success=False, warnings=warnings, error=err, original_path=original_path)

    processed_path = os.path.join(output_dir, "processed.jpg")
    if not save_bgr_jpeg(processed, processed_path, quality=JPEG_QUALITY):
        return ProcessResult(success=False, warnings=warnings, error=f"write_failed: {processed_path}", original_path=original_path)

    masks = generate_masks(processed_path, output_dir)
    red_mask_path = masks.get("red_mask_path")
    hw_mask_path = masks.get("hw_mask_path")
    combined_mask_path = masks.get("combined_mask_path")

    cleaned_path = os.path.join(output_dir, "cleaned.jpg")
    if not apply_masks_separately(processed_path, red_mask_path, hw_mask_path, cleaned_path):
        return ProcessResult(success=False, warnings=warnings, error="erase_failed",
                            original_path=original_path, processed_path=processed_path,
                            red_mask_path=red_mask_path, hw_mask_path=hw_mask_path,
                            combined_mask_path=combined_mask_path)

    try:
        proc_img = load_bgr(processed_path)
        clean_img = load_bgr(cleaned_path)
        mask_img = load_gray(combined_mask_path) if combined_mask_path else None
        quality = score_quality(proc_img, clean_img, mask_img) if proc_img is not None and clean_img is not None and mask_img is not None else 1.0
    except Exception as e:
        quality = 0.0
        warnings.append(f"quality_score_failed: {e}")

    if quality < QUALITY_THRESHOLD:
        warnings.append(f"quality_score {quality:.2f} below threshold {QUALITY_THRESHOLD}")

    return ProcessResult(success=True, original_path=original_path, processed_path=processed_path,
                        cleaned_path=cleaned_path, red_mask_path=red_mask_path,
                        hw_mask_path=hw_mask_path, combined_mask_path=combined_mask_path,
                        quality_score=quality, warnings=warnings)

__all__ = ["process_paper", "ProcessResult", "QUALITY_THRESHOLD", "JPEG_QUALITY"]
