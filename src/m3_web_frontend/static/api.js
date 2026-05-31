/**
 * 试卷宝 — API wrapper (M3 Web Frontend → M4 FastAPI backend)
 *
 * Zero dependencies: uses native fetch + AbortController.
 *
 * All functions return Promises that:
 *   • resolve with the backend JSON body on 2xx responses
 *   • reject with an Error whose .message is a Chinese, user-friendly string
 *
 * Endpoint definitions: docs/INTERFACE-CONTRACT.md §4.3 / §4.4
 *
 * Loading hooks: setHooks(onStart, onEnd) lets pages drive global spinners.
 */
(function (global) {
  'use strict';

  // ---------- Config ----------
  const API_BASE = '/api';
  const DEFAULT_TIMEOUT_MS = 30_000;
  const UPLOAD_TIMEOUT_MS = 120_000;

  // ---------- Loading hooks (no-op by default) ----------
  let onRequestStart = () => {};
  let onRequestEnd = () => {};

  /**
   * Register loading hooks. Called once per page bootstrap.
   * @param {() => void} start
   * @param {() => void} end
   */
  function setHooks(start, end) {
    if (typeof start === 'function') onRequestStart = start;
    if (typeof end === 'function') onRequestEnd = end;
  }

  // ---------- HTTP status → friendly message ----------
  const STATUS_MESSAGES = {
    400: '请检查填写的内容是否正确',
    401: '请先登录',
    403: '没有权限执行此操作',
    404: '找不到这条记录,可能已经删除了',
    413: '图片太大了,请压缩后再上传',
    422: '提交的数据有问题',
    429: '操作太快啦,稍等一会儿再试',
    500: '服务器开小差了,请稍后再试',
    502: '服务器开小差了,请稍后再试',
    503: '服务器开小差了,请稍后再试',
    504: '请求超时,请检查网络或重试',
  };

  /**
   * Inspect a fetch Response and throw an Error with a friendly message.
   * Tries to read backend error body first, then falls back to status map.
   * @param {Response} res
   */
  async function throwFriendly(res) {
    let backendMsg = '';
    try {
      const data = await res.clone().json();
      backendMsg = data?.error || data?.detail || data?.message || '';
      if (typeof backendMsg !== 'string') backendMsg = JSON.stringify(backendMsg);
    } catch (_) {
      try { backendMsg = await res.text(); } catch (_) { /* ignore */ }
    }
    const fallback = STATUS_MESSAGES[res.status] || `请求失败 (${res.status})`;
    const err = new Error(backendMsg && res.status === 422 ? backendMsg : fallback);
    err.status = res.status;
    err.backendMessage = backendMsg;
    throw err;
  }

  /**
   * Core fetch wrapper. Adds timeout via AbortController, surfaces friendly
   * errors, and brackets every call with the loading hooks.
   *
   * @param {string} path - path under API_BASE (e.g. '/papers')
   * @param {RequestInit & {timeout?: number}} [options]
   * @returns {Promise<any>} parsed JSON body
   */
  async function request(path, options = {}) {
    const timeout = options.timeout || DEFAULT_TIMEOUT_MS;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);

    onRequestStart();
    try {
      const res = await fetch(API_BASE + path, {
        ...options,
        signal: controller.signal,
      });
      if (!res.ok) await throwFriendly(res);
      if (res.status === 204) return null;
      const text = await res.text();
      return text ? JSON.parse(text) : null;
    } catch (err) {
      if (err.name === 'AbortError') {
        const e = new Error('请求超时,请检查网络或重试');
        e.cause = err;
        throw e;
      }
      if (err instanceof TypeError) {
        // network failure, CORS, etc.
        const e = new Error('网络好像断了,检查一下网络连接');
        e.cause = err;
        throw e;
      }
      throw err;
    } finally {
      clearTimeout(timer);
      onRequestEnd();
    }
  }

  /** Build a querystring from a flat object (skips null/undefined/empty). */
  function qs(filters) {
    if (!filters) return '';
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === '') continue;
      params.append(k, String(v));
    }
    const s = params.toString();
    return s ? `?${s}` : '';
  }

  // =====================================================================
  // Papers
  // =====================================================================

  /**
   * Upload a paper image.
   * @param {File} file - the image file (jpg/png/heic, ≤20MB)
   * @param {('K1'|'K2')} childId
   * @param {string} subject - 数学|语文|英语|科学|其他
   * @param {string} [paperType='其他'] - 作业|单元卷|考试卷|练习册|其他
   * @param {string} [title=''] - optional paper title
   * @returns {Promise<{paper_id: number, status: string}>}
   */
  async function uploadPaper(file, childId, subject, paperType = '其他', title = '') {
    if (!file) throw new Error('请先选择要上传的图片');
    if (!childId) throw new Error('请选择孩子');
    if (!subject) throw new Error('请选择学科');

    const form = new FormData();
    form.append('file', file);
    form.append('child_id', childId);
    form.append('subject', subject);
    form.append('paper_type', paperType || '其他');
    if (title) form.append('title', title);

    return request('/papers/upload', {
      method: 'POST',
      body: form,
      timeout: UPLOAD_TIMEOUT_MS,
    });
  }

  /**
   * List papers with optional filters.
   * @param {Object} [filters]
   * @param {string} [filters.child_id]
   * @param {string} [filters.subject]
   * @param {string} [filters.status]
   * @param {number} [filters.limit=50]
   * @param {number} [filters.offset=0]
   * @returns {Promise<{papers: Array, total: number}>}
   */
  async function listPapers(filters = {}) {
    return request('/papers' + qs(filters));
  }

  /**
   * Get a single paper's details (includes image URLs).
   * @param {number|string} paperId
   * @returns {Promise<Object>}
   */
  async function getPaper(paperId) {
    if (paperId === undefined || paperId === null || paperId === '')
      throw new Error('缺少试卷 ID');
    return request(`/papers/${encodeURIComponent(paperId)}`);
  }

  /**
   * Trigger backend processing pipeline for a paper.
   * Backend may sleep / do heavy work; uses the upload-length timeout.
   * @param {number|string} paperId
   * @returns {Promise<{status: string, quality_score?: number, warnings?: Array}>}
   */
  async function processPaper(paperId) {
    if (paperId === undefined || paperId === null || paperId === '')
      throw new Error('缺少试卷 ID');
    return request(`/papers/${encodeURIComponent(paperId)}/process`, {
      method: 'POST',
      timeout: UPLOAD_TIMEOUT_MS,
    });
  }

  // =====================================================================
  // Mistakes
  // =====================================================================

  /**
   * Create a mistake (crop) on a paper.
   * @param {number|string} paperId
   * @param {{x:number, y:number, width:number, height:number}} cropData
   *        Original-image pixel coordinates.
   * @param {string} [note='']
   * @param {string} [errorType=''] - 粗心|概念不清|计算错误|不会做|其他
   * @returns {Promise<{mistake_id: number}>}
   */
  async function createMistake(paperId, cropData, note = '', errorType = '') {
    if (!cropData) throw new Error('缺少错题区域数据');
    const body = {
      paper_id: typeof paperId === 'string' ? Number(paperId) || paperId : paperId,
      crop_x: Math.round(cropData.x),
      crop_y: Math.round(cropData.y),
      crop_width: Math.round(cropData.width),
      crop_height: Math.round(cropData.height),
      note: note || null,
      error_type: errorType || null,
    };
    return request('/mistakes', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  /**
   * List mistakes with optional filters.
   * @param {Object} [filters] - {child_id, subject, status, paper_id, limit, offset}
   * @returns {Promise<{mistakes: Array, total: number}>}
   */
  async function listMistakes(filters = {}) {
    return request('/mistakes' + qs(filters));
  }

  /**
   * Delete a mistake by id.
   * @param {number|string} mistakeId
   * @returns {Promise<{success: boolean}>}
   */
  async function deleteMistake(mistakeId) {
    if (mistakeId === undefined || mistakeId === null || mistakeId === '')
      throw new Error('缺少错题 ID');
    return request(`/mistakes/${encodeURIComponent(mistakeId)}`, {
      method: 'DELETE',
    });
  }

  /**
   * Partial-update a mistake (status / note / error_type).
   * @param {number|string} mistakeId
   * @param {{status?:string, note?:string, error_type?:string}} data
   * @returns {Promise<{success: boolean}>}
   */
  async function updateMistake(mistakeId, data) {
    if (mistakeId === undefined || mistakeId === null || mistakeId === '')
      throw new Error('缺少错题 ID');
    if (!data || typeof data !== 'object') throw new Error('缺少更新内容');
    return request(`/mistakes/${encodeURIComponent(mistakeId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
  }

  // =====================================================================
  // Export
  // =====================================================================

  /**
   * Export selected mistakes to PDF.
   * @param {string} childId - 'K1' | 'K2'
   * @param {number[]} mistakeIds
   * @param {('one_per_page'|'two_per_page'|'compact')} [layout='one_per_page']
   * @param {string} [title='']
   * @returns {Promise<{pdf_url: string, export_id: number}>}
   */
  async function exportPdf(childId, mistakeIds, layout = 'one_per_page', title = '') {
    if (!childId) throw new Error('缺少孩子标识');
    if (!Array.isArray(mistakeIds) || mistakeIds.length === 0)
      throw new Error('请先选择要导出的错题');
    const body = {
      child_id: childId,
      mistake_ids: mistakeIds.map((id) => Number(id)).filter((n) => !Number.isNaN(n)),
      layout,
      title: title || null,
    };
    return request('/export/pdf', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      timeout: UPLOAD_TIMEOUT_MS,
    });
  }

  /**
   * Fetch export history.
   * @param {string} [childId]
   * @param {number} [limit=20]
   * @returns {Promise<{exports: Array}>}
   */
  async function getExportHistory(childId, limit = 20) {
    return request('/export/history' + qs({ child_id: childId, limit }));
  }

  // ---------- Public surface ----------
  const ExamApi = {
    API_BASE,
    setHooks,
    uploadPaper,
    listPapers,
    getPaper,
    processPaper,
    createMistake,
    listMistakes,
    deleteMistake,
    updateMistake,
    exportPdf,
    getExportHistory,
  };

  global.ExamApi = ExamApi;
  // Also expose individual functions for legacy / sugar usage.
  Object.assign(global, {
    uploadPaper, listPapers, getPaper, processPaper,
    createMistake, listMistakes, deleteMistake, updateMistake,
    exportPdf, getExportHistory,
  });
})(typeof window !== 'undefined' ? window : globalThis);
