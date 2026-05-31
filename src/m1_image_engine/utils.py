"""图像加载与文件 I/O 工具函数。

负责：
- HEIC 解码器注册（graceful fallback）
- 统一的图片读取入口（返回 PIL Image，RGB 模式）
- PIL / OpenCV 数组互转
- 路径与目录操作
"""

from __future__ import annotations

import os
from typing import Optional

import cv2
import numpy as np
from PIL import Image

# --- HEIC graceful fallback ---
try:
    from pillow_heif import register_heif_opener  # type: ignore

    register_heif_opener()
    HEIC_SUPPORTED: bool = True
except Exception:  # pragma: no cover - environment dependent
    HEIC_SUPPORTED = False


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".heic", ".heif"}


def is_heic(path: str) -> bool:
    """判断路径是否为 HEIC / HEIF 文件。"""
    ext = os.path.splitext(path)[1].lower()
    return ext in (".heic", ".heif")


def is_supported_image(path: str) -> bool:
    """判断扩展名是否在支持列表内。"""
    ext = os.path.splitext(path)[1].lower()
    return ext in SUPPORTED_EXTS


def ensure_dir(path: str) -> None:
    """递归创建目录（已存在则忽略）。"""
    if not path:
        return
    os.makedirs(path, exist_ok=True)


def load_image_pil(path: str) -> Image.Image:
    """以 PIL 方式加载图片，统一返回 RGB 模式。

    Raises:
        FileNotFoundError: 文件不存在
        RuntimeError: HEIC 文件但 pillow-heif 未安装
        OSError / Image.UnidentifiedImageError: 图片损坏或格式不支持
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"image not found: {path}")
    if is_heic(path) and not HEIC_SUPPORTED:
        raise RuntimeError(
            "HEIC not supported: install pillow-heif (pip install pillow-heif)"
        )
    img = Image.open(path)
    # 强制加载像素数据并转 RGB（避免 lazy 与色彩空间陷阱）
    img.load()
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    """PIL Image (RGB) -> OpenCV BGR ndarray。"""
    arr = np.array(img)
    if arr.ndim == 2:
        return cv2.cvtColor(arr, cv2.COLOR_GRAY2BGR)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def bgr_to_pil(arr: np.ndarray) -> Image.Image:
    """OpenCV BGR ndarray -> PIL Image (RGB)。"""
    if arr.ndim == 2:
        return Image.fromarray(arr, mode="L")
    return Image.fromarray(cv2.cvtColor(arr, cv2.COLOR_BGR2RGB), mode="RGB")


def save_bgr_jpeg(arr: np.ndarray, path: str, quality: int = 95) -> bool:
    """保存 BGR 数组为 JPEG 文件。

    使用 PIL 写入，避免 cv2.imwrite 在某些平台对中文路径的问题。
    """
    ensure_dir(os.path.dirname(path))
    try:
        pil_img = bgr_to_pil(arr)
        pil_img.save(path, format="JPEG", quality=quality)
        return True
    except Exception:
        return False


def save_gray(arr: np.ndarray, path: str) -> bool:
    """保存单通道灰度 mask。"""
    ensure_dir(os.path.dirname(path))
    try:
        if arr.dtype != np.uint8:
            arr = arr.astype(np.uint8)
        Image.fromarray(arr, mode="L").save(path)
        return True
    except Exception:
        return False


def load_gray(path: str) -> Optional[np.ndarray]:
    """加载灰度 mask。失败返回 None。"""
    try:
        if not os.path.exists(path):
            return None
        img = Image.open(path)
        img.load()
        if img.mode != "L":
            img = img.convert("L")
        return np.array(img, dtype=np.uint8)
    except Exception:
        return None


def load_bgr(path: str) -> Optional[np.ndarray]:
    """加载图片为 BGR ndarray。失败返回 None。"""
    try:
        pil = load_image_pil(path)
        return pil_to_bgr(pil)
    except Exception:
        return None


__all__ = [
    "HEIC_SUPPORTED",
    "SUPPORTED_EXTS",
    "is_heic",
    "is_supported_image",
    "ensure_dir",
    "load_image_pil",
    "pil_to_bgr",
    "bgr_to_pil",
    "save_bgr_jpeg",
    "save_gray",
    "load_gray",
    "load_bgr",
]
