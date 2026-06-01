"""TextIn 实验 — CLI入口 + 可复用 pipeline 函数"""

from __future__ import annotations

import json, os, shutil, sys, time
from pathlib import Path

def _load_dotenv():
    env_file = Path(__file__).resolve().parents[4] / ".env"
    if not env_file.exists():
        return
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
_load_dotenv()

from .client import TextInClient
from .presets import PRESETS

INPUT_DIR = Path("data/api_eval/textin/input")
OUTPUT_DIR = Path("data/api_eval/textin/output")
COMPARISON_DIR = Path("data/api_eval/textin/comparison")


def _run_one_preset(image_bytes, preset, client, out_dir):
    res_out = out_dir / "responses"
    res_out.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    result = {"preset": preset["name"], "pipeline": preset["pipeline"], "ok": False,
              "description": preset.get("description", ""),
              "output_path": None, "x_request_id": None, "error": None, "stage_failed": None}

    try:
        if preset["pipeline"] == "direct_erase":
            r = client.handwritten_erase(image_bytes, **preset["erase_params"])
            result["duration_ms"] = r.get("duration_ms", 0)
            result["x_request_id"] = r.get("x_request_id", "")
            _save_json(res_out / f"{preset['name']}.json", r.get("response_json", {}))
            if not r["ok"]:
                result["error"] = r.get("error", "unknown")
                return result
            out_path = out_dir / f"{preset['name']}.jpg"
            out_path.write_bytes(r["image_bytes"])
            result["ok"] = True
            result["output_path"] = str(out_path)
        elif preset["pipeline"] == "enhance_then_erase":
            e = client.crop_enhance_image(image_bytes, **preset["enhance_params"])
            _save_json(res_out / f"{preset['name']}_enhance.json", e.get("response_json", {}))
            result["x_request_id"] = e.get("x_request_id", "")
            if not e["ok"]:
                result["duration_ms"] = e.get("duration_ms", 0)
                result["error"] = e.get("error", "unknown")
                result["stage_failed"] = "crop_enhance_image"
                return result
            enhanced_path = out_dir / f"{preset['name']}_enhanced.jpg"
            enhanced_path.write_bytes(e["image_bytes"])
            er = client.handwritten_erase(e["image_bytes"], **preset["erase_params"])
            _save_json(res_out / f"{preset['name']}_erase.json", er.get("response_json", {}))
            result["duration_ms"] = e.get("duration_ms", 0) + er.get("duration_ms", 0)
            result["x_request_id"] += " | " + er.get("x_request_id", "")
            if not er["ok"]:
                result["error"] = er.get("error", "unknown")
                result["stage_failed"] = "handwritten_erase"
                return result
            out_path = out_dir / f"{preset['name']}.jpg"
            out_path.write_bytes(er["image_bytes"])
            result["ok"] = True
            result["output_path"] = str(out_path)
        else:
            result["error"] = f"unknown pipeline: {preset['pipeline']}"
    except Exception as e:
        result["duration_ms"] = int((time.monotonic() - t0) * 1000)
        result["error"] = str(e)
    return result


def _save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def run_textin_presets(image_bytes, output_dir, preset_filter=None):
    """可复用函数 — 对一张图跑 TextIn preset。

    Args:
        image_bytes: 图片二进制数据
        output_dir: 输出目录 (Path 或 str)
        preset_filter: 要跑的 preset 名列表, None=全部

    Returns:
        {"ok": bool, "job_id": str, "results": [...], "errors": [...]}
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "responses").mkdir(exist_ok=True)

    client = TextInClient()
    presets = PRESETS
    if preset_filter:
        presets = [p for p in PRESETS if p["name"] in preset_filter]

    results = []
    errors = []
    for preset in presets:
        r = _run_one_preset(image_bytes, preset, client, out)
        results.append(r)
        if not r["ok"]:
            errors.append(f"[{preset['name']}] {r.get('error', 'unknown')}")

    meta = {"results": results}
    _save_json(out / "meta.json", meta)

    return {"ok": len(errors) == 0, "job_id": out.name, "results": results, "errors": errors}


# ── CLI ──

def run_all():
    images = sorted(list(INPUT_DIR.glob("*.jpg")) + list(INPUT_DIR.glob("*.png")) + list(INPUT_DIR.glob("*.jpeg")))
    if not images:
        print("input/ 目录无图片，请放入 JPG/PNG 样本后重试")
        return
    client = TextInClient()
    for sample_path in images:
        name = sample_path.stem
        out_dir = OUTPUT_DIR / name
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(sample_path, out_dir / "original.jpg")
        image_bytes = sample_path.read_bytes()
        for preset in PRESETS:
            print(f"  [{preset['name']}] ... ", end="", flush=True)
            r = _run_one_preset(image_bytes, preset, client, out_dir)
            print(f"{'✅ '+str(r['duration_ms'])+'ms' if r['ok'] else '❌ '+str(r.get('error','?'))}")
        meta = {"sample": name, "results": []}
        meta_path = out_dir / "meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
        _save_json(meta_path, meta)


STAGE_LABELS = ["original", "A1_default", "A2_no_sharpen", "B1_geom_only", "B2_deshadow"]

def _img_info(path):
    try:
        from PIL import Image
        img = Image.open(path)
        return img.size[0], img.size[1], path.stat().st_size
    except: return 0, 0, 0

def generate_compare_html():
    samples = sorted(d for d in OUTPUT_DIR.iterdir() if d.is_dir())
    if not samples: return
    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)
    for sample_dir in samples:
        name = sample_dir.name
        meta_path = sample_dir / "meta.json"
        if not meta_path.exists(): continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        results = {r["preset"]: r for r in meta.get("results", [])}
        html = '<!doctype html><html lang="zh"><head><meta charset="UTF-8">'
        html += f'<title>{name}</title><style>body{{font-family:system-ui;background:#111;color:#eee;margin:16px}}'
        html += 'h2{border-bottom:1px solid #333}.grid{display:flex;gap:12px;overflow-x:auto}'
        html += '.card{min-width:220px;flex:1;background:#1a1a2e;border-radius:8px;overflow:hidden}'
        html += '.card.fail{background:#3b1111}.card img{width:100%}.card .info{padding:10px;font-size:12px;color:#aaa}'
        html += '.card .name{font-weight:700;color:#fff;font-size:14px;padding:8px}'
        html += '.err{color:#f87171}.okc{color:#34d399}</style></head><body>'
        html += f'<h2>{name}</h2><div class="grid">'
        for stage in STAGE_LABELS:
            err = ""; r = {}
            if stage == "original":
                path = sample_dir / "original.jpg"; label = "原图"; dur = "-"; ok = True
            else:
                path = sample_dir / f"{stage}.jpg"
                r = results.get(stage, {})
                ok = r.get("ok", False); dur = f"{r.get('duration_ms','?')}ms"; err = r.get("error",""); label = stage
            w, h, size = _img_info(path) if path.exists() else (0, 0, 0)
            fc = ' fail' if not ok else ''
            html += f'<div class="card{fc}"><div class="name">{label}</div>'
            if path.exists():
                html += f'<img src="../output/{name}/{path.name}" alt="{label}" loading="lazy">'
            else:
                html += '<div style="min-height:150px;background:#111;display:flex;align-items:center;justify-content:center;color:#666">无图片</div>'
            html += f'<div class="info"><span class="{"okc" if ok else "err"}">{"✅" if ok else "❌"}</span> {w}×{h} · {size//1024}KB · {dur}'
            if err: html += f'<br><span class="err">{err}</span>'
            if r.get("stage_failed"): html += f'<br>failed: {r["stage_failed"]}'
            html += '</div></div>'
        html += '</div></body></html>'
        (sample_dir / "compare.html").write_text(html, encoding="utf-8")
    with open(COMPARISON_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write('<!doctype html><html lang="zh"><head><meta charset="UTF-8"><title>TextIn 实验总览</title>')
        f.write('<style>body{font-family:system-ui;background:#111;color:#eee;margin:20px}a{color:#60a5fa}li{margin:8px 0}</style></head><body><h1>TextIn 实验对比</h1><ul>')
        for d in samples: f.write(f'<li><a href="../output/{d.name}/compare.html">{d.name}</a></li>')
        f.write('</ul></body></html>')

if __name__ == "__main__":
    run_all()
    generate_compare_html()
    print(f"\n对比页: {COMPARISON_DIR.resolve()}/index.html")
