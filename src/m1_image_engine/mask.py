"""Stage 2: Red + handwriting mask generation."""
import os, cv2
import numpy as np
from .utils import ensure_dir, load_image_pil, pil_to_bgr, save_gray

LAB_A_RED_LO, LAB_A_RED_HI = 130, 200
LAB_MIN_L, LAB_MAX_L = 30, 220
HW_GRAY_MAX, HW_GRAY_MIN = 150, 20
HW_MIN_AREA, HW_MAX_AREA = 15, 15000
HW_MAX_ASPECT = 20.0
K_SIZE = 2; RED_K = 5

def _red_mask_lab(bgr):
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    L, A = lab[:,:,0], lab[:,:,1]
    return ((A > LAB_A_RED_LO) & (L > LAB_MIN_L) & (L < LAB_MAX_L)).astype(np.uint8) * 255

def _hw_mask_gray(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    cand = ((gray < HW_GRAY_MAX) & (gray > HW_GRAY_MIN)).astype(np.uint8) * 255
    n, labels, stats, _ = cv2.connectedComponentsWithStats(cand, 8)
    result = np.zeros_like(gray, dtype=np.uint8)
    if n <= 1: return result
    for i in range(1, n):
        a, w, h = int(stats[i, cv2.CC_STAT_AREA]), int(stats[i, cv2.CC_STAT_WIDTH]), int(stats[i, cv2.CC_STAT_HEIGHT])
        if w == 0 or h == 0 or a < HW_MIN_AREA or a > HW_MAX_AREA: continue
        if max(w,h)/max(1,min(w,h)) > HW_MAX_ASPECT: continue
        result[labels == i] = 255
    return result

def generate_masks(input_path, output_dir):
    try:
        pil = load_image_pil(input_path)
        bgr = pil_to_bgr(pil)
    except: return {"red_mask_path":None,"hw_mask_path":None,"combined_mask_path":None}
    ensure_dir(output_dir)

    red = _red_mask_lab(bgr)
    if red is not None and np.count_nonzero(red) > 0:
        ks = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (K_SIZE,K_SIZE))
        kl = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (RED_K,RED_K))
        red = cv2.morphologyEx(red, cv2.MORPH_CLOSE, ks)
        red = cv2.dilate(red, kl, iterations=1)
        _, red = cv2.threshold(red, 127, 255, cv2.THRESH_BINARY)
    rp = os.path.join(output_dir, "red_mask.jpg"); rok = save_gray(red, rp)

    hw = _hw_mask_gray(bgr)
    if hw is not None and np.count_nonzero(hw) > 0:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (K_SIZE,K_SIZE))
        hw = cv2.morphologyEx(hw, cv2.MORPH_CLOSE, k)
        hw = cv2.dilate(hw, k, iterations=1)
        _, hw = cv2.threshold(hw, 127, 255, cv2.THRESH_BINARY)
    hp = os.path.join(output_dir, "handwriting_mask.jpg"); hok = save_gray(hw, hp)

    comb = cv2.bitwise_or(red if red is not None else np.zeros((1,1),np.uint8),
                           hw if hw is not None else np.zeros((1,1),np.uint8))
    cp = os.path.join(output_dir, "combined_mask.jpg"); save_gray(comb, cp)
    return {"red_mask_path":rp if rok else None, "hw_mask_path":hp if hok else None, "combined_mask_path":cp}

def generate_mask(inp, out):
    r = generate_masks(inp, os.path.dirname(out))
    return r.get("combined_mask_path") is not None

__all__ = ["generate_mask", "generate_masks"]
