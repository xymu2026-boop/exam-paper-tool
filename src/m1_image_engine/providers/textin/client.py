"""TextIn API client — handwritten_erase + crop_enhance_image. Stdlib only."""

from __future__ import annotations

import base64, json, os, time, urllib.request, urllib.error
from typing import Optional


class TextInError(Exception):
    pass


class TextInClient:
    BASE = "https://api.textin.com/ai/service/v1"

    def __init__(self):
        self.app_id = os.environ.get("TEXTIN_APP_ID", "")
        self.secret = os.environ.get("TEXTIN_SECRET_CODE", "")
        if not self.app_id or not self.secret:
            raise TextInError("未设置 TEXTIN_APP_ID 或 TEXTIN_SECRET_CODE。请复制 .env.example 为 .env 并填入密钥。")

    def _request(self, endpoint, image_bytes, extra_fields=None):
        url = f"{self.BASE}/{endpoint}"
        if extra_fields:
            params = {k: str(v) for k, v in extra_fields.items() if v is not None}
            qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
            url = f"{url}?{qs}"
        headers = {"x-ti-app-id": self.app_id, "x-ti-secret-code": self.secret, "Content-Type": "application/octet-stream"}
        req = urllib.request.Request(url, data=image_bytes, headers=headers, method="POST")
        t0 = time.monotonic()
        try:
            resp = urllib.request.urlopen(req, timeout=60)
            duration_ms = int((time.monotonic() - t0) * 1000)
            body = resp.read()
            rj = json.loads(body) if body else {}
            return {"ok": True, "response_json": rj, "duration_ms": duration_ms, "x_request_id": resp.headers.get("x-ti-request-id", "")}
        except urllib.error.HTTPError as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            body = e.read()
            rj = json.loads(body) if body else {}
            code = rj.get("code", e.code)
            msg = rj.get("message", str(e))
            return {"ok": False, "image_bytes": None, "response_json": rj, "duration_ms": duration_ms, "error": f"{code} {msg}", "x_request_id": e.headers.get("x-ti-request-id", "")}
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            msg = str(e)
            if "timed out" in msg.lower(): msg = "请求超时 (60s)"
            return {"ok": False, "image_bytes": None, "response_json": {}, "duration_ms": duration_ms, "error": msg, "x_request_id": None}

    def handwritten_erase(self, image_bytes, *, crop=0, crop_position=None, doc_direction=0,
                          mask_position=None, dewarp=1, binarization=1, image_type=1):
        r = self._request("handwritten_erase", image_bytes, extra_fields={
            "crop": crop, "crop_position": crop_position, "doc_direction": doc_direction,
            "mask_position": mask_position, "dewarp": dewarp, "binarization": binarization,
            "image_type": image_type,
        })
        if not r["ok"]: return r
        try:
            r["image_bytes"] = base64.b64decode(r["response_json"]["result"]["image"])
        except Exception:
            r["ok"] = False; r["image_bytes"] = None; r["error"] = "response 缺少 result.image"
        return r

    def crop_enhance_image(self, image_bytes, *, enhance_mode=-1, crop_image=1, only_position=0,
                           dewarp_image=1, deblur_image=0, correct_direction=0, round_image=0,
                           jpeg_quality=95, size_and_positon=None):
        r = self._request("crop_enhance_image", image_bytes, extra_fields={
            "enhance_mode": enhance_mode, "crop_image": crop_image, "only_position": only_position,
            "dewarp_image": dewarp_image, "deblur_image": deblur_image,
            "correct_direction": correct_direction, "round_image": round_image,
            "jpeg_quality": jpeg_quality, "size_and_positon": size_and_positon,
        })
        if not r["ok"]: return r
        try:
            img_list = r["response_json"]["result"]["image_list"]
            if not img_list:
                r["ok"] = False; r["image_bytes"] = None; r["error"] = "image_list 为空"
                return r
            item = img_list[0]
            r["image_bytes"] = base64.b64decode(item["image"])
            r["position"] = item.get("position")
            r["angle"] = item.get("angle")
        except Exception:
            r["ok"] = False; r["image_bytes"] = None; r["error"] = "response 结构解析失败"
        return r
