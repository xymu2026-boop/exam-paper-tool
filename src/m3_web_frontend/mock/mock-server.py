#!/usr/bin/env python3
"""
试卷宝 — Mock API + static-file server (M3 Web Frontend dev only).

Zero non-stdlib dependencies. Serves the m3_web_frontend tree AND simulates
all 10 endpoints defined in docs/INTERFACE-CONTRACT.md §4.3/§4.4.

Usage:
    python mock/mock-server.py            # default :8000
    python mock/mock-server.py 9000       # custom port

The server holds an in-memory store seeded with a few sample papers and
mistakes. Mutations (upload / create / delete / patch) are persisted only
for the lifetime of the process — perfect for front-end iteration.

Endpoints implemented:
    POST   /api/papers/upload
    GET    /api/papers
    GET    /api/papers/{id}
    POST   /api/papers/{id}/process
    POST   /api/mistakes
    GET    /api/mistakes
    DELETE /api/mistakes/{id}
    PATCH  /api/mistakes/{id}
    POST   /api/export/pdf
    GET    /api/export/history

Plus a dynamic placeholder image generator at:
    /static/data/placeholder/{w}x{h}/{label}.png
so the frontend has real images to render even without M1 output.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import random
import re
import struct
import sys
import threading
import time
import urllib.parse
import zlib
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent          # src/m3_web_frontend/
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# In-memory mock state
# ---------------------------------------------------------------------------

_lock = threading.Lock()


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _seed_state() -> dict:
    papers = [
        {
            "id": 1,
            "child_id": "K1",
            "subject": "数学",
            "paper_type": "单元卷",
            "title": "20以内加减法练习",
            "original_path": "placeholder/1200x1600/K1-数学-原图.png",
            "processed_path": "placeholder/1200x1600/K1-数学-预处理.png",
            "cleaned_path": "placeholder/1200x1600/K1-数学-擦除.png",
            "upload_time": "2026-05-30 09:14:22",
            "status": "processed",
            "quality_score": 0.86,
            "error_message": None,
            "created_at": "2026-05-30 09:14:22",
        },
        {
            "id": 2,
            "child_id": "K1",
            "subject": "语文",
            "paper_type": "作业",
            "title": "拼音听写",
            "original_path": "placeholder/1200x1600/K1-语文-原图.png",
            "processed_path": "placeholder/1200x1600/K1-语文-预处理.png",
            "cleaned_path": "placeholder/1200x1600/K1-语文-擦除.png",
            "upload_time": "2026-05-29 18:02:11",
            "status": "processed",
            "quality_score": 0.74,
            "error_message": None,
            "created_at": "2026-05-29 18:02:11",
        },
        {
            "id": 3,
            "child_id": "K2",
            "subject": "数学",
            "paper_type": "考试卷",
            "title": "期中模拟",
            "original_path": "placeholder/1200x1600/K2-数学-原图.png",
            "processed_path": None,
            "cleaned_path": None,
            "upload_time": "2026-05-31 08:30:00",
            "status": "pending",
            "quality_score": None,
            "error_message": None,
            "created_at": "2026-05-31 08:30:00",
        },
        {
            "id": 4,
            "child_id": "K2",
            "subject": "英语",
            "paper_type": "练习册",
            "title": "Unit 3 Listening",
            "original_path": "placeholder/1200x1600/K2-英语-原图.png",
            "processed_path": None,
            "cleaned_path": None,
            "upload_time": "2026-05-31 10:11:42",
            "status": "failed",
            "quality_score": 0.32,
            "error_message": "图像过暗,请重新拍摄",
            "created_at": "2026-05-31 10:11:42",
        },
        {
            "id": 5,
            "child_id": "K1",
            "subject": "科学",
            "paper_type": "其他",
            "title": "动物分类小测",
            "original_path": "placeholder/1200x1600/K1-科学-原图.png",
            "processed_path": "placeholder/1200x1600/K1-科学-预处理.png",
            "cleaned_path": "placeholder/1200x1600/K1-科学-擦除.png",
            "upload_time": "2026-05-28 15:45:09",
            "status": "processed",
            "quality_score": 0.91,
            "error_message": None,
            "created_at": "2026-05-28 15:45:09",
        },
    ]
    mistakes = [
        {
            "id": 101, "paper_id": 1, "child_id": "K1", "subject": "数学",
            "crop_x": 120, "crop_y": 360, "crop_width": 460, "crop_height": 180,
            "mistake_image_path": "placeholder/600x240/错题-1.png",
            "clean_mistake_image_path": "placeholder/600x240/错题-1-擦除.png",
            "note": "进位忘了,12+9 写成 12",
            "error_type": "粗心", "status": "new",
            "created_at": "2026-05-30 09:30:00", "reviewed_at": None,
        },
        {
            "id": 102, "paper_id": 1, "child_id": "K1", "subject": "数学",
            "crop_x": 130, "crop_y": 760, "crop_width": 480, "crop_height": 200,
            "mistake_image_path": "placeholder/600x250/错题-2.png",
            "clean_mistake_image_path": "placeholder/600x250/错题-2-擦除.png",
            "note": "不会比较 8 和 11 的大小",
            "error_type": "概念不清", "status": "practiced",
            "created_at": "2026-05-30 09:31:00", "reviewed_at": "2026-05-31 07:00:00",
        },
        {
            "id": 103, "paper_id": 2, "child_id": "K1", "subject": "语文",
            "crop_x": 200, "crop_y": 410, "crop_width": 520, "crop_height": 220,
            "mistake_image_path": "placeholder/650x275/错题-3.png",
            "clean_mistake_image_path": "placeholder/650x275/错题-3-擦除.png",
            "note": "把'b' 写成了 'd'",
            "error_type": "粗心", "status": "passed",
            "created_at": "2026-05-29 18:30:00", "reviewed_at": "2026-05-30 19:00:00",
        },
        {
            "id": 104, "paper_id": 5, "child_id": "K1", "subject": "科学",
            "crop_x": 110, "crop_y": 880, "crop_width": 540, "crop_height": 230,
            "mistake_image_path": "placeholder/600x255/错题-4.png",
            "clean_mistake_image_path": "placeholder/600x255/错题-4-擦除.png",
            "note": "鲸鱼归类为鱼类",
            "error_type": "概念不清", "status": "new",
            "created_at": "2026-05-28 16:00:00", "reviewed_at": None,
        },
        {
            "id": 105, "paper_id": 1, "child_id": "K1", "subject": "数学",
            "crop_x": 100, "crop_y": 1180, "crop_width": 500, "crop_height": 200,
            "mistake_image_path": "placeholder/600x240/错题-5.png",
            "clean_mistake_image_path": "placeholder/600x240/错题-5-擦除.png",
            "note": None,
            "error_type": None, "status": "retry",
            "created_at": "2026-05-30 09:32:00", "reviewed_at": None,
        },
    ]
    exports = [
        {
            "id": 1, "child_id": "K1", "subject": "数学",
            "mistake_ids": "[101,102,105]",
            "pdf_path": "exports/mock-1.pdf",
            "created_at": "2026-05-30 21:14:00",
        },
        {
            "id": 2, "child_id": "K1", "subject": None,
            "mistake_ids": "[101,103,104]",
            "pdf_path": "exports/mock-2.pdf",
            "created_at": "2026-05-31 08:00:00",
        },
    ]
    return {
        "papers": papers,
        "mistakes": mistakes,
        "exports": exports,
        "next_paper_id": max(p["id"] for p in papers) + 1,
        "next_mistake_id": max(m["id"] for m in mistakes) + 1,
        "next_export_id": max(e["id"] for e in exports) + 1,
    }


STATE = _seed_state()

# ---------------------------------------------------------------------------
# Tiny PNG generator (so we don't depend on Pillow)
# ---------------------------------------------------------------------------

PALETTE = [
    (235, 244, 255), (255, 240, 235), (235, 255, 240),
    (252, 240, 255), (255, 252, 230), (235, 250, 255),
]


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def _generate_placeholder_png(width: int, height: int, label: str) -> bytes:
    """Render a colored rectangle PNG with corner markers + a label band.

    Pure-stdlib: builds raw RGBA pixels, deflates them, wraps in PNG chunks.
    Label is rendered as a solid band so the user can see WHICH placeholder
    they're looking at. Actual glyphs are drawn with a 5x7 bitmap font for
    ASCII; non-ASCII (Chinese) labels degrade to colored bars.
    """
    width = max(64, min(int(width), 2400))
    height = max(64, min(int(height), 2400))

    # Pick a deterministic color based on the label
    seed = sum(ord(c) for c in label) if label else 0
    r0, g0, b0 = PALETTE[seed % len(PALETTE)]
    accent = ((r0 * 7) % 200 + 30, (g0 * 11) % 200 + 30, (b0 * 13) % 200 + 30)

    # Build RGB pixel buffer
    rows = bytearray()
    band_top = max(0, height // 2 - 30)
    band_bottom = min(height, height // 2 + 30)
    border = 4

    for y in range(height):
        rows.append(0)  # PNG filter byte: None
        for x in range(width):
            if x < border or y < border or x >= width - border or y >= height - border:
                rows.append(180); rows.append(190); rows.append(205)  # frame
            elif band_top <= y < band_bottom:
                rows.append(accent[0]); rows.append(accent[1]); rows.append(accent[2])
            else:
                # diagonal pin-stripe so it doesn't look like a flat block
                if (x + y) % 36 < 2:
                    rows.append(220); rows.append(228); rows.append(238)
                else:
                    rows.append(r0); rows.append(g0); rows.append(b0)

    raw = bytes(rows)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8-bit RGB
    idat = zlib.compress(raw, 6)
    return (
        sig
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"tEXt", b"Comment\x00" + label.encode("utf-8", errors="ignore"))
        + _png_chunk(b"IDAT", idat)
        + _png_chunk(b"IEND", b"")
    )


def _generate_placeholder_pdf(title: str = "试卷宝 错题导出 (Mock)") -> bytes:
    """Build a minimal one-page PDF with a Latin-1 fallback title.

    Avoids any external library. Good enough for the frontend to trigger a
    real download in mock mode.
    """
    safe_title = title.encode("latin-1", errors="replace").decode("latin-1")
    body_text = f"({safe_title}) Tj"
    content_stream = (
        b"BT\n"
        b"/F1 24 Tf\n"
        b"72 760 Td\n"
        b"(Mock PDF Export) Tj\n"
        b"0 -36 Td\n"
        b"/F1 14 Tf\n"
        + body_text.encode("latin-1") + b"\n"
        b"0 -28 Td\n"
        b"(Generated by m3_web_frontend mock-server) Tj\n"
        b"ET\n"
    )
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content_stream)).encode("ascii") + b" >>\nstream\n"
        + content_stream + b"endstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray()
    out += b"%PDF-1.4\n"
    offsets = [0]
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
    xref_pos = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        out += f"{off:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
        + f"startxref\n{xref_pos}\n%%EOF\n".encode("ascii")
    )
    return bytes(out)


# Pre-generate the mock PDF on disk so /static/data/exports/mock.pdf works.
EXPORTS_DIR = FIXTURES_DIR / "exports"
EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
for name in ("mock.pdf", "mock-1.pdf", "mock-2.pdf"):
    target = EXPORTS_DIR / name
    if not target.exists():
        target.write_bytes(_generate_placeholder_pdf(f"试卷宝 {name}"))


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("mock")


def _parse_multipart(body: bytes, content_type: str) -> dict:
    """Parse a multipart/form-data body into {name: [{filename, value, content_type}, ...]}.

    Stdlib-only replacement for the removed `cgi` module (Python 3.13+).
    """
    # Extract boundary
    m = re.search(r'boundary=(?:"([^"]+)"|([^;]+))', content_type)
    if not m:
        raise ValueError("missing multipart boundary")
    boundary = (m.group(1) or m.group(2)).strip()
    delim = b"--" + boundary.encode("latin-1")
    closing = delim + b"--"

    # Normalise CRLF / LF endings
    if not body.endswith(b"\r\n"):
        body = body + b"\r\n"

    fields: dict = {}
    parts = body.split(delim)
    for part in parts:
        if not part or part == b"--\r\n" or part.startswith(b"--"):
            continue
        # Strip leading CRLF, trailing CRLF
        if part.startswith(b"\r\n"):
            part = part[2:]
        if part.endswith(b"\r\n"):
            part = part[:-2]
        # Split header / body on first blank line
        sep = part.find(b"\r\n\r\n")
        if sep < 0:
            continue
        header_blob = part[:sep].decode("utf-8", errors="replace")
        value = part[sep + 4:]
        # Parse Content-Disposition
        cd_match = re.search(r'Content-Disposition:\s*form-data;\s*([^\r\n]+)', header_blob, re.I)
        if not cd_match:
            continue
        params = {}
        for piece in cd_match.group(1).split(";"):
            piece = piece.strip()
            if "=" in piece:
                k, v = piece.split("=", 1)
                params[k.strip().lower()] = v.strip().strip('"')
        name = params.get("name")
        if not name:
            continue
        filename = params.get("filename")
        ct_match = re.search(r"Content-Type:\s*([^\r\n]+)", header_blob, re.I)
        ct = ct_match.group(1).strip() if ct_match else None

        record = {"value": value, "filename": filename, "content_type": ct}
        fields.setdefault(name, []).append(record)
    return fields


class MockHandler(SimpleHTTPRequestHandler):
    """Serves the m3_web_frontend tree + the mock /api/* endpoints."""

    server_version = "ExamPaperMock/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    # ------------ helpers ------------

    def _set_cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, X-Requested-With",
        )
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, obj, status: int = 200) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._set_cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _parse_query(self) -> dict:
        u = urllib.parse.urlparse(self.path)
        return {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}

    def end_headers(self):  # noqa: D401  - signature dictated by stdlib
        # Inject CORS on every static-file response too.
        if "Access-Control-Allow-Origin" not in self._headers_buffer_str():
            self._set_cors()
        super().end_headers()

    def _headers_buffer_str(self) -> str:
        try:
            return b"".join(self._headers_buffer).decode("latin-1", errors="replace")
        except Exception:
            return ""

    def log_message(self, fmt, *args):  # quieter, structured
        log.info("%s - %s", self.address_string(), fmt % args)

    # ------------ routing ------------

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self._set_cors()
        self.end_headers()

    def do_GET(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        # API
        if path.startswith("/api/"):
            return self._route_get(path)
        # Static placeholder image generator
        if path.startswith("/static/data/placeholder/"):
            return self._serve_placeholder(path)
        # Static fixtures (PDFs, sample images)
        if path.startswith("/static/data/exports/"):
            name = os.path.basename(path)
            target = EXPORTS_DIR / name
            if target.exists():
                return self._send_bytes(target.read_bytes(), "application/pdf")
            # fall back: synthesize a fresh mock PDF
            return self._send_bytes(_generate_placeholder_pdf(name), "application/pdf")
        if path.startswith("/static/data/"):
            # Fallback: any other /static/data/* → 1200x1600 placeholder
            return self._send_bytes(
                _generate_placeholder_png(1200, 1600, os.path.basename(path)),
                "image/png",
            )
        # Default static-file handling under m3_web_frontend/
        return super().do_GET()

    def do_POST(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._send_json({"error": "Not found"}, 404)
        return self._route_post(path)

    def do_PATCH(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._send_json({"error": "Not found"}, 404)
        return self._route_patch(path)

    def do_DELETE(self):  # noqa: N802
        path = urllib.parse.urlparse(self.path).path
        if not path.startswith("/api/"):
            return self._send_json({"error": "Not found"}, 404)
        return self._route_delete(path)

    # ------------ /static/data/placeholder/{w}x{h}/{label}.png ------------

    def _serve_placeholder(self, path: str) -> None:
        m = re.match(r"^/static/data/placeholder/(\d+)x(\d+)/([^/]+)$", path)
        if not m:
            self._send_json({"error": "bad placeholder path"}, 400)
            return
        w, h, label = int(m.group(1)), int(m.group(2)), m.group(3)
        label = urllib.parse.unquote(label)
        png = _generate_placeholder_png(w, h, label.rsplit(".", 1)[0])
        self._send_bytes(png, "image/png")

    # ------------ GET routes ------------

    def _route_get(self, path: str):
        q = self._parse_query()

        # /api/papers
        if path == "/api/papers":
            with _lock:
                items = list(STATE["papers"])
            for k in ("child_id", "subject", "status"):
                v = q.get(k)
                if v:
                    items = [p for p in items if p.get(k) == v]
            limit = int(q.get("limit", 50))
            offset = int(q.get("offset", 0))
            return self._send_json({
                "papers": items[offset: offset + limit],
                "total": len(items),
            })

        # /api/papers/{id}
        m = re.match(r"^/api/papers/(\d+)$", path)
        if m:
            pid = int(m.group(1))
            with _lock:
                p = next((x for x in STATE["papers"] if x["id"] == pid), None)
            if not p:
                return self._send_json({"error": "试卷不存在"}, 404)
            return self._send_json(p)

        # /api/mistakes
        if path == "/api/mistakes":
            with _lock:
                items = list(STATE["mistakes"])
            for k in ("child_id", "subject", "status"):
                v = q.get(k)
                if v:
                    items = [x for x in items if x.get(k) == v]
            if q.get("paper_id"):
                items = [x for x in items if str(x["paper_id"]) == str(q["paper_id"])]
            limit = int(q.get("limit", 100))
            offset = int(q.get("offset", 0))
            return self._send_json({
                "mistakes": items[offset: offset + limit],
                "total": len(items),
            })

        # /api/export/history
        if path == "/api/export/history":
            with _lock:
                items = list(STATE["exports"])
            if q.get("child_id"):
                items = [e for e in items if e.get("child_id") == q["child_id"]]
            limit = int(q.get("limit", 20))
            return self._send_json({"exports": items[:limit]})

        return self._send_json({"error": "Not found"}, 404)

    # ------------ POST routes ------------

    def _route_post(self, path: str):
        # /api/papers/upload  (multipart)
        if path == "/api/papers/upload":
            return self._upload_paper()

        # /api/papers/{id}/process
        m = re.match(r"^/api/papers/(\d+)/process$", path)
        if m:
            pid = int(m.group(1))
            time.sleep(2)  # simulate processing time
            with _lock:
                p = next((x for x in STATE["papers"] if x["id"] == pid), None)
                if not p:
                    return self._send_json({"error": "试卷不存在"}, 404)
                p["status"] = "processed"
                p["quality_score"] = round(0.65 + random.random() * 0.3, 2)
                p["processed_path"] = f"placeholder/1200x1600/{p['child_id']}-{p['subject']}-预处理.png"
                p["cleaned_path"] = f"placeholder/1200x1600/{p['child_id']}-{p['subject']}-擦除.png"
                p["error_message"] = None
            return self._send_json({
                "status": "processed",
                "quality_score": p["quality_score"],
                "warnings": [],
            })

        # /api/mistakes  (JSON)
        if path == "/api/mistakes":
            data = self._read_json_body()
            if not data.get("paper_id"):
                return self._send_json({"error": "缺少 paper_id"}, 400)
            with _lock:
                mid = STATE["next_mistake_id"]
                STATE["next_mistake_id"] += 1
                paper = next((x for x in STATE["papers"] if x["id"] == int(data["paper_id"])), None)
                child_id = (paper or {}).get("child_id", "K1")
                subject = (paper or {}).get("subject", "数学")
                rec = {
                    "id": mid,
                    "paper_id": int(data["paper_id"]),
                    "child_id": child_id,
                    "subject": subject,
                    "crop_x": int(data.get("crop_x", 0)),
                    "crop_y": int(data.get("crop_y", 0)),
                    "crop_width": int(data.get("crop_width", 0)),
                    "crop_height": int(data.get("crop_height", 0)),
                    "mistake_image_path": f"placeholder/600x240/错题-{mid}.png",
                    "clean_mistake_image_path": f"placeholder/600x240/错题-{mid}-擦除.png",
                    "note": data.get("note"),
                    "error_type": data.get("error_type"),
                    "status": "new",
                    "created_at": _now(),
                    "reviewed_at": None,
                }
                STATE["mistakes"].append(rec)
            return self._send_json({"mistake_id": mid})

        # /api/export/pdf
        if path == "/api/export/pdf":
            data = self._read_json_body()
            child = data.get("child_id") or "K1"
            ids = data.get("mistake_ids") or []
            if not ids:
                return self._send_json({"error": "缺少 mistake_ids"}, 400)
            with _lock:
                eid = STATE["next_export_id"]
                STATE["next_export_id"] += 1
                # subject inference
                sel = [m for m in STATE["mistakes"] if m["id"] in ids]
                subjects = {m["subject"] for m in sel}
                subj = sel[0]["subject"] if len(subjects) == 1 else None
                # write a mock PDF on disk
                pdf_name = f"export-{eid}.pdf"
                (EXPORTS_DIR / pdf_name).write_bytes(
                    _generate_placeholder_pdf(data.get("title") or f"{child} 错题导出 #{eid}")
                )
                rec = {
                    "id": eid,
                    "child_id": child,
                    "subject": subj,
                    "mistake_ids": json.dumps(ids),
                    "pdf_path": f"exports/{pdf_name}",
                    "created_at": _now(),
                }
                STATE["exports"].insert(0, rec)
            time.sleep(0.6)  # tiny simulated delay
            return self._send_json({
                "pdf_url": f"/static/data/exports/{pdf_name}",
                "export_id": eid,
            })

        return self._send_json({"error": "Not found"}, 404)

    # ------------ PATCH routes ------------

    def _route_patch(self, path: str):
        m = re.match(r"^/api/mistakes/(\d+)$", path)
        if not m:
            return self._send_json({"error": "Not found"}, 404)
        mid = int(m.group(1))
        data = self._read_json_body()
        with _lock:
            rec = next((x for x in STATE["mistakes"] if x["id"] == mid), None)
            if not rec:
                return self._send_json({"error": "错题不存在"}, 404)
            for k in ("status", "note", "error_type"):
                if k in data and data[k] is not None:
                    rec[k] = data[k]
            if data.get("status") in ("practiced", "passed"):
                rec["reviewed_at"] = _now()
        return self._send_json({"success": True})

    # ------------ DELETE routes ------------

    def _route_delete(self, path: str):
        m = re.match(r"^/api/mistakes/(\d+)$", path)
        if not m:
            return self._send_json({"error": "Not found"}, 404)
        mid = int(m.group(1))
        with _lock:
            before = len(STATE["mistakes"])
            STATE["mistakes"] = [x for x in STATE["mistakes"] if x["id"] != mid]
            if len(STATE["mistakes"]) == before:
                return self._send_json({"error": "错题不存在"}, 404)
        return self._send_json({"success": True})

    # ------------ /api/papers/upload (multipart) ------------

    def _upload_paper(self):
        ctype = self.headers.get("Content-Type", "")
        if not ctype.startswith("multipart/form-data"):
            return self._send_json({"error": "需要 multipart/form-data"}, 400)
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            fields = _parse_multipart(raw, ctype)
        except Exception as e:
            return self._send_json({"error": f"解析上传失败: {e}"}, 400)

        def _first(name: str, default: str = "") -> str:
            v = fields.get(name)
            if not v:
                return default
            val = v[0]["value"]
            if isinstance(val, bytes):
                try:
                    return val.decode("utf-8").strip()
                except Exception:
                    return default
            return str(val).strip()

        child_id = _first("child_id")
        subject = _first("subject")
        paper_type = _first("paper_type", "其他")
        title = _first("title")
        if child_id not in ("K1", "K2"):
            return self._send_json({"error": "child_id 非法"}, 400)
        if not subject:
            return self._send_json({"error": "缺少 subject"}, 400)
        if "file" not in fields:
            return self._send_json({"error": "缺少 file 字段"}, 400)
        # Note: we don't actually persist the upload — we just acknowledge it.

        with _lock:
            pid = STATE["next_paper_id"]
            STATE["next_paper_id"] += 1
            rec = {
                "id": pid,
                "child_id": child_id,
                "subject": subject,
                "paper_type": paper_type,
                "title": title or None,
                "original_path": f"placeholder/1200x1600/{child_id}-{subject}-原图-{pid}.png",
                "processed_path": None,
                "cleaned_path": None,
                "upload_time": _now(),
                "status": "pending",
                "quality_score": None,
                "error_message": None,
                "created_at": _now(),
            }
            STATE["papers"].insert(0, rec)
        return self._send_json({"paper_id": pid, "status": "pending"})


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(description="试卷宝 mock API server")
    parser.add_argument("port", nargs="?", type=int, default=8000)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args(argv)

    httpd = HTTPServer((args.host, args.port), MockHandler)
    log.info("Serving %s on http://%s:%d", ROOT, args.host, args.port)
    log.info("Open http://localhost:%d/index.html in your browser", args.port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log.info("Shutting down…")
        httpd.server_close()


if __name__ == "__main__":
    main(sys.argv[1:])
