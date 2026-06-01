"""Stage 3: Erasure using bgfill + inpaint."""
import cv2, numpy as np
from .utils import load_bgr, load_gray, save_bgr_jpeg

def _bg_fill(bgr, mask, r=20):
    mb = mask > 127
    if mb.sum() == 0: return bgr.copy()
    res = bgr.copy()
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (r, r))
    dil = cv2.dilate((mb.astype(np.uint8))*255, k)
    ring = (dil > 127) & (~mb)
    if ring.sum() == 0:
        return cv2.inpaint(bgr, (mb.astype(np.uint8))*255, 5, cv2.INPAINT_TELEA)
    for c in range(3):
        res[:,:,c][mb] = int(np.median(bgr[:,:,c][ring]))
    return res

def _apply_mask_array(bgr, mask, method="inpaint"):
    if mask.shape[:2] != bgr.shape[:2]:
        mask = cv2.resize(mask, (bgr.shape[1], bgr.shape[0]), interpolation=cv2.INTER_NEAREST)
    if mask.dtype != np.uint8: mask = mask.astype(np.uint8)
    if method == "white":
        res = bgr.copy(); res[mask > 127] = (255,255,255); return res
    if method == "bgfill": return _bg_fill(bgr, mask)
    return cv2.inpaint(bgr, ((mask > 127).astype(np.uint8))*255, 5, cv2.INPAINT_TELEA)

def apply_mask(inp, mp, outp, method="inpaint"):
    try:
        bgr = load_bgr(inp); m = load_gray(mp)
        if bgr is None or m is None: return False
        return save_bgr_jpeg(_apply_mask_array(bgr, m, method), outp)
    except: return False

def apply_masks_separately(preproc, redp, hwp, outp):
    try:
        bgr = load_bgr(preproc)
        if bgr is None: return False
        if redp is not None:
            rm = load_gray(redp)
            if rm is not None and rm.any(): bgr = _apply_mask_array(bgr, rm, "bgfill")
        if hwp is not None:
            hm = load_gray(hwp)
            if hm is not None and hm.any(): bgr = _apply_mask_array(bgr, hm, "inpaint")
        return save_bgr_jpeg(bgr, outp)
    except: return False

__all__ = ["apply_mask", "apply_masks_separately", "_apply_mask_array"]
