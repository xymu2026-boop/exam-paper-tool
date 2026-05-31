"""M1: 图像处理引擎

公开接口请见 docs/INTERFACE-CONTRACT.md 4.1 节。
开发任务卡：docs/modules/M1-IMAGE-ENGINE.md
"""

from .engine import ProcessResult, process_paper
from .eraser import apply_mask
from .mask import generate_mask

__all__ = ["process_paper", "generate_mask", "apply_mask", "ProcessResult"]
