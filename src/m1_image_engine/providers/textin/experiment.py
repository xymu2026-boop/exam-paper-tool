"""TextIn 实验主入口 — python -m src.m1_image_engine.providers.textin.experiment"""

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


def run_one_sample(sample_path, preset, client, out_dir):
    res_out = out_dir / "responses"
    res_out.mkdir(parents=True, exist_ok=True)
    image_bytes = sample_path.read_bytes()
    t0 = time.monotonic()
    result = {"preset": preset["name"], "pipeline": preset["pipeline"], "ok": False,
              "output_path": None, "x_request_id": None, "error": None, "stage_failed": None}

    try:
        if preset["pipeline"] == "direct_erase":
            r = client.handwritten_erase(image_bytes, **preset["erase_params"])
            result["duration_ms"] = r.get("duration_ms", 0)
            result["x_request_id"] = r.get("x_request_id", "")
            with open(res_out / f"{preset['name']}.json", "w", encoding="utf-8") as f:
                json.dump(r.get("response_json", {}), f, ensure_ascii=False, indent=2)
            if not r["ok"]:
                result["error"] = r.get("error", "unknown")
                return result
            out_path = out_dir / f"{preset['name']}.jpg"
            out_path.write_bytes(r["image_bytes"])
            result["ok"] = True
            result["output_path"] = str(out_path)
        elif preset["pipeline"] == "enhance_then_erase":
            t_enhance = time.monotonic()
            e = client.crop_enhance_image(image_bytes, **preset["enhance_params"])
            with open(res_out / f"{preset['name']}_enhance.json", "w", encoding="utf-8") as f:
                json.dump(e.get("response_json", {}), f, ensure_ascii=False, indent=2)
            result["x_request_id"] = e.get("x_request_id", "")
            if not e["ok"]:
                result["duration_ms"] = e.get("duration_ms", 0)
                result["error"] = e.get("error", "unknown")
                result["stage_failed"] = "crop_enhance_image"
                return result
            enhanced_path = out_dir / f"{preset['name']}_enhanced.jpg"
            enhanced_path.write_bytes(e["image_bytes"])
            result["enhanced_path"] = str(enhanced_path)

            t_erase = time.monotonic()
            er = client.handwritten_erase(e["image_bytes"], **preset["erase_params"])
            with open(res_out / f"{preset['name']}_erase.json", "w", encoding="utf-8") as f:
                json.dump(er.get("response_json", {}), f, ensure_ascii=False, indent=2)
            result["duration_ms"] = e.get("duration_ms", 0) + er.get("duration_ms", 0)
            result["x_request_id"] = result["x_request_id"] + " | " + er.get("x_request_id", "")
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


def run_all():
    images = sorted(list(INPUT_DIR.glob("*.jpg")) + list(INPUT_DIR.glob("*.png")) + list(INPUT_DIR.glob("*.jpeg")))
    if not images:
        print("input/ 目录无图片，请放入 JPG/PNG 样本后重试")
        return

    client = TextInClient()
    for sample_path in images:
        sample_name = sample_path.stem
        out_dir = OUTPUT_DIR / sample_name
        out_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(sample_path, out_dir / "original.jpg")

        meta = {"sample": sample_name, "input_path": str(sample_path),
                "input_size_bytes": sample_path.stat().st_size, "results": []}

        for preset in PRESETS:
            print(f"  [{preset['name']}] ... ", end="", flush=True)
            r = run_one_sample(sample_path, preset, client, out_dir)
            meta["results"].append(r)
            if r["ok"]: print(f"✅ {r['duration_ms']}ms")
            else: print(f"❌ {r.get('error','?')}")

        with open(out_dir / "meta.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2, default=str)


if __name__ == "__main__":
    run_all()


STAGE_LABELS = ["original", "A1_default", "A2_no_sharpen", "B1_geom_only", "B2_deshadow"]

def _img_info(path):
    try:
        from PIL import Image
        img = Image.open(path)
        return img.size[0], img.size[1], path.stat().st_size
    except Exception:
        return 0, 0, 0


def generate_compare_html():
    samples = sorted(d for d in OUTPUT_DIR.iterdir() if d.is_dir())
    if not samples:
        return

    COMPARISON_DIR.mkdir(parents=True, exist_ok=True)

    for sample_dir in samples:
        name = sample_dir.name
        meta_path = sample_dir / "meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        results = {r["preset"]: r for r in meta.get("results", [])}

        html = '<!doctype html><html lang="zh"><head><meta charset="UTF-8">'
        html += f'<title>{name} — TextIn 实验对比</title>'
        html += '<style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:16px}'
        html += 'h2{border-bottom:1px solid #333;padding-bottom:8px}'
        html += '.grid{display:flex;gap:12px;overflow-x:auto;margin-bottom:24px}'
        html += '.card{min-width:220px;flex:1;background:#1a1a2e;border-radius:8px;overflow:hidden}'
        html += '.card.fail{background:#3b1111}'
        html += '.card img{width:100%;display:block}'
        html += '.card .info{padding:10px;font-size:12px;color:#aaa;line-height:1.6}'
        html += '.card .name{font-weight:700;color:#fff;font-size:14px}'
        html += '.card .err{color:#f87171}'
        html += '.card .ok{color:#34d399}'
        html += '</style></head><body>'
        html += f'<h2>{name}</h2><div class="grid">'

        for stage in STAGE_LABELS:
            err = ""
            r = {}
            if stage == "original":
                path = sample_dir / "original.jpg"
                label = "原图"
                dur = "-"
                ok = True
            else:
                path = sample_dir / f"{stage}.jpg"
                r = results.get(stage, {})
                ok = r.get("ok", False)
                dur = f"{r.get('duration_ms', '?')}ms"
                err = r.get("error", "")
                label = stage
            w, h, size = _img_info(path) if path.exists() else (0, 0, 0)
            fail_class = ' fail' if not ok else ''
            html += f'<div class="card{fail_class}">'
            html += f'<div class="name">{label}</div>'
            if path.exists():
                html += f'<img src="../output/{name}/{path.name}" alt="{label}" loading="lazy">'
            else:
                html += f'<div style="min-height:150px;background:#111;display:flex;align-items:center;justify-content:center;color:#666">无图片</div>'
            html += f'<div class="info">'
            html += f'{"<span class=ok>✅</span>" if ok else "<span class=err>❌</span>"} '
            html += f'{w}×{h} · {size//1024}KB · {dur}'
            if err:
                html += f'<br><span class="err">{err}</span>'
            if r.get("stage_failed"):
                html += f'<br>failed at: {r["stage_failed"]}'
            html += '</div></div>'

        html += '</div></body></html>'
        (sample_dir / "compare.html").write_text(html, encoding="utf-8")

    with open(COMPARISON_DIR / "index.html", "w", encoding="utf-8") as f:
        f.write('<!doctype html><html lang="zh"><head><meta charset="UTF-8"><title>TextIn 实验总览</title>')
        f.write('<style>body{font-family:system-ui;background:#111;color:#eee;margin:20px}')
        f.write('a{color:#60a5fa}h1{font-size:20px}li{margin:8px 0}</style></head><body>')
        f.write('<h1>TextIn 实验对比</h1><ul>')
        for sample_dir in samples:
            f.write(f'<li><a href="../output/{sample_dir.name}/compare.html">{sample_dir.name}</a></li>')
        f.write('</ul></body></html>')


if __name__ == "__main__":
    run_all()
    generate_compare_html()
    print(f"\n对比页: {COMPARISON_DIR.resolve()}/index.html")
