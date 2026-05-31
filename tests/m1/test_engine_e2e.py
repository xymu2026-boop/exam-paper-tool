"""tests/m1/test_engine_e2e.py — 端到端流水线 + 边缘情况。"""

from __future__ import annotations

import os
from dataclasses import fields

import numpy as np
import pytest

from src.m1_image_engine import (
    ProcessResult,
    apply_mask,
    generate_mask,
    process_paper,
)


# ---------------------------------------------------------------------------
# ProcessResult 契约
# ---------------------------------------------------------------------------


def test_process_result_has_required_fields():
    """ProcessResult 字段必须严格匹配 INTERFACE-CONTRACT.md 4.1。"""
    names = {f.name for f in fields(ProcessResult)}
    expected = {"success", "processed_path", "cleaned_path", "quality_score", "warnings", "error"}
    assert names == expected


def test_process_result_defaults():
    r = ProcessResult(success=False)
    assert r.processed_path is None
    assert r.cleaned_path is None
    assert r.quality_score == 0.0
    assert r.warnings == []
    assert r.error is None


# ---------------------------------------------------------------------------
# 端到端：process_paper
# ---------------------------------------------------------------------------


def test_process_paper_with_blue_handwriting(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "blue.jpg")
    out_dir = str(tmp_path / "out")
    result = process_paper(in_path, out_dir)
    assert isinstance(result, ProcessResult)
    assert result.success is True
    assert result.processed_path and os.path.exists(result.processed_path)
    assert result.cleaned_path and os.path.exists(result.cleaned_path)
    assert 0.0 <= result.quality_score <= 1.0
    assert result.error is None


def test_process_paper_creates_output_dir_if_missing(tmp_path, tmp_image_path, white_canvas):
    in_path = tmp_image_path(white_canvas, "blank.jpg")
    out_dir = str(tmp_path / "deep" / "nested" / "out")
    assert not os.path.exists(out_dir)
    result = process_paper(in_path, out_dir)
    assert os.path.isdir(out_dir)
    assert result.success is True


def test_process_paper_does_not_modify_original(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "in.jpg")
    before = open(in_path, "rb").read()
    out_dir = str(tmp_path / "out")
    process_paper(in_path, out_dir)
    after = open(in_path, "rb").read()
    assert before == after, "原图被修改了"


def test_process_paper_missing_input():
    result = process_paper("/nonexistent/file.jpg", "/tmp/whatever_m1_test_out")
    assert result.success is False
    assert result.error is not None
    assert "load_failed" in result.error or "not found" in result.error.lower()


def test_process_paper_corrupt_image(tmp_path):
    bad = tmp_path / "bad.jpg"
    bad.write_bytes(b"not_an_image_at_all_42")
    result = process_paper(str(bad), str(tmp_path / "out"))
    assert result.success is False
    assert result.error is not None


def test_process_paper_empty_input_path():
    result = process_paper("", "/tmp/out")
    assert result.success is False
    assert result.error is not None


def test_process_paper_empty_output_dir(tmp_path, tmp_image_path, white_canvas):
    in_path = tmp_image_path(white_canvas, "in.jpg")
    result = process_paper(in_path, "")
    assert result.success is False


def test_process_paper_small_image(tmp_path, tmp_image_path, small_image):
    in_path = tmp_image_path(small_image, "tiny.jpg")
    out_dir = str(tmp_path / "out")
    result = process_paper(in_path, out_dir)
    # 不要求成功，但不应崩溃
    assert isinstance(result, ProcessResult)


def test_process_paper_all_black(tmp_path, tmp_image_path, all_black_image):
    in_path = tmp_image_path(all_black_image, "black.jpg")
    out_dir = str(tmp_path / "out")
    result = process_paper(in_path, out_dir)
    # 不应崩溃
    assert isinstance(result, ProcessResult)


def test_process_paper_perspective_paper(tmp_path, tmp_image_path, canvas_perspective_paper):
    in_path = tmp_image_path(canvas_perspective_paper, "persp.jpg")
    out_dir = str(tmp_path / "out")
    result = process_paper(in_path, out_dir)
    assert result.success is True
    assert os.path.exists(result.processed_path)


def test_process_paper_outputs_jpeg(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "in.jpg")
    out_dir = str(tmp_path / "out")
    result = process_paper(in_path, out_dir)
    assert result.processed_path.endswith("processed.jpg")
    assert result.cleaned_path.endswith("cleaned.jpg")


def test_heic_fallback_when_unsupported(tmp_path, monkeypatch):
    """HEIC 文件 + pillow-heif 不支持 -> 友好错误。"""
    import src.m1_image_engine.utils as utils_mod
    import src.m1_image_engine.preprocess as preprocess_mod

    monkeypatch.setattr(utils_mod, "HEIC_SUPPORTED", False)
    monkeypatch.setattr(preprocess_mod, "preprocess_pipeline", preprocess_mod.preprocess_pipeline)

    fake_heic = tmp_path / "phone.heic"
    fake_heic.write_bytes(b"not real heic data")
    result = process_paper(str(fake_heic), str(tmp_path / "out"))
    assert result.success is False
    assert result.error is not None
    assert "HEIC" in result.error


# ---------------------------------------------------------------------------
# 端到端：generate_mask + apply_mask 流水线
# ---------------------------------------------------------------------------


def test_generate_then_apply_mask_pipeline(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "in.jpg")
    mask_path = str(tmp_path / "mask.png")
    out_path = str(tmp_path / "cleaned.jpg")

    assert generate_mask(in_path, mask_path) is True
    assert os.path.exists(mask_path)

    assert apply_mask(in_path, mask_path, out_path, method="white") is True
    assert os.path.exists(out_path)


def test_apply_mask_inpaint_e2e(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "in.jpg")
    mask_path = str(tmp_path / "mask.png")
    out_path = str(tmp_path / "cleaned_inpaint.jpg")
    assert generate_mask(in_path, mask_path) is True
    assert apply_mask(in_path, mask_path, out_path, method="inpaint") is True
    assert os.path.exists(out_path)


# ---------------------------------------------------------------------------
# 不依赖其他模块 — 静态检查
# ---------------------------------------------------------------------------


def test_no_imports_of_other_modules():
    """确保 m1 不引用 m2/m3/m4/m5。"""
    import importlib
    import pkgutil

    import src.m1_image_engine as m1_pkg

    forbidden = ("m2_data_layer", "m3_web_frontend", "m4_web_backend", "m5_pdf_export")

    for _, modname, _ in pkgutil.walk_packages(m1_pkg.__path__, prefix="src.m1_image_engine."):
        mod = importlib.import_module(modname)
        for f in forbidden:
            for k in vars(mod):
                v = vars(mod)[k]
                # 检查导入的模块名
                if hasattr(v, "__module__") and v.__module__:
                    assert f not in v.__module__, f"{modname} 引用了 {f}"


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------


def test_cli_help():
    """CLI --help 不应崩溃，应显示三个子命令。"""
    from src.m1_image_engine.cli import build_parser

    parser = build_parser()
    # 触发解析 --help 应当 SystemExit 0
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--help"])
    assert exc_info.value.code == 0


def test_cli_process_command(tmp_path, tmp_image_path, canvas_with_blue_handwriting, capsys):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "in.jpg")
    out_dir = str(tmp_path / "out")
    from src.m1_image_engine.cli import main

    rc = main(["process", in_path, out_dir])
    assert rc == 0
    out = capsys.readouterr().out
    assert "processed_path" in out


def test_cli_mask_command(tmp_path, tmp_image_path, canvas_with_blue_handwriting):
    in_path = tmp_image_path(canvas_with_blue_handwriting, "in.jpg")
    mask_path = str(tmp_path / "mask.png")
    from src.m1_image_engine.cli import main

    rc = main(["mask", in_path, mask_path])
    assert rc == 0
    assert os.path.exists(mask_path)


def test_cli_batch_command(tmp_path, tmp_image_path, canvas_with_blue_handwriting, white_canvas):
    in_dir = tmp_path / "in_dir"
    in_dir.mkdir()
    # 在 in_dir 内放两张图（绕过 tmp_image_path 的工厂机制，直接保存）
    from src.m1_image_engine.utils import bgr_to_pil

    bgr_to_pil(canvas_with_blue_handwriting).save(str(in_dir / "a.jpg"), "JPEG", quality=95)
    bgr_to_pil(white_canvas).save(str(in_dir / "b.jpg"), "JPEG", quality=95)
    out_dir = str(tmp_path / "out_dir")
    from src.m1_image_engine.cli import main

    rc = main(["batch", str(in_dir), out_dir])
    assert rc == 0
    assert os.path.isdir(os.path.join(out_dir, "a"))
    assert os.path.isdir(os.path.join(out_dir, "b"))


def test_cli_batch_empty_dir(tmp_path, capsys):
    in_dir = tmp_path / "empty"
    in_dir.mkdir()
    out_dir = str(tmp_path / "out")
    from src.m1_image_engine.cli import main

    rc = main(["batch", str(in_dir), out_dir])
    assert rc == 0
    out = capsys.readouterr().out
    assert "\"total\": 0" in out


def test_cli_batch_missing_dir(tmp_path):
    from src.m1_image_engine.cli import main

    rc = main(["batch", "/nonexistent/in_dir", str(tmp_path / "out")])
    assert rc == 2
