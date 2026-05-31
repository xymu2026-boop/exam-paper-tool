/**
 * 试卷宝 — Shared page helpers (M3 Web Frontend)
 *
 * Small, dependency-free utilities used by every Alpine page:
 *   - global toast stack (success / error / info)
 *   - global loading hook installation for ExamApi
 *   - small URL / format helpers
 *   - static-file URL resolver (paper image paths → /static/data/...)
 */
(function (global) {
  'use strict';

  // ---------- Toast ----------
  const TOAST_TTL = 3200;
  let toastStack = null;

  function ensureToastStack() {
    if (toastStack && document.body.contains(toastStack)) return toastStack;
    toastStack = document.createElement('div');
    toastStack.className = 'toast-stack';
    toastStack.setAttribute('aria-live', 'polite');
    toastStack.setAttribute('aria-atomic', 'true');
    document.body.appendChild(toastStack);
    return toastStack;
  }

  /**
   * Push a toast notification.
   * @param {string} message
   * @param {('info'|'success'|'error')} [type='info']
   * @param {number} [ttl=3200]
   */
  function toast(message, type = 'info', ttl = TOAST_TTL) {
    if (!message) return;
    const root = ensureToastStack();
    const node = document.createElement('div');
    node.className = `toast toast--${type}`;
    node.textContent = message;
    root.appendChild(node);
    setTimeout(() => {
      node.style.transition = 'opacity 200ms ease, transform 200ms ease';
      node.style.opacity = '0';
      node.style.transform = 'translateY(-6px)';
      setTimeout(() => node.remove(), 220);
    }, ttl);
  }

  // ---------- Global loading indicator (simple counter) ----------
  let pending = 0;
  let loadingBar = null;
  function ensureLoadingBar() {
    if (loadingBar && document.body.contains(loadingBar)) return loadingBar;
    loadingBar = document.createElement('div');
    loadingBar.style.cssText = [
      'position:fixed', 'top:0', 'left:0', 'height:3px', 'width:0%',
      'background:linear-gradient(90deg,#3B82F6,#60A5FA)',
      'transition:width 200ms ease,opacity 200ms ease',
      'z-index:9999', 'pointer-events:none', 'opacity:0',
    ].join(';');
    document.body.appendChild(loadingBar);
    return loadingBar;
  }
  function startReq() {
    pending++;
    const bar = ensureLoadingBar();
    bar.style.opacity = '1';
    bar.style.width = Math.min(85, 30 + pending * 12) + '%';
  }
  function endReq() {
    pending = Math.max(0, pending - 1);
    const bar = ensureLoadingBar();
    if (pending === 0) {
      bar.style.width = '100%';
      setTimeout(() => {
        bar.style.opacity = '0';
        setTimeout(() => { bar.style.width = '0%'; }, 220);
      }, 150);
    }
  }

  // ---------- URL / formatting helpers ----------

  /** Parse `?a=1&b=2,3` into an object; values stay as strings. */
  function parseQuery(search = location.search) {
    const out = {};
    const sp = new URLSearchParams(search);
    sp.forEach((v, k) => { out[k] = v; });
    return out;
  }

  /**
   * Resolve a backend image path (e.g. "processed/1/cleaned.jpg" or an
   * already-absolute URL) to a URL the browser can fetch.
   * Backend convention: GET /static/data/{path}
   */
  function staticUrl(path) {
    if (!path) return '';
    if (/^https?:\/\//i.test(path)) return path;
    if (path.startsWith('/')) return path;
    return '/static/data/' + path.replace(/^\/+/, '');
  }

  /** Friendly date formatter for "2026-05-31 15:30:22" or ISO strings. */
  function formatDate(s) {
    if (!s) return '';
    // Already in "YYYY-MM-DD HH:mm:ss" form — slice
    const m = String(s).match(/(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2})/);
    if (m) return `${m[1]}-${m[2]}-${m[3]} ${m[4]}:${m[5]}`;
    return String(s);
  }

  /** "5 分钟前" style relative time (best-effort, fallback to formatDate). */
  function timeAgo(s) {
    if (!s) return '';
    const t = Date.parse(String(s).replace(' ', 'T'));
    if (Number.isNaN(t)) return formatDate(s);
    const diff = Date.now() - t;
    const min = 60_000, hr = 3_600_000, day = 86_400_000;
    if (diff < min) return '刚刚';
    if (diff < hr)  return Math.floor(diff / min) + ' 分钟前';
    if (diff < day) return Math.floor(diff / hr) + ' 小时前';
    if (diff < 7 * day) return Math.floor(diff / day) + ' 天前';
    return formatDate(s);
  }

  /** Status → CSS modifier */
  function statusBadgeClass(status) {
    switch (status) {
      case 'pending':    return 'badge badge--pending';
      case 'processing': return 'badge badge--processing';
      case 'processed':  return 'badge badge--processed';
      case 'failed':     return 'badge badge--failed';
      default:           return 'badge';
    }
  }

  function statusLabel(status) {
    return ({
      pending: '待处理',
      processing: '处理中',
      processed: '已处理',
      failed: '失败',
      new: '未掌握',
      printed: '已打印',
      practiced: '已练习',
      passed: '已掌握',
      retry: '待复习',
    })[status] || status || '';
  }

  function errorTypeTagClass(t) {
    return ({
      '粗心':       'tag tag--careless',
      '概念不清':   'tag tag--concept',
      '计算错误':   'tag tag--calculation',
      '不会做':     'tag tag--unknown',
      '其他':       'tag tag--other',
    })[t] || 'tag';
  }

  function subjectIcon(subject) {
    return ({
      '数学': '∑',
      '语文': '文',
      '英语': 'A',
      '科学': '⚗',
      '其他': '·',
    })[subject] || '·';
  }

  // ---------- Bootstrap ----------
  function bootstrap() {
    if (global.ExamApi && typeof global.ExamApi.setHooks === 'function') {
      global.ExamApi.setHooks(startReq, endReq);
    }
  }

  // Auto-bootstrap on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bootstrap, { once: true });
  } else {
    bootstrap();
  }

  // Public surface
  global.App = {
    toast,
    parseQuery,
    staticUrl,
    formatDate,
    timeAgo,
    statusBadgeClass,
    statusLabel,
    errorTypeTagClass,
    subjectIcon,
  };
})(typeof window !== 'undefined' ? window : globalThis);
