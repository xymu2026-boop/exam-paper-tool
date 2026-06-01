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
            # B-line in Commit 3
            result["ok"] = False
            result["error"] = "B线 Commit 3 实现"
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
