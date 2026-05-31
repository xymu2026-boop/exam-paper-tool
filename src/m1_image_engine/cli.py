"""M1 命令行入口。

三个子命令：
- process: 处理单张图片
- mask:    仅生成 mask
- batch:   批量处理目录

用法：
    python -m src.m1_image_engine.cli process input.jpg output_dir/
    python -m src.m1_image_engine.cli mask input.jpg mask.jpg
    python -m src.m1_image_engine.cli batch input_dir/ output_dir/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict

from .engine import process_paper
from .mask import generate_mask
from .utils import SUPPORTED_EXTS


def _cmd_process(args: argparse.Namespace) -> int:
    result = process_paper(args.input_path, args.output_dir)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
    return 0 if result.success else 1


def _cmd_mask(args: argparse.Namespace) -> int:
    ok = generate_mask(args.input_path, args.output_path)
    print(json.dumps({"success": bool(ok)}, ensure_ascii=False))
    return 0 if ok else 1


def _cmd_batch(args: argparse.Namespace) -> int:
    if not os.path.isdir(args.input_dir):
        print(json.dumps({"error": f"input_dir not found: {args.input_dir}"}))
        return 2

    files: list[str] = []
    for name in sorted(os.listdir(args.input_dir)):
        full = os.path.join(args.input_dir, name)
        if not os.path.isfile(full):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in SUPPORTED_EXTS:
            files.append(full)

    if not files:
        print(json.dumps({"total": 0, "success": 0, "avg_quality": 0.0}))
        return 0

    succ = 0
    qualities: list[float] = []
    results = []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        out_dir = os.path.join(args.output_dir, base)
        r = process_paper(f, out_dir)
        if r.success:
            succ += 1
            qualities.append(r.quality_score)
        results.append(
            {
                "input": f,
                "success": r.success,
                "quality_score": r.quality_score,
                "error": r.error,
            }
        )
        print(
            json.dumps(
                {
                    "input": f,
                    "success": r.success,
                    "quality_score": r.quality_score,
                    "error": r.error,
                },
                ensure_ascii=False,
            )
        )

    avg = (sum(qualities) / len(qualities)) if qualities else 0.0
    summary = {
        "total": len(files),
        "success": succ,
        "avg_quality": round(avg, 4),
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="m1_image_engine",
        description="M1 图像处理引擎 CLI：预处理 + 手写擦除",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_process = sub.add_parser("process", help="处理单张图片")
    p_process.add_argument("input_path")
    p_process.add_argument("output_dir")
    p_process.set_defaults(func=_cmd_process)

    p_mask = sub.add_parser("mask", help="仅生成手写 mask")
    p_mask.add_argument("input_path")
    p_mask.add_argument("output_path")
    p_mask.set_defaults(func=_cmd_mask)

    p_batch = sub.add_parser("batch", help="批量处理目录")
    p_batch.add_argument("input_dir")
    p_batch.add_argument("output_dir")
    p_batch.set_defaults(func=_cmd_batch)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
