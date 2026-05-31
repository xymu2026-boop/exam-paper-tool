"""M5 command-line interface.

Usage:
    python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o out.pdf
    python -m src.m5_pdf_export.cli export *.png -o out.pdf --layout two_per_page
    python -m src.m5_pdf_export.cli export a.png b.png -o out.pdf --layout compact --title "K1 Math"
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import List, Optional, Sequence

from .exporter import ExportConfig, export_pdf


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.m5_pdf_export.cli",
        description="Export a list of mistake images to a printable PDF.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    export_p = sub.add_parser("export", help="Export images to a PDF file.")
    export_p.add_argument(
        "images",
        nargs="+",
        help="One or more image file paths (JPG/PNG).",
    )
    export_p.add_argument(
        "-o",
        "--output",
        required=True,
        help="Output PDF path.",
    )
    export_p.add_argument(
        "--layout",
        default="one_per_page",
        choices=("one_per_page", "two_per_page", "compact"),
        help="Layout mode (default: one_per_page).",
    )
    export_p.add_argument(
        "--page-size",
        default="A4",
        choices=("A4", "A3"),
        help="Page size (default: A4).",
    )
    export_p.add_argument(
        "--margin",
        type=int,
        default=15,
        help="Page margin in millimetres (default: 15).",
    )
    export_p.add_argument(
        "--spacing",
        type=int,
        default=20,
        help="Spacing between questions in millimetres (default: 20).",
    )
    export_p.add_argument(
        "--title",
        default="",
        help="Optional title shown on the first page.",
    )
    export_p.add_argument(
        "--no-number",
        action="store_true",
        help="Do not render question numbers.",
    )
    export_p.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if getattr(args, "verbose", False) else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.command == "export":
        config = ExportConfig(
            layout=args.layout,
            page_size=args.page_size,
            margin_mm=args.margin,
            spacing_mm=args.spacing,
            title=args.title,
            show_number=not args.no_number,
        )
        images: List[str] = list(args.images)
        ok = export_pdf(images, args.output, config)
        if ok:
            print(f"PDF written: {args.output}")
            return 0
        print("PDF export failed (see log messages above).", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
