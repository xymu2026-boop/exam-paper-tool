"""M1: 图像处理引擎

公开接口请见 docs/INTERFACE-CONTRACT.md 4.1 节。
"""

from .engine import ProcessResult, process_paper
from .eraser import apply_mask, apply_masks_separately
from .mask import generate_mask, generate_masks

__all__ = ["process_paper", "generate_mask", "generate_masks", "apply_mask", "apply_masks_separately", "ProcessResult"]
