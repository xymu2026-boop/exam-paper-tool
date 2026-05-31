# M3 Web Frontend — 技术实现计划

> **模块**: M3 (Web Frontend)
> **技术栈**: HTML + Alpine.js (CDN) + Canvas API + 原生 CSS
> **约束**: 零构建工具，零打包，纯静态文件
> **版本**: v1.0
> **日期**: 2026-05-31

---

## 1. 模块职责

M3 是一个纯静态 HTML + JavaScript 前端，不引入任何构建工具或打包流程。所有页面由 M4 的 FastAPI 静态文件服务托管，开发阶段可通过 Python mock 服务器独立运行。前端与 M4 之间的全部通信均通过浏览器原生 `fetch()` 调用 REST API 完成。

---

## 2. 输入输出

### 2.1 页面与 URL 结构

| 页面 | URL | 核心职责 |
|------|-----|----------|
| 主页 | `index.html` | 上传图片、填写表单、查看试卷列表 |
| 试卷详情 | `paper.html?id={paper_id}` | 左右对比预览、Canvas 框选错题 |
| 错题库 | `mistakes.html` | 筛选浏览、批量勾选、批量操作 |
| 导出页 | `export.html?ids={id1},{id2}&child_id={child_id}` | 错题预览、PDF 布局配置、触发下载 |

### 2.2 每页数据流与 API 调用

#### index.html

**初始加载时**:

- 调用 `GET /api/papers?limit=50&offset=0` 获取试卷列表，渲染卡片视图。

**用户操作触发**:

- 选择文件并点击「上传」→ 构造 `FormData`，调用 `POST /api/papers/upload`。
- 上传成功后，将返回的 paper 信息插入本地列表顶部。
- 点击试卷卡片「处理」按钮 → 调用 `POST /api/papers/{id}/process`。
- 轮询或等待处理完成后刷新列表状态。

#### paper.html?id={paper_id}

**初始加载时**:

- 从 URL 解析 `paper_id`。
- 调用 `GET /api/papers/{paper_id}` 获取试卷详情，包含 `original_path` 和 `cleaned_path`。
- 通过 `GET /static/data/{path}` 加载原图和擦除图到 Canvas。
- 调用 `GET /api/mistakes?paper_id={paper_id}` 加载已保存的框选区域，反序列化到 Canvas 状态。

**用户操作触发**:

- 在 Canvas 上拖拽画框 → 本地状态更新，不立即发请求。
- 点击「保存」→ 遍历所有框，对每个新框调用 `POST /api/mistakes`；对已修改框调用 `PATCH /api/mistakes/{id}`。
- 点击「删除框」→ 若框已有后端 ID，先调用 `DELETE /api/mistakes/{id}`，再从本地移除。

#### mistakes.html

**初始加载时**:

- 调用 `GET /api/mistakes?limit=100&offset=0` 获取全部错题。
- 解析返回数据，按 `child_id` / `subject` / `status` 分组供筛选。

**用户操作触发**:

- 切换筛选条件 → 本地过滤已缓存数据，或重新调用 `GET /api/mistakes?child_id=...&subject=...`。
- 勾选错题 → 本地维护 `selected[]` 数组。
- 点击「批量删除」→ 对 `selected[]` 中每个 ID 串行调用 `DELETE /api/mistakes/{id}`，完成后刷新列表。
- 点击「导出 PDF」→ 将 `selected[]` 编码为 URL 参数，跳转到 `export.html`。
- 更新错因类型或备注 → 调用 `PATCH /api/mistakes/{id}`。

#### export.html?ids=...

**初始加载时**:

- 从 URL 解析 `ids` 和 `child_id`。
- 调用 `GET /api/mistakes?limit=100` 获取全部错题，按 ID 过滤出待导出项。
- 通过 `GET /static/data/{path}` 加载每道错题的缩略图。

**用户操作触发**:

- 切换布局模式（`one_per_page` / `two_per_page` / `compact`）→ 仅本地预览重排。
- 点击「导出」→ 调用 `POST /api/export/pdf`，参数为 `child_id`、`mistake_ids` 数组、`layout`。
- 导出成功后，从响应中获取 `pdf_url`，触发浏览器下载。
- 调用 `GET /api/export/history?child_id=...` 可查看历史导出记录。

### 2.3 完整用户旅程数据流

```
用户打开 index.html
  → GET /api/papers (加载列表)
  → 拖拽图片 + 填写表单
  → POST /api/papers/upload (上传原图)
  ← {paper_id, status: "pending"}
  → 列表出现新卡片，显示 pending 徽章
  → 点击「处理」
  → POST /api/papers/{id}/process
  ← {status: "processed", quality_score: 0.75}
  → 状态徽章变为 processed

用户点击卡片进入 paper.html?id={id}
  → GET /api/papers/{id}
  → GET /static/data/{original_path} (加载原图)
  → GET /static/data/{cleaned_path} (加载擦除图)
  → GET /api/mistakes?paper_id={id} (加载已有框)
  → 用户在擦除图上拖拽画框
  → 填写错因和备注
  → 点击「保存」
  → POST /api/mistakes (对每个新框)
  ← {mistake_id}

用户打开 mistakes.html
  → GET /api/mistakes (加载全部)
  → 筛选 / 搜索
  → 勾选多个错题
  → 点击「导出选中」
  → 跳转到 export.html?ids=1,2,3&child_id=K1

用户进入 export.html
  → GET /api/mistakes (过滤出选中项)
  → GET /static/data/{mistake_image_path} (加载缩略图)
  → 选择布局模式
  → 点击「导出」
  → POST /api/export/pdf
  ← {pdf_url: "/static/data/exports/1.pdf", export_id: 1}
  → 浏览器自动下载 PDF
```

---

## 3. 技术选型

### 3.1 Alpine.js (CDN, v3)

选择 Alpine.js 而非 React 或 Vue 的核心原因是**零构建约束**。React 和 Vue 无论通过 CDN 引入还是构建后使用，都需要 JSX 编译器、单文件组件解析器或至少一个打包步骤。Alpine.js 通过 CDN 直接引入即可工作，所有逻辑写在 HTML 的 `x-data`、`x-on`、`x-show` 等属性中，非常适合四个页面的轻量级交互需求。其响应式模型基于 Proxy，与 Vue 3 同源，足以处理表单绑定、列表渲染、条件显示等场景。

### 3.2 Canvas API (原生)

框选功能仅需在图片上绘制矩形、显示选中和拖拽手柄，不需要复杂的几何变换、图层管理或事件系统。fabric.js 和 konva.js 虽然功能强大，但分别增加约 300KB 和 150KB 的下载体积，且引入了额外的学习成本和 API 抽象层。原生 Canvas 2D API 完全满足需求：绘制矩形用 `fillRect` / `strokeRect`，拖拽检测用简单的 AABB 碰撞，手柄用 8 个小方块表示。依赖最小化意味着更少的故障点和更快的加载速度。

### 3.3 Fetch API

所有 HTTP 请求均使用浏览器原生 `fetch()`，不引入 axios。理由如下：

- 现代浏览器对 `fetch` 的支持已足够完善，项目目标环境为 Safari iOS 和 Chrome Android，均完全支持。
- `fetch` 原生支持 `AbortController`，便于实现请求超时和取消。
- axios 的拦截器、自动 JSON 解析等功能在本项目规模下可通过 20 行封装代码实现，不值得引入额外依赖。

### 3.4 CSS (原生)

不使用 Tailwind CSS CDN 版本。Tailwind CDN 在开发时可用，但生产环境推荐构建，CDN 版体积大且存在已知性能问题。本项目采用原生 CSS，原因包括：

- 四个页面的样式总量有限，无需工具类原子化系统。
- 原生 CSS 变量（`--primary`, `--radius` 等）足以实现主题一致性。
- 避免外部 CDN 依赖，减少加载失败风险。
- 采用**移动优先**策略：基础样式针对 375px 视口，通过 `@media (min-width: 768px)` 添加桌面端增强。

### 3.5 Mock 服务器 (Python http.server)

开发阶段使用 Python 标准库的 `http.server` 模块实现 mock API。不选择 json-server 的原因是：

- json-server 基于 Node.js，需要安装 npm，违反零构建约束。
- Python `http.server` 配合自定义 `BaseHTTPRequestHandler` 可以完全模拟所有端点的请求方法和响应格式，且与项目 Python 后端生态一致。
- mock 服务器同时托管静态文件（HTML/JS/CSS）和 API，前端开发者只需运行 `python mock/mock-server.py` 即可完整工作。

### 3.6 CDN 风险缓解

Alpine.js CDN 文件约 30KB（gzip 后约 10KB），体积很小。为应对 CDN 不可用的情况，采取以下措施：

- 首选方案：`https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js`
- 降级方案：将 `cdn.min.js` 下载到 `static/vendor/alpinejs@3.min.js`，通过条件加载脚本检测 CDN 是否加载成功，失败时回退到本地文件。
- 由于 Alpine.js 不经常发布破坏性更新，锁定 v3 主版本即可保证稳定性。

---

## 4. 核心算法与流程

### 4.1 Canvas 框选状态机

框选交互由显式状态机驱动，避免事件处理中的竞态和模糊逻辑。四个状态及转换条件如下：

| 状态 | 含义 | 触发进入 | 触发退出 |
|------|------|----------|----------|
| `idle` | 空闲，无交互 | 初始状态；框保存后 | 鼠标/触摸按下 |
| `drawing` | 正在画新框 | `idle` 时按下空白处 | 抬起手指/鼠标 |
| `moving` | 正在移动已有框 | `idle` 时按下框内部（非手柄） | 抬起手指/鼠标 |
| `resizing` | 正在调整框大小 | `idle` 时按下手柄 | 抬起手指/鼠标 |

状态转换规则：

1. `idle` → `drawing`：按下事件坐标不在任何现有框内，记录 `dragStart` 为当前原图像素坐标。
2. `drawing` → `idle`：抬起事件，根据 `dragStart` 和当前坐标计算矩形，若宽高均大于 10 像素则加入 `boxes` 数组，赋予唯一 ID 和循环颜色。
3. `idle` → `moving`：按下事件坐标在某个框内，记录 `dragStart` 和框的当前位置。
4. `moving` → `idle`：抬起事件，更新框的 `x` 和 `y`。
5. `idle` → `resizing`：按下事件坐标在某个框的 8 向手柄内（8px 热区），记录 `dragStart` 和调整的边/角标识。
6. `resizing` → `idle`：抬起事件，根据拖动向量重新计算框的 `x`, `y`, `w`, `h`，确保结果不为负数。

### 4.2 坐标转换算法

坐标转换是框选功能的核心，必须精确处理 CSS 缩放、`devicePixelRatio` 和 Canvas 内部坐标系。

**步骤一：指针事件坐标 → Canvas 内部坐标**

对于鼠标事件：

```
rect = canvas.getBoundingClientRect()
canvasX = (event.clientX - rect.left) * (canvas.width / rect.width)
canvasY = (event.clientY - rect.top) * (canvas.height / rect.height)
```

对于触摸事件：

```
touch = event.touches[0] || event.changedTouches[0]
canvasX = (touch.clientX - rect.left) * (canvas.width / rect.width)
canvasY = (touch.clientY - rect.top) * (canvas.height / rect.height)
```

**步骤二：Canvas 内部坐标 → 原图像素坐标**

```
scaleX = imageNaturalWidth / canvas.width
scaleY = imageNaturalHeight / canvas.height
imgX = canvasX * scaleX
imgY = canvasY * scaleY
```

所有存入 `state.boxes` 的坐标必须是原图像素，这样无论 Canvas 被 CSS 缩放到多大或多小，框的实际物理位置始终正确。

**步骤三：绘制时反向转换**

```
drawX = box.x / scaleX
drawY = box.y / scaleY
drawW = box.w / scaleX
drawH = box.h / scaleY
```

**devicePixelRatio 处理**：

为了在高密度屏（Retina）上避免 Canvas 模糊，设置 Canvas 实际像素尺寸时乘以 `window.devicePixelRatio`，但通过 CSS 将其显示尺寸限制为容器大小。`canvas.width` 和 `canvas.height` 是实际像素，`rect.width` 和 `rect.height` 是 CSS 像素。上述公式中 `canvas.width / rect.width` 恰好等于 `devicePixelRatio`，因此转换公式在逻辑上自动包含了 DPR 修正，无需单独判断。

### 4.3 框数据模型

每个框在内存中的数据结构如下：

```javascript
{
  id: "box-uuid-or-backend-id",   // 本地临时 ID 或后端返回的 mistake_id
  x: 120,                          // 原图像素坐标，左上角 x
  y: 340,                          // 原图像素坐标，左上角 y
  w: 200,                          // 原图像素宽度
  h: 80,                           // 原图像素高度
  color: "#FF6B6B",                // 显示颜色，6 色循环
  note: "计算步骤漏了进位",         // 用户备注
  errorType: "计算错误"             // 错因类型，来自固定枚举
}
```

坐标存储为整数（`Math.round`），避免浮点误差在后续裁剪时产生亚像素偏差。`id` 在首次创建时为本地生成的临时 UUID，保存到后端成功后替换为后端返回的 `mistake_id`，便于后续 PATCH 和 DELETE 操作。

### 4.4 多点触控处理

移动端框选仅支持单指操作，多点触控事件需要被安全忽略或屏蔽。

事件注册顺序与处理逻辑：

1. `touchstart`：调用 `event.preventDefault()` 阻止页面滚动。仅当 `event.touches.length === 1` 时处理，否则忽略。提取 `event.touches[0]` 的 `clientX/clientY`。
2. `touchmove`：同样 `event.preventDefault()`。单指时按上述坐标转换算法实时更新框的位置或大小，触发 Canvas `requestAnimationFrame` 重绘。
3. `touchend`：从 `event.changedTouches[0]` 提取最终坐标，执行状态机退出逻辑（`drawing` / `moving` / `resizing` → `idle`）。

鼠标事件（`mousedown`, `mousemove`, `mouseup`）与触摸事件并行注册，互不影响。桌面端优先使用鼠标事件，移动端优先使用触摸事件。不直接使用 Pointer Events API，因为 iOS Safari 在部分旧版本中对 `pointer` 事件的支持不完整，而 `touch` + `mouse` 双保险覆盖率更高。

### 4.5 批量保存流程

用户在 paper.html 上完成所有框选后，点击「保存」按钮触发以下流程：

1. 前端遍历 `state.boxes`，按 `id` 前缀区分新框和已有框。
2. 新框（临时 UUID）：对每个框调用 `POST /api/mistakes`，请求体包含 `paper_id`, `crop_x` (box.x), `crop_y` (box.y), `crop_width` (box.w), `crop_height` (box.h), `note`, `error_type`。
3. 已有框（后端 ID）且被修改过：调用 `PATCH /api/mistakes/{id}`，可更新 `note`、`error_type`。
4. 被删除的已有框：在删除时已即时调用 `DELETE /api/mistakes/{id}`，不在保存流程中处理。
5. 所有请求完成后，刷新页面或重新调用 `GET /api/mistakes?paper_id={id}` 同步最新状态。

为提升体验，保存时显示全局 loading 遮罩。若某次 `POST /api/mistakes` 失败，显示具体错误 toast，但继续处理剩余框，最后汇总失败项供用户重试。

### 4.6 上传流程

1. 用户通过 `<input type="file" accept="image/*">` 或拖拽选择文件。
2. 前端验证文件扩展名（`.jpg`, `.jpeg`, `.png`, `.heic`），大小限制 20MB。
3. 构造 `FormData`，追加字段：`file` (File 对象), `child_id`, `subject`, `paper_type`, `title`。
4. 调用 `fetch('/api/papers/upload', { method: 'POST', body: formData })`。
5. `fetch` 上传时浏览器自动设置 `Content-Type: multipart/form-data`，无需手动指定。
6. 上传超时设置为 120 秒，使用 `AbortController`。
7. 成功后解析 JSON，将新试卷插入本地列表顶部，清空表单。
8. 失败时根据 HTTP 状态码显示不同提示：413 为文件过大，400 为参数错误，500 为服务器异常。

---

## 5. 接口设计

### 5.1 api.js 模块函数清单

所有函数返回 `Promise`，成功时 resolve 后端 JSON，失败时 reject 包含 `message` 的 `Error`。

```javascript
// === 试卷相关 ===

/**
 * 上传试卷图片
 * @param {File} file - 用户选择的图片文件
 * @param {string} childId - 'K1' 或 'K2'
 * @param {string} subject - '数学'|'语文'|'英语'|'科学'|'其他'
 * @param {string} [title=''] - 可选标题/备注
 * @returns {Promise<{paper_id: number, status: string}>}
 */
async function uploadPaper(file, childId, subject, title = '')

/**
 * 查询试卷列表
 * @param {Object} [filters={}] - 可选过滤条件 {child_id, subject, status, limit, offset}
 * @returns {Promise<{papers: Array, total: number}>}
 */
async function listPapers(filters = {})

/**
 * 获取单张试卷详情
 * @param {number} paperId
 * @returns {Promise<Object>} 包含图片 URL 的试卷对象
 */
async function getPaper(paperId)

/**
 * 触发试卷图像处理
 * @param {number} paperId
 * @returns {Promise<{status: string, quality_score: number, warnings: Array}>}
 */
async function processPaper(paperId)

// === 错题相关 ===

/**
 * 创建错题记录
 * @param {number} paperId
 * @param {Object} cropData - {x, y, width, height} 原图像素坐标
 * @param {string} [note='']
 * @param {string} [errorType='']
 * @returns {Promise<{mistake_id: number}>}
 */
async function createMistake(paperId, cropData, note, errorType)

/**
 * 查询错题列表
 * @param {Object} [filters={}] - {child_id, subject, status, paper_id, limit, offset}
 * @returns {Promise<{mistakes: Array, total: number}>}
 */
async function listMistakes(filters = {})

/**
 * 删除错题
 * @param {number} mistakeId
 * @returns {Promise<{success: boolean}>}
 */
async function deleteMistake(mistakeId)

/**
 * 更新错题信息
 * @param {number} mistakeId
 * @param {Object} data - {status, note, error_type} 中任意字段
 * @returns {Promise<{success: boolean}>}
 */
async function updateMistake(mistakeId, data)

// === 导出相关 ===

/**
 * 导出错题 PDF
 * @param {string} childId
 * @param {number[]} mistakeIds
 * @param {string} [layout='one_per_page']
 * @param {string} [title=''] PDF 首页标题（如 "K1 数学错题 2026-05-31"）
 * @returns {Promise<{pdf_url: string, export_id: number}>}
 */
async function exportPdf(childId, mistakeIds, layout = 'one_per_page', title = '')

/**
 * 查询导出历史
 * @param {string} [childId]
 * @param {number} [limit=20]
 * @returns {Promise<{exports: Array}>}
 */
async function getExportHistory(childId, limit = 20)
```

### 5.2 错误处理策略

统一错误映射表：

| HTTP 状态码 | 错误场景 | 用户提示文案 |
|-------------|----------|--------------|
| 400 | 参数校验失败（缺少字段、非法枚举值） | "请检查填写的内容是否正确" |
| 404 | 资源不存在（试卷/错题已被删除） | "找不到这条记录，可能已经删除了" |
| 413 | 文件过大 | "图片太大了，请压缩后再上传" |
| 422 | 业务逻辑错误 | 显示后端返回的 `error` 字段内容 |
| 429 | 请求过于频繁 | "操作太快啦，稍等一会儿再试" |
| 500 / 502 / 503 | 服务器内部错误 | "服务器开小差了，请稍后再试" |
| 网络断开 / DNS 失败 | `fetch` 抛出 TypeError | "网络好像断了，检查一下网络连接" |
| 超时 | AbortController 触发 | "请求超时，请检查网络或重试" |

所有错误均通过统一的 `handleError(error)` 函数处理，该函数判断错误类型后显示顶部 toast 通知，3 秒后自动消失。

### 5.3 超时策略

- 默认请求超时：30 秒。
- 上传请求超时：120 秒（大图片在慢网络下可能需要较长时间）。
- 实现方式：每个 `fetch` 调用伴随一个 `AbortController`，在 `setTimeout` 中调用 `controller.abort()`。

### 5.4 Loading 状态钩子

`api.js` 暴露两个全局回调钩子，供 Alpine.js  store 注入：

```javascript
let onRequestStart = () => {};
let onRequestEnd = () => {};

export function setHooks(start, end) {
  onRequestStart = start;
  onRequestEnd = end;
}
```

每次 `fetch` 调用前执行 `onRequestStart()`，无论成功或失败，最终在 `finally` 中执行 `onRequestEnd()`。页面级 store 利用这两个钩子控制全局 loading 遮罩或局部按钮 spinner。

---

## 6. 数据结构

### 6.1 页面级 Alpine.js Store

#### index.html — papersStore

```javascript
{
  papers: [],           // 试卷列表，元素为后端返回的 Paper JSON
  uploading: false,     // 上传中状态，控制按钮和 spinner
  formData: {           // 表单绑定对象
    childId: 'K1',
    subject: '数学',
    paperType: '其他',
    title: ''
  },
  dragOver: false,      // 拖拽悬停状态，控制上传区高亮
  error: null,          // 当前错误消息
  hasMore: false        // 是否还有更多数据可加载
}
```

#### paper.html — paperStore

```javascript
{
  paper: null,          // 当前试卷详情
  imageLoaded: false,   // 图片是否加载完成
  boxes: [],            // 框选数组，元素为 {id, x, y, w, h, color, note, errorType}
  selectedBoxId: null,  // 当前选中框的 ID
  mode: 'idle',         // 状态机当前状态
  dragState: {          // 拖拽过程中的临时数据
    startX: 0,
    startY: 0,
    origX: 0,           // 移动/缩放前的原始位置
    origY: 0,
    origW: 0,
    origH: 0,
    handle: null        // 缩放时标识被拖拽的手柄位置（如 'se', 'n'）
  },
  saving: false,        // 保存中状态
  activeTab: 'cleaned'  // 移动端：'original' | 'cleaned'，控制显示哪张图
}
```

#### mistakes.html — mistakesStore

```javascript
{
  mistakes: [],         // 全部错题列表
  filtered: [],         // 筛选后的显示列表
  filters: {            // 当前筛选条件
    childId: '',
    subject: '',
    status: ''
  },
  selected: [],         // 已勾选 mistake_id 数组
  batchMode: false,     // 是否进入批量操作模式（有选中项时自动 true）
  loading: false,
  error: null
}
```

#### export.html — exportStore

```javascript
{
  selectedMistakes: [], // 从 URL 解析出的待导出错题完整对象
  config: {             // 导出配置
    layout: 'one_per_page',  // 'one_per_page' | 'two_per_page' | 'compact'
    title: ''           // PDF 标题
  },
  exporting: false,     // 导出中状态
  pdfUrl: null,         // 导出成功后返回的下载链接
  history: []           // 该 child_id 的导出历史
}
```

### 6.2 Canvas 核心状态对象

```javascript
const canvasState = {
  // 图像维度（原始像素）
  imageNaturalWidth: 0,
  imageNaturalHeight: 0,

  // Canvas 实际像素尺寸（含 DPR）
  canvasPixelWidth: 0,
  canvasPixelHeight: 0,

  // Canvas CSS 显示尺寸
  displayWidth: 0,
  displayHeight: 0,

  // 框选数据（核心）
  boxes: [],

  // 交互状态
  selectedBoxId: null,
  mode: 'idle',
  dragStart: null,      // {x, y} 原图像素坐标

  // 衍生比例（缓存，避免重复计算）
  scaleX: 0,            // imageNaturalWidth / canvasPixelWidth
  scaleY: 0             // imageNaturalHeight / canvasPixelHeight
};
```

### 6.3 API 响应形状预期

前端在解析 API 响应时，期望以下 JSON 结构：

**`GET /api/papers`**:

```json
{
  "papers": [
    {
      "id": 1,
      "child_id": "K1",
      "subject": "数学",
      "paper_type": "单元卷",
      "title": "期中复习卷",
      "original_path": "originals/K1/数学/20260531_153022_abc123.jpg",
      "processed_path": "processed/1/processed.jpg",
      "cleaned_path": "processed/1/cleaned.jpg",
      "upload_time": "2026-05-31 15:30:22",
      "status": "processed",
      "quality_score": 0.85
    }
  ],
  "total": 42
}
```

**`GET /api/papers/{id}`**: 单条 Paper 对象，字段同上，额外包含可被 `GET /static/data/{path}` 访问的完整图片 URL。

**`POST /api/papers/upload`**:

```json
{ "paper_id": 1, "status": "pending" }
```

**`POST /api/papers/{id}/process`**:

```json
{ "status": "processed", "quality_score": 0.75, "warnings": ["轻微倾斜已矫正"] }
```

**`GET /api/mistakes`**:

```json
{
  "mistakes": [
    {
      "id": 1,
      "paper_id": 1,
      "child_id": "K1",
      "subject": "数学",
      "crop_x": 120,
      "crop_y": 340,
      "crop_width": 200,
      "crop_height": 80,
      "mistake_image_path": "mistakes/1/original.jpg",
      "clean_mistake_image_path": "mistakes/1/clean.jpg",
      "note": "漏了进位",
      "error_type": "计算错误",
      "status": "new",
      "created_at": "2026-05-31 16:00:00"
    }
  ],
  "total": 15
}
```

**`POST /api/mistakes`**:

```json
{ "mistake_id": 1 }
```

**`PATCH /api/mistakes/{id}` / `DELETE /api/mistakes/{id}`**:

```json
{ "success": true }
```

**`POST /api/export/pdf`**:

```json
{ "pdf_url": "/static/data/exports/1.pdf", "export_id": 1 }
```

**`GET /api/export/history`**:

```json
{
  "exports": [
    {
      "id": 1,
      "child_id": "K1",
      "subject": "数学",
      "mistake_ids": "[1,2,3]",
      "pdf_path": "exports/1.pdf",
      "created_at": "2026-05-31 17:00:00"
    }
  ]
}
```

---

## 7. 测试策略

### 7.1 Mock 服务器覆盖

`mock/mock-server.py` 必须完整实现以下 10 个端点，返回结构符合 INTERFACE-CONTRACT.md 的 JSON 形状：

1. `POST /api/papers/upload` — 接收 multipart，返回 `{paper_id, status}`。
2. `GET /api/papers` — 返回 5 条以上带不同状态（pending / processed / failed）的假数据。
3. `GET /api/papers/{id}` — 返回单条详情，包含指向 `mock/fixtures/` 中示例图片的 URL。
4. `POST /api/papers/{id}/process` — `time.sleep(2)` 后返回 `status=processed` 及随机 quality_score。
5. `POST /api/mistakes` — 接收表单/JSON，返回递增的 `mistake_id`。
6. `GET /api/mistakes` — 返回多条假数据，支持 `paper_id` 过滤。
7. `DELETE /api/mistakes/{id}` — 返回 `{success: true}`。
8. `PATCH /api/mistakes/{id}` — 返回 `{success: true}`。
9. `POST /api/export/pdf` — 返回指向 `mock/fixtures/sample.pdf` 的 `pdf_url`。
10. `GET /api/export/history` — 返回 2-3 条导出历史假数据。

Mock  fixtures 目录放置 2-3 张不同尺寸的 JPG 图片和 1 个小型 PDF 文件，确保前端在 mock 环境下能真实预览和下载。

### 7.2 手动测试场景

**上传流程**：

1. 打开 index.html，拖拽一张 JPG 到上传区，确认高亮反馈。
2. 选择 K2、英语，填写标题，点击上传。
3. 确认列表顶部出现新卡片，状态为 pending。
4. 点击「处理」，确认按钮进入 loading，2 秒后状态变为 processed。

**框选流程**：

1. 进入 paper.html?id=1，确认原图和擦除图均正常加载。
2. 在擦除图上拖拽画一个矩形框，确认框显示为预设颜色之一。
3. 点击框，确认出现选中高亮和 8 个调整手柄。
4. 拖拽右下角手柄放大框，确认尺寸实时更新。
5. 填写备注和错因类型，点击保存。
6. 刷新页面，确认框的位置、备注、错因均正确恢复。

**错题 CRUD**：

1. 打开 mistakes.html，确认筛选栏能按孩子、学科、状态过滤。
2. 勾选 3 道错题，确认底部浮现批量操作栏。
3. 点击批量删除，确认列表刷新且选中项消失。
4. 单独修改一道错题的错因类型，确认 PATCH 调用后 UI 更新。

**导出流程**：

1. 在 mistakes.html 勾选 2 道错题，点击「导出选中」。
2. 确认跳转到 export.html?ids=...,child_id=...，页面显示 2 张缩略图。
3. 切换布局模式为「两题一页」，确认预览布局变化。
4. 点击「导出」，确认 loading 后浏览器触发 PDF 下载。

### 7.3 移动端测试

- **Safari iOS**：iPhone 12 或更新机型，测试触摸画框、input file 拍照、页面滚动。
- **Chrome Android**：Pixel 系列或主流国产安卓机，测试多点触控屏蔽、大按钮点击热区。
- **响应式验证**：确保 375px 宽度下无横向滚动条，所有按钮高度不低于 44px，字体大小不低于 14px。

### 7.4 边缘情况

| 场景 | 预期行为 |
|------|----------|
| 网络断开（飞行模式） | 顶部 toast 提示 "网络好像断了"，操作按钮恢复可点击状态 |
| 上传 15MB 高清图片 | 进度条或 spinner 持续显示，120 秒内完成；超时后提示重试 |
| 上传 HEIC 文件 | 前端不预览、不转换，直接通过 FormData 上传；后端负责处理 |
| Canvas 上画极小的框（< 10px） | 抬起时不创建框，避免误触产生无效数据 |
| 快速连续点击保存按钮 | 首次点击后禁用按钮，直到所有请求完成，防止重复提交 |
| 后端返回 500 | toast 提示 "服务器开小差了"，不丢失本地框选数据 |
| 试卷图片宽高比极端（如 1:3） | Canvas 自适应容器宽度，保持比例缩放，不拉伸变形 |

### 7.5 视觉回归

在 375px 宽度视口下，对四个页面分别截图保存为基准图：

- `index.html`：上传区 + 3 张试卷卡片
- `paper.html?id=1`：左右对比 + 1 个框选
- `mistakes.html`：筛选栏 + 2 列错题卡片
- `export.html`：2 张错题预览 + 布局选择器

后续迭代时对比新截图与基准图，检测非预期的布局漂移。

### 7.6 验收标准对照

来源于 M3-WEB-FRONTEND.md 的验收标准，测试完成后逐条确认：

- [ ] 四个页面在 mock 和真实后端下均能正常打开
- [ ] 上传流程完整走通：选文件 → 填表单 → 上传 → 列表出现
- [ ] paper.html 正确加载原图和擦除图
- [ ] Canvas 框选支持画框、删框、调整大小，输出坐标为原图像素
- [ ] 多个框选通过批量 POST 一次性保存
- [ ] mistakes.html 支持筛选、勾选、批量导出
- [ ] export.html 触发后端生成 PDF 并下载
- [ ] 手机端无横向滚动，按钮可点，触摸事件正常
- [ ] 全程不依赖 npm / node / 任何构建工具

---

## 8. 风险与对策

### 8.1 Canvas 坐标漂移（Retina 显示屏）

**风险描述**：高 DPR 设备（MacBook Retina、iPhone）上，若未正确处理 `devicePixelRatio`，Canvas 绘制会出现模糊，或框选坐标与实际图像像素产生偏移，导致裁切区域错误。

**对策**：严格执行双向坐标转换算法。设置 Canvas 时，`canvas.width = displayWidth * DPR`，`canvas.height = displayHeight * DPR`，然后通过 CSS `width: displayWidth` 限制显示尺寸。所有事件坐标先除以 DPR 得到 Canvas 内部坐标，再乘以 `(naturalWidth / canvas.width)` 得到原图坐标。绘制时反向转换。在 mock 环境中使用 Chrome DevTools 模拟 DPR=2 和 DPR=3 进行验证。

### 8.2 移动端 Safari 兼容性

**风险描述**：iOS Safari 存在多个已知行为差异：`input[type=file]` 的 `capture` 属性表现不一致；`touch` 事件可能触发 `mouse` 事件导致处理函数执行两次；滚动穿透可能干扰 Canvas 触摸操作。

**对策**：

- `<input type="file">` 使用 `accept="image/*"`，不依赖 `capture` 属性，由系统弹窗让用户自选拍照或相册。
- 在 `touchstart` 和 `touchmove` 中调用 `event.preventDefault()`，阻断默认滚动和双击缩放。
- 不使用 Pointer Events API，而是并行注册 `touch` 和 `mouse` 事件，在事件处理器中通过 `event.type` 区分来源，避免双重触发。
- 对 `touchend` 后的 300ms 延迟点击问题，若出现则通过 `touch-action: manipulation` 在 CSS 层面缓解。

### 8.3 Alpine.js CDN 不可用

**风险描述**：CDN 服务（jsDelivr）在特定网络环境下可能访问缓慢或完全不可用，导致页面白屏或交互失效。

**对策**：

- 将 Alpine.js v3 的 `cdn.min.js` 下载一份到 `static/vendor/alpinejs@3.x.x.min.js`。
- 页面加载时优先请求 CDN，通过 `script.onload` 检测是否成功；若 5 秒内未触发 onload，则动态插入本地备份 script 标签。
- Alpine.js 仅 30KB，本地备份对仓库体积影响可忽略。

### 8.4 大图片导致 Canvas OOM（移动端内存溢出）

**风险描述**：手机拍摄的照片分辨率可达 4000×3000 以上，若直接以完整尺寸绘制到 Canvas 中，低端安卓机或旧款 iPhone 可能因内存不足导致页面崩溃或浏览器被系统终止。

**对策**：

- paper.html 的 Canvas 上显示的擦除图和原图，通过 CSS 缩放限制最大显示宽度为屏幕宽度的 100%，Canvas 实际像素尺寸不超过 1920px（长边）。
- 创建一个隐藏的 `<img>` 元素加载原图以获取 `naturalWidth/naturalHeight`，但 Canvas 上绘制的是按比例缩小的版本。
- 原始高分辨率文件仅在 `POST /api/papers/upload` 时通过 FormData 完整传给后端，前端不保留在内存中。
- 在检测到图片 `naturalWidth > 3000` 时，在 Canvas 绘制前先用 `drawImage` 的源矩形参数进行等比降级采样。

### 8.5 API 契约漂移

**风险描述**：M4 后端在开发过程中可能调整字段名、响应结构或端点路径，导致前端解析失败。由于 M3 与 M4 并行开发，这种漂移风险始终存在。

**对策**：

- mock 服务器严格按 INTERFACE-CONTRACT.md 实现，作为契约的物理校验器。任何后端变更若未同步更新 mock，前端开发会立即发现不一致。
- `api.js` 中所有函数对响应 JSON 做最小校验：若期望字段缺失，抛出带有具体字段名的错误，方便快速定位契约偏差。
- 在持续集成阶段（如有），增加契约测试：mock 服务器和真实后端对同一请求应返回结构一致的 JSON。
- 团队协作约定：任何接口变更必须先改 INTERFACE-CONTRACT.md，再改代码。

---

*本文档为 M3 Web 前端的技术实现计划，所有 API 端点、参数名、响应结构均与 `INTERFACE-CONTRACT.md` v1.0-FINAL 保持一致。*
