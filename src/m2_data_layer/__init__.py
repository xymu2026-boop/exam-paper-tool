"""M2: 数据层 — 数据访问层

所有数据库操作通过此模块进行，其他模块禁止直接操作 SQLite。
公开接口请见 ``docs/INTERFACE-CONTRACT.md`` 第 4.2 节。

导出的主要类:
    Database  数据库访问类（所有 CRUD 操作入口）
    Paper     试卷数据模型
    Mistake   错题数据模型
    ExportLog 导出日志数据模型
"""

from .models import Paper, Mistake, ExportLog
from .db import Database

__all__ = [
    "Database",
    "Paper",
    "Mistake",
    "ExportLog",
]
