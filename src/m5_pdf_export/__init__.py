"""M5: PDF export module.

Public API (see docs/INTERFACE-CONTRACT.md section 4.5):
    - ExportConfig
    - export_pdf
"""

from .exporter import ExportConfig, export_pdf

__all__ = ["ExportConfig", "export_pdf"]
