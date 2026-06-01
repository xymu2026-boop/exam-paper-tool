"""M1: 图像处理引擎 — V2

公开接口: ProcessResult + process_paper。
"""

from .engine import ProcessResult, process_paper

__all__ = ["process_paper", "ProcessResult"]
