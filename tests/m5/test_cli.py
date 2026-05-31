"""CLI tests — invoke the entry point as a subprocess and via main()."""

from __future__ import annotations

import os
import subprocess
import sys

from src.m5_pdf_export.cli import main as cli_main


PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)


def _run_cli(args, env_extra=None):
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "src.m5_pdf_export.cli", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        env=env,
    )


def test_cli_export_basic(single_image, tmp_path):
    out = tmp_path / "cli_basic.pdf"
    result = _run_cli(["export", single_image, "-o", str(out)])
    assert result.returncode == 0, result.stderr
    assert out.is_file()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_cli_export_two_per_page(sample_images, tmp_path):
    out = tmp_path / "cli_two.pdf"
    result = _run_cli(
        ["export", *sample_images, "-o", str(out), "--layout", "two_per_page"]
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_cli_export_compact_with_title(sample_images, tmp_path):
    out = tmp_path / "cli_compact.pdf"
    result = _run_cli(
        [
            "export",
            *sample_images,
            "-o",
            str(out),
            "--layout",
            "compact",
            "--title",
            "K1 Math Mistakes",
        ]
    )
    assert result.returncode == 0, result.stderr
    assert out.is_file()


def test_cli_export_help_exits_zero():
    result = _run_cli(["export", "--help"])
    assert result.returncode == 0
    assert "layout" in result.stdout


def test_cli_main_returns_zero_in_process(single_image, tmp_path):
    out = tmp_path / "in_proc.pdf"
    code = cli_main(["export", single_image, "-o", str(out)])
    assert code == 0
    assert out.is_file()


def test_cli_main_returns_nonzero_on_missing_input(tmp_path):
    out = tmp_path / "wont_exist.pdf"
    code = cli_main(["export", "/no/such/file.png", "-o", str(out)])
    assert code == 1
    assert not out.exists()


def test_cli_rejects_invalid_layout(single_image, tmp_path):
    out = tmp_path / "x.pdf"
    result = _run_cli(
        ["export", single_image, "-o", str(out), "--layout", "bogus"]
    )
    assert result.returncode != 0
