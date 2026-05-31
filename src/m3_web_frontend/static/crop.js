/**
 * 试卷宝 — Canvas 框选 (M3 Web Frontend)
 *
 * Pure-JS, zero deps. Drives a <canvas> overlay on top of an <img>
 * (the cleaned/processed paper) and lets the user draw, select, move,
 * resize, and delete rectangles. All box coordinates are stored in
 * ORIGINAL image pixel space, so the upstream POST /api/mistakes call
 * needs no further conversion.
 *
 * Public API:
 *   const cropper = createCropper({ canvas, image, onChange });
 *   cropper.setBoxes([...]);            // hydrate from server
 *   cropper.getBoxes();                 // -> array of {x,y,width,height,note,errorType,id,color}
 *   cropper.deleteSelected();
 *   cropper.selectBox(id);
 *   cropper.updateBox(id, partial);
 *   cropper.destroy();
 *
 * State machine:
 *   idle ─(down on empty)→ drawing ─(up)→ idle
 *   idle ─(down on body)─→ moving  ─(up)→ idle
 *   idle ─(down on handle)→ resizing ─(up)→ idle
 *
 * Coordinate conversion (event → image pixels):
 *   rect = canvas.getBoundingClientRect()
 *   canvasX = (clientX - rect.left) * (canvas.width / rect.width)
 *   imgX    = canvasX * (imageNaturalWidth / canvas.width)
 *   The factor (canvas.width / rect.width) folds in devicePixelRatio
 *   automatically because we also scale the backing buffer by DPR.
 */
(function (global) {
  'use strict';

  // 6-color rotation for new boxes.
  const CROP_COLORS = ['#FF6B6B', '#4ECDC4', '#FFD93D', '#6BCB77', '#4D96FF', '#C780FA'];

  const HANDLE_HIT_RADIUS = 14;        // px, in canvas-internal space
  const HANDLE_VISUAL_SIZE = 10;       // px, drawn handle square edge
  const MIN_BOX_SIZE = 10;             // image-pixel minimum side length
  const ERROR_TYPES = ['粗心', '概念不清', '计算错误', '不会做', '其他'];

  // 8 resize handles: corners + edge midpoints
  const HANDLES = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];

  /** Generate a short local UUID for client-side box identity. */
  function localId() {
    return 'tmp-' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36).slice(-4);
  }

  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  /**
   * Create a cropper instance bound to a canvas + image pair.
   *
   * @param {Object} opts
   * @param {HTMLCanvasElement} opts.canvas
   * @param {HTMLImageElement} opts.image - already-loaded image element
   * @param {(boxes: Array) => void} [opts.onChange] - fires after any mutation
   * @param {(id: string|number|null) => void} [opts.onSelect]
   * @returns {Object} cropper API
   */
  function createCropper(opts) {
    const { canvas, image } = opts;
    const onChange = typeof opts.onChange === 'function' ? opts.onChange : () => {};
    const onSelect = typeof opts.onSelect === 'function' ? opts.onSelect : () => {};
    const ctx = canvas.getContext('2d');

    const state = {
      // image natural dims
      imageNaturalWidth: image.naturalWidth || image.width,
      imageNaturalHeight: image.naturalHeight || image.height,

      // canvas backing pixel size (set on resize)
      canvasPixelWidth: 0,
      canvasPixelHeight: 0,

      // canvas display (CSS) size
      displayWidth: 0,
      displayHeight: 0,

      // boxes list — coords are ORIGINAL IMAGE PIXELS
      boxes: [],

      selectedBoxId: null,
      mode: 'idle',                  // 'idle' | 'drawing' | 'moving' | 'resizing'

      // drag bookkeeping (image-pixel coordinates)
      dragStart: null,               // {x, y}
      origBox: null,                 // snapshot of box at drag start
      activeHandle: null,            // 'nw' | 'n' | ... when resizing
      colorIndex: 0,
    };

    // ----- coordinate conversion -----

    /** Get pointer position in CANVAS-INTERNAL coordinates (already DPR-scaled). */
    function pointerToCanvas(ev) {
      const rect = canvas.getBoundingClientRect();
      let cx, cy;
      if (ev.touches && ev.touches.length) {
        cx = ev.touches[0].clientX;
        cy = ev.touches[0].clientY;
      } else if (ev.changedTouches && ev.changedTouches.length) {
        cx = ev.changedTouches[0].clientX;
        cy = ev.changedTouches[0].clientY;
      } else {
        cx = ev.clientX;
        cy = ev.clientY;
      }
      const w = rect.width || 1;
      const h = rect.height || 1;
      return {
        x: (cx - rect.left) * (canvas.width / w),
        y: (cy - rect.top) * (canvas.height / h),
      };
    }

    /** Canvas-internal → original image pixels. */
    function canvasToImage(p) {
      return {
        x: p.x * (state.imageNaturalWidth / canvas.width),
        y: p.y * (state.imageNaturalHeight / canvas.height),
      };
    }

    /** Pointer event → image pixel coordinates. */
    function pointerToImage(ev) {
      return canvasToImage(pointerToCanvas(ev));
    }

    /** Image pixel rect → canvas-internal rect (for drawing/hit-testing). */
    function imageRectToCanvas(box) {
      const sx = canvas.width / state.imageNaturalWidth;
      const sy = canvas.height / state.imageNaturalHeight;
      return {
        x: box.x * sx,
        y: box.y * sy,
        w: box.w * sx,
        h: box.h * sy,
      };
    }

    // ----- canvas sizing (DPR-aware) -----

    function resize() {
      const rect = canvas.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      state.displayWidth = rect.width;
      state.displayHeight = rect.height;
      state.canvasPixelWidth = Math.round(rect.width * dpr);
      state.canvasPixelHeight = Math.round(rect.height * dpr);
      // Only resize backing buffer if changed (avoids losing context state).
      if (canvas.width !== state.canvasPixelWidth || canvas.height !== state.canvasPixelHeight) {
        canvas.width = state.canvasPixelWidth;
        canvas.height = state.canvasPixelHeight;
      }
      draw();
    }

    // ----- hit testing -----

    function findHandle(box, p) {
      const r = imageRectToCanvas(box);
      const handles = handlePositions(r);
      for (const h of HANDLES) {
        const hp = handles[h];
        if (Math.abs(p.x - hp.x) <= HANDLE_HIT_RADIUS &&
            Math.abs(p.y - hp.y) <= HANDLE_HIT_RADIUS) {
          return h;
        }
      }
      return null;
    }

    function handlePositions(r) {
      return {
        nw: { x: r.x,           y: r.y },
        n:  { x: r.x + r.w / 2, y: r.y },
        ne: { x: r.x + r.w,     y: r.y },
        e:  { x: r.x + r.w,     y: r.y + r.h / 2 },
        se: { x: r.x + r.w,     y: r.y + r.h },
        s:  { x: r.x + r.w / 2, y: r.y + r.h },
        sw: { x: r.x,           y: r.y + r.h },
        w:  { x: r.x,           y: r.y + r.h / 2 },
      };
    }

    function pointInBox(box, p) {
      const r = imageRectToCanvas(box);
      return p.x >= r.x && p.x <= r.x + r.w &&
             p.y >= r.y && p.y <= r.y + r.h;
    }

    /**
     * Find a box under the pointer. Selected box is checked first so
     * its handles win over other boxes' bodies.
     * @returns {{box, handle}|null}
     */
    function hitTest(p) {
      // Selected box: handles take priority
      if (state.selectedBoxId !== null) {
        const sel = state.boxes.find((b) => b.id === state.selectedBoxId);
        if (sel) {
          const h = findHandle(sel, p);
          if (h) return { box: sel, handle: h };
          if (pointInBox(sel, p)) return { box: sel, handle: null };
        }
      }
      // Other boxes (top of stack first)
      for (let i = state.boxes.length - 1; i >= 0; i--) {
        const b = state.boxes[i];
        if (b.id === state.selectedBoxId) continue;
        if (pointInBox(b, p)) return { box: b, handle: null };
      }
      return null;
    }

    // ----- drawing -----

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (const box of state.boxes) {
        const r = imageRectToCanvas(box);
        const isSelected = box.id === state.selectedBoxId;

        // Fill
        ctx.fillStyle = hexToRgba(box.color, isSelected ? 0.18 : 0.10);
        ctx.fillRect(r.x, r.y, r.w, r.h);

        // Stroke
        ctx.lineWidth = isSelected ? 3 : 2;
        ctx.strokeStyle = box.color;
        ctx.strokeRect(r.x, r.y, r.w, r.h);

        // Index label
        const idx = state.boxes.indexOf(box) + 1;
        ctx.font = '600 14px -apple-system, BlinkMacSystemFont, "PingFang SC", sans-serif';
        const label = '#' + idx;
        const padX = 6, padY = 4;
        const m = ctx.measureText(label);
        const tagW = m.width + padX * 2;
        const tagH = 20;
        ctx.fillStyle = box.color;
        ctx.fillRect(r.x, r.y - tagH, tagW, tagH);
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText(label, r.x + padX, r.y - padY - 2);

        // Handles when selected
        if (isSelected) {
          const handles = handlePositions(r);
          ctx.fillStyle = '#FFFFFF';
          ctx.strokeStyle = box.color;
          ctx.lineWidth = 2;
          for (const h of HANDLES) {
            const hp = handles[h];
            const s = HANDLE_VISUAL_SIZE;
            ctx.fillRect(hp.x - s / 2, hp.y - s / 2, s, s);
            ctx.strokeRect(hp.x - s / 2, hp.y - s / 2, s, s);
          }
        }
      }
    }

    function hexToRgba(hex, alpha) {
      const h = hex.replace('#', '');
      const n = parseInt(h, 16);
      const r = (n >> 16) & 255;
      const g = (n >> 8) & 255;
      const b = n & 255;
      return `rgba(${r},${g},${b},${alpha})`;
    }

    // ----- pointer handlers (mouse + touch unified) -----

    function onDown(ev) {
      // Touch: single-finger only; ignore multi-touch & prevent scroll
      if (ev.touches) {
        if (ev.touches.length !== 1) return;
        ev.preventDefault();
      }
      const p = pointerToCanvas(ev);
      const imgPt = canvasToImage(p);
      const hit = hitTest(p);

      if (hit) {
        state.selectedBoxId = hit.box.id;
        onSelect(hit.box.id);
        if (hit.handle) {
          state.mode = 'resizing';
          state.activeHandle = hit.handle;
          state.origBox = clone(hit.box);
          state.dragStart = imgPt;
        } else {
          state.mode = 'moving';
          state.origBox = clone(hit.box);
          state.dragStart = imgPt;
        }
        canvas.dataset.state = state.mode;
        draw();
        return;
      }

      // Empty area → start drawing a new box
      state.mode = 'drawing';
      const color = CROP_COLORS[state.colorIndex % CROP_COLORS.length];
      const newBox = {
        id: localId(),
        x: imgPt.x,
        y: imgPt.y,
        w: 0,
        h: 0,
        color,
        note: '',
        errorType: '',
        dirty: true,
      };
      state.boxes.push(newBox);
      state.selectedBoxId = newBox.id;
      state.origBox = clone(newBox);
      state.dragStart = imgPt;
      state.colorIndex++;
      canvas.dataset.state = state.mode;
      onSelect(newBox.id);
      draw();
    }

    function onMove(ev) {
      if (state.mode === 'idle') return;
      if (ev.touches) {
        if (ev.touches.length !== 1) return;
        ev.preventDefault();
      }
      const imgPt = pointerToImage(ev);
      const box = state.boxes.find((b) => b.id === state.selectedBoxId);
      if (!box) return;

      const dx = imgPt.x - state.dragStart.x;
      const dy = imgPt.y - state.dragStart.y;

      if (state.mode === 'drawing') {
        const startX = state.dragStart.x;
        const startY = state.dragStart.y;
        box.x = Math.min(startX, imgPt.x);
        box.y = Math.min(startY, imgPt.y);
        box.w = Math.abs(imgPt.x - startX);
        box.h = Math.abs(imgPt.y - startY);
        box.dirty = true;
      } else if (state.mode === 'moving') {
        box.x = state.origBox.x + dx;
        box.y = state.origBox.y + dy;
        // clamp to image bounds
        box.x = Math.max(0, Math.min(state.imageNaturalWidth - box.w, box.x));
        box.y = Math.max(0, Math.min(state.imageNaturalHeight - box.h, box.y));
        box.dirty = true;
      } else if (state.mode === 'resizing') {
        applyResize(box, state.origBox, state.activeHandle, dx, dy);
        box.dirty = true;
      }
      draw();
    }

    function applyResize(box, orig, handle, dx, dy) {
      let nx = orig.x, ny = orig.y, nw = orig.w, nh = orig.h;
      if (handle.includes('w')) { nx = orig.x + dx; nw = orig.w - dx; }
      if (handle.includes('e')) { nw = orig.w + dx; }
      if (handle.includes('n')) { ny = orig.y + dy; nh = orig.h - dy; }
      if (handle.includes('s')) { nh = orig.h + dy; }
      // Flip-safe: keep positive width/height
      if (nw < 0) { nx += nw; nw = -nw; }
      if (nh < 0) { ny += nh; nh = -nh; }
      // Clamp inside image
      nx = Math.max(0, nx);
      ny = Math.max(0, ny);
      nw = Math.min(state.imageNaturalWidth - nx, nw);
      nh = Math.min(state.imageNaturalHeight - ny, nh);
      box.x = nx; box.y = ny; box.w = nw; box.h = nh;
    }

    function onUp(ev) {
      if (state.mode === 'idle') return;
      if (ev && ev.changedTouches) ev.preventDefault();

      const box = state.boxes.find((b) => b.id === state.selectedBoxId);

      if (state.mode === 'drawing' && box) {
        // discard zero-sized / sub-threshold boxes
        if (box.w < MIN_BOX_SIZE || box.h < MIN_BOX_SIZE) {
          state.boxes = state.boxes.filter((b) => b.id !== box.id);
          state.selectedBoxId = null;
          onSelect(null);
        } else {
          // round to integer pixels (per tech plan §4.3)
          box.x = Math.round(box.x);
          box.y = Math.round(box.y);
          box.w = Math.round(box.w);
          box.h = Math.round(box.h);
        }
      } else if (box) {
        box.x = Math.round(box.x);
        box.y = Math.round(box.y);
        box.w = Math.round(box.w);
        box.h = Math.round(box.h);
      }

      state.mode = 'idle';
      state.dragStart = null;
      state.origBox = null;
      state.activeHandle = null;
      canvas.dataset.state = state.mode;
      draw();
      onChange(getBoxesPublic());
    }

    function onKeyDown(ev) {
      if ((ev.key === 'Delete' || ev.key === 'Backspace') && state.selectedBoxId !== null) {
        // Avoid hijacking input fields
        const t = ev.target;
        if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
        deleteSelected();
        ev.preventDefault();
      } else if (ev.key === 'Escape') {
        state.selectedBoxId = null;
        onSelect(null);
        draw();
      }
    }

    // ----- public mutators -----

    function setBoxes(arr) {
      state.boxes = (arr || []).map((b, i) => ({
        id: b.id !== undefined ? b.id : localId(),
        x: Number(b.x) || 0,
        y: Number(b.y) || 0,
        w: Number(b.w !== undefined ? b.w : b.width) || 0,
        h: Number(b.h !== undefined ? b.h : b.height) || 0,
        color: b.color || CROP_COLORS[i % CROP_COLORS.length],
        note: b.note || '',
        errorType: b.errorType || b.error_type || '',
        dirty: false,
      }));
      state.colorIndex = state.boxes.length;
      draw();
      onChange(getBoxesPublic());
    }

    function getBoxesPublic() {
      return state.boxes.map((b, i) => ({
        id: b.id,
        index: i + 1,
        x: Math.round(b.x),
        y: Math.round(b.y),
        width: Math.round(b.w),
        height: Math.round(b.h),
        color: b.color,
        note: b.note,
        errorType: b.errorType,
        dirty: !!b.dirty,
      }));
    }

    function deleteSelected() {
      if (state.selectedBoxId === null) return null;
      const removed = state.boxes.find((b) => b.id === state.selectedBoxId);
      state.boxes = state.boxes.filter((b) => b.id !== state.selectedBoxId);
      state.selectedBoxId = null;
      draw();
      onSelect(null);
      onChange(getBoxesPublic());
      return removed || null;
    }

    function deleteBox(id) {
      const removed = state.boxes.find((b) => b.id === id);
      state.boxes = state.boxes.filter((b) => b.id !== id);
      if (state.selectedBoxId === id) {
        state.selectedBoxId = null;
        onSelect(null);
      }
      draw();
      onChange(getBoxesPublic());
      return removed || null;
    }

    function selectBox(id) {
      state.selectedBoxId = id;
      onSelect(id);
      draw();
    }

    function updateBox(id, partial) {
      const b = state.boxes.find((x) => x.id === id);
      if (!b) return;
      if (partial.note !== undefined) b.note = partial.note;
      if (partial.errorType !== undefined) b.errorType = partial.errorType;
      if (partial.error_type !== undefined) b.errorType = partial.error_type;
      if (partial.id !== undefined) b.id = partial.id;
      b.dirty = true;
      onChange(getBoxesPublic());
    }

    function clearAll() {
      state.boxes = [];
      state.selectedBoxId = null;
      state.colorIndex = 0;
      draw();
      onSelect(null);
      onChange(getBoxesPublic());
    }

    // ----- wire events -----

    // mouse
    canvas.addEventListener('mousedown', onDown);
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    // touch
    canvas.addEventListener('touchstart', onDown, { passive: false });
    canvas.addEventListener('touchmove', onMove, { passive: false });
    canvas.addEventListener('touchend', onUp, { passive: false });
    canvas.addEventListener('touchcancel', onUp, { passive: false });
    // keyboard
    window.addEventListener('keydown', onKeyDown);
    // resize
    window.addEventListener('resize', resize);

    // initial layout
    canvas.dataset.state = 'idle';
    resize();

    function destroy() {
      canvas.removeEventListener('mousedown', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
      canvas.removeEventListener('touchstart', onDown);
      canvas.removeEventListener('touchmove', onMove);
      canvas.removeEventListener('touchend', onUp);
      canvas.removeEventListener('touchcancel', onUp);
      window.removeEventListener('keydown', onKeyDown);
      window.removeEventListener('resize', resize);
    }

    return {
      // queries
      getBoxes: getBoxesPublic,
      getSelectedId: () => state.selectedBoxId,
      // mutations
      setBoxes,
      deleteSelected,
      deleteBox,
      selectBox,
      updateBox,
      clearAll,
      resize,
      // teardown
      destroy,
      // constants
      ERROR_TYPES,
      CROP_COLORS,
    };
  }

  global.createCropper = createCropper;
  global.CROP_COLORS = CROP_COLORS;
  global.CROP_ERROR_TYPES = ERROR_TYPES;
})(typeof window !== 'undefined' ? window : globalThis);
