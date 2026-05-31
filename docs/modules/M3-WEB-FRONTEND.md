# M3: Web 前端 — 开发任务卡

| 模块编号 | 状态 | 可并行 | 依赖 |
|----------|------|--------|------|
| M3 | 待开发 | ✅（用 mock API） | M4 的 API 定义 |

---

## 模块定位

纯静态前端，HTML + Alpine.js (CDN) + Canvas API。

- **零构建**：不依赖 npm / node / webpack / vite
- **零打包**：所有依赖通过 CDN 引入
- 由 M4 的 FastAPI 提供静态文件服务（生产环境）
- 开发时可用任何静态服务器或直接双击 HTML 打开
- 通过 mock 服务器即可独立开发、独立调试，不必等待 M4 完成

通过 `fetch` 调用 M4 的 REST API（端点定义见 `INTERFACE-CONTRACT.md`）。

---

## 前置阅读

开发前必须先阅读以下文档：

- `docs/INTERFACE-CONTRACT.md` 第四节 4.3 和 4.4（API 端点列表，权威接口契约）
- `家庭版试卷宝需求总文档_v1.0.md` 主线1（试卷上传与管理）和主线4（错题导出）

---

## 目录结构

```
src/m3_web_frontend/
├── index.html          # 主页（上传 + 试卷列表）
├── paper.html          # 试卷详情页（预览 + 框选错题）
├── mistakes.html       # 错题库列表页
├── export.html         # 导出页
├── static/
│   ├── app.js          # Alpine.js 主逻辑
│   ├── crop.js         # Canvas 框选逻辑（核心交互）
│   ├── api.js          # API 调用封装
│   └── style.css       # 样式
└── mock/
    └── mock-server.py  # 开发用 mock API 服务器
```

---

## 页面设计

### index.html — 主页

**功能**：

- 上传图片（支持拖拽 + 点击选择，支持 JPG/PNG/HEIC）
- 选择孩子（K1 / K2 下拉框）
- 选择学科（数学 / 语文 / 英语 / 科学 / 其他）
- 可选备注（试卷标题、来源等）
- 上传后显示待处理列表
- 点击「处理」按钮触发后端处理流程
- 显示处理状态徽章：`pending` / `processing` / `processed` / `failed`
- 点击试卷卡片进入详情页

**布局要点**：

- 顶部：上传区（大块拖拽区，移动端友好）
- 中部：表单（孩子 / 学科 / 备注）
- 底部：试卷列表（按上传时间倒序，卡片视图）

---

### paper.html — 试卷详情页

**功能**：

- 左右对比显示：原图 | 擦除图（移动端可切换为上下排列或 Tab 切换）
- 在擦除图上用 Canvas 框选错题区域
- 支持多个框选框（不同颜色区分）
- 支持删除 / 调整框选大小
- 每个框选可添加备注和错因类型（粗心 / 不会 / 概念错 / 其他）
- 「保存」按钮一次性提交所有框选

**URL 参数**：`paper.html?id=<paper_id>`

---

### mistakes.html — 错题库列表页

**功能**：

- 筛选条件：孩子 + 学科 + 状态（未掌握 / 已掌握 / 待复习）
- 错题卡片列表（显示缩略图 + 备注 + 状态 + 错因类型）
- 可勾选多个错题（checkbox）
- 批量操作：导出 PDF / 更新状态 / 删除

**布局要点**：

- 顶部：筛选栏（粘性定位）
- 中部：卡片网格（移动端单列，桌面端 2-3 列）
- 底部：批量操作栏（选中后浮现）

---

### export.html — 导出页

**功能**：

- 显示已勾选的错题预览（可在 mistakes 页选中后跳转过来）
- 选择布局模式（一题一页 / 紧凑布局 / 自定义题数）
- 点击「导出」按钮
- 后端生成 PDF 后触发下载

**URL 参数**：`export.html?ids=<id1>,<id2>,...&child_id=<child_id>`

---

## 核心交互：Canvas 框选 (crop.js)

这是前端最复杂的部分。要求：

- 在 Canvas 上显示擦除后的试卷图片
- 用户可以拖拽画矩形框
- 支持多个框（不同颜色区分，例如循环使用 6 种预设色）
- 点击已有框可以选中 / 删除 / 调整大小（八向手柄）
- 输出每个框的坐标：`{x, y, width, height}`（**相对于原图像素，不是 Canvas 像素**）
- 注意：Canvas 显示尺寸和图片实际尺寸可能不同，坐标要按比例转换

**关键状态**：

```javascript
const state = {
  imageNaturalWidth: 0,    // 原图像素宽
  imageNaturalHeight: 0,   // 原图像素高
  canvasWidth: 0,          // Canvas 显示宽（可能被 CSS 缩放）
  canvasHeight: 0,         // Canvas 显示高
  boxes: [],               // [{id, x, y, w, h, color, note, errorType}]，坐标是原图像素
  selectedBoxId: null,
  mode: 'idle',            // 'idle' | 'drawing' | 'moving' | 'resizing'
  dragStart: null,
};
```

**坐标转换**：所有鼠标 / 触屏事件得到的坐标先用 `getBoundingClientRect()` 转成 Canvas 坐标，再乘以 `(naturalWidth / canvasWidth)` 转成原图坐标存入 `state.boxes`。绘制时反向转换。

**事件处理**：mouse 和 touch 事件并行注册，统一抽象为 `pointerdown / pointermove / pointerup`（也可直接用 Pointer Events API，注意 Safari 兼容性）。

---

## API 调用封装 (api.js)

统一封装所有 API 调用，方便切换 mock 和真实后端。所有函数返回 Promise，错误统一抛出。

```javascript
const API_BASE = '/api';

async function uploadPaper(file, childId, subject, title = '') { ... }
async function listPapers(filters = {}) { ... }
async function getPaper(paperId) { ... }
async function processPaper(paperId) { ... }
async function createMistake(paperId, cropData, note, errorType) { ... }
async function listMistakes(filters = {}) { ... }
async function deleteMistake(mistakeId) { ... }
async function updateMistake(mistakeId, data) { ... }
async function exportPdf(childId, mistakeIds, layout) { ... }
```

**实现要点**：

- 上传用 `FormData`，其他用 `application/json`
- 统一的错误处理：HTTP 4xx/5xx 抛出包含 message 的 Error
- 超时控制（默认 30s，上传放宽到 120s）
- 调用前后可加 loading 状态钩子（暴露 `onRequestStart` / `onRequestEnd`）

具体参数和返回值以 `INTERFACE-CONTRACT.md` 第 4.3、4.4 节为准。

---

## Mock 服务器 (mock/mock-server.py)

用 Python `http.server` 或简单 Flask 实现，返回固定 JSON 数据，便于前端独立开发。

**要求**：

- 启动方式：`python mock/mock-server.py`，监听 `http://localhost:8000`
- 同时托管静态文件（HTML/JS/CSS）和 mock API
- 覆盖所有 `api.js` 中调用的端点
- 可以返回示例图片（放在 `mock/fixtures/` 目录）
- 模拟处理延迟（`processPaper` 可以 sleep 2 秒后返回 `processed`）

**示例端点**：

```python
GET  /api/papers              -> 返回 3-5 条假数据
POST /api/papers              -> 接收 multipart，返回 {paper_id: "mock-001"}
GET  /api/papers/{id}         -> 返回详情，含原图和擦除图 URL
POST /api/papers/{id}/process -> sleep 后返回 status=processed
GET  /api/mistakes            -> 返回假数据列表
POST /api/mistakes            -> 返回 {mistake_id: "mock-mst-001"}
POST /api/export/pdf          -> 返回一个真实的小 PDF 文件流
```

---

## 设计规范

- **移动端优先**：手机上传是高频场景，所有页面先在 375×667 视口下设计
- **简洁实用**：不追求花哨动效，功能优先
- **大按钮**：触屏友好，主操作按钮 ≥ 44px 高
- **加载状态明确**：spinner、骨架屏或进度条，避免用户疑惑
- **错误提示友好**：toast 或顶部条幅，文案口语化（避免 "Error 500" 之类）
- **配色**：建议浅色 + 一种主色调（如蓝或绿），不超过 3 种主要颜色
- **字体**：系统默认字体栈，确保中英文都好看

---

## 测试要求

- 可以用 `mock-server.py` 独立运行所有页面（不依赖 M4）
- 手机浏览器访问正常（Safari iOS / Chrome Android）
- Canvas 框选在触屏和鼠标下都能工作
- 网络异常时有友好提示（断网、超时、4xx/5xx）
- HEIC 文件上传不报错（前端不转换，直接传给后端）

---

## 验收标准

- [ ] 四个页面都能正常打开（index / paper / mistakes / export）
- [ ] 上传流程走通（用 mock）：选文件 → 填表单 → 上传 → 列表出现
- [ ] 试卷详情页能加载原图和擦除图
- [ ] Canvas 框选能画框、删框、调整大小、输出原图坐标
- [ ] 多个框选保存一次性提交
- [ ] 错题库列表能筛选、勾选、批量导出
- [ ] 导出页能触发 PDF 下载
- [ ] 手机端布局正常（无横向滚动条，按钮可点）
- [ ] 不依赖 npm / node / 任何构建工具

---

## 技术要点

**Alpine.js CDN 引入**：

```html
<script src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js" defer></script>
```

**Canvas 坐标转换**：

```javascript
// 鼠标坐标 → Canvas 内部坐标
const rect = canvas.getBoundingClientRect();
const canvasX = (event.clientX - rect.left) * (canvas.width / rect.width);
const canvasY = (event.clientY - rect.top) * (canvas.height / rect.height);

// Canvas 内部坐标 → 原图像素坐标
const imgX = canvasX * (imageNaturalWidth / canvas.width);
const imgY = canvasY * (imageNaturalHeight / canvas.height);
```

**触屏事件**：`touchstart` / `touchmove` / `touchend` 和 `mouse` 事件并行处理；移动端注意 `event.preventDefault()` 避免页面滚动；使用 `event.touches[0]` 取第一个触点。

**HEIC 上传**：前端不做转换（浏览器对 HEIC 支持差），直接当成普通文件上传，由后端处理。

**避免坑点**：

- iOS Safari 对 `<input type="file">` 拍照支持的 `capture` 属性，建议加 `accept="image/*"`
- Canvas 在 retina 屏要处理 `devicePixelRatio` 防止模糊
- `fetch` 上传大文件时不要预读到内存，用 `FormData` 直接传 `File` 对象

---

## 协作约定

- 与 M4 通过 `INTERFACE-CONTRACT.md` 4.3 / 4.4 节定义的 REST API 通信
- 联调前用 mock-server 完成所有页面功能
- 联调时将 `api.js` 的 `API_BASE` 切换到 M4 真实地址
- 发现 API 契约不清晰时，**改文档而不是改代码**，先和 M4 对齐
