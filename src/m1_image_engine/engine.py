"""M1 主编排：8 步流水线 + ProcessResult。

ProcessResult 字段严格遵守 docs/INTERFACE-CONTRACT.md 4.1。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from .eraser import _apply_mask_array
from .mask import _generate_mask_array
from .preprocess import preprocess_pipeline
from .quality import score_quality
from .utils import ensure_dir, save_bgr_jpeg

JPEG_QUALITY = 95
QUALITY_THRESHOLD = 0.60


@dataclass
class ProcessResult:
    """图像处理结果。"""

    success: bool
    processed_path: Optional[str] = None
    cleaned_path: Optional[str] = None
    quality_score: float = 0.0
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None


def process_paper(input_path: str, output_dir: str) -> ProcessResult:
    """处理单张试卷图片。

    Args:
        input_path: 原始图片绝对路径
        output_dir: 输出目录绝对路径，自动创建

    Returns:
        ProcessResult
    """
    # 参数基础校验
    if not input_path:
        return ProcessResult(success=False, error="input_path is empty")
    if not output_dir:
        return ProcessResult(success=False, error="output_dir is empty")

    # 预处理 (Step 1-5)
    processed, warnings, err = preprocess_pipeline(input_path)
    if err is not None or processed is None:
        return ProcessResult(success=False, warnings=warnings, error=err)

    # 创建输出目录
    try:
        ensure_dir(output_dir)
    except Exception as e:
        return ProcessResult(
            success=False, warnings=warnings, error=f"mkdir_failed: {e}"
        )

    # 保存 processed.jpg
    processed_path = os.path.join(output_dir, "processed.jpg")
    if not save_bgr_jpeg(processed, processed_path, quality=JPEG_QUALITY):
        return ProcessResult(
            success=False,
            warnings=warnings,
            error=f"write_failed: {processed_path}",
        )

    # Step 6: mask
    try:
        mask = _generate_mask_array(processed)
    except Exception as e:
        return ProcessResult(
            success=False,
            processed_path=processed_path,
            warnings=warnings,
            error=f"mask_failed: {e}",
        )

    if int((mask > 127).sum()) == 0:
        warnings.append("no_handwriting_detected")

    # Step 7: 擦除
    try:
        cleaned = _apply_mask_array(processed, mask, method="white")
    except Exception as e:
        return ProcessResult(
            success=False,
            processed_path=processed_path,
            warnings=warnings,
            error=f"erase_failed: {e}",
        )

    cleaned_path = os.path.join(output_dir, "cleaned.jpg")
    if not save_bgr_jpeg(cleaned, cleaned_path, quality=JPEG_QUALITY):
        return ProcessResult(
            success=False,
            processed_path=processed_path,
            warnings=warnings,
            error=f"write_failed: {cleaned_path}",
        )

    # Step 8: 评分
    try:
        quality = score_quality(processed, cleaned, mask)
    except Exception as e:
        quality = 0.0
        warnings.append(f"quality_score_failed: {e}")

    if quality < QUALITY_THRESHOLD:
        warnings.append(f"quality_score {quality:.2f} below threshold {QUALITY_THRESHOLD}")

    return ProcessResult(
        success=True,
        processed_path=processed_path,
        cleaned_path=cleaned_path,
        quality_score=quality,
        warnings=warnings,
        error=None,
    )


__all__ = ["process_paper", "ProcessResult", "QUALITY_THRESHOLD", "JPEG_QUALITY"]
