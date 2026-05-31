# M4: Web 后端 — 开发任务卡

| 项目 | 内容 |
|------|------|
| 模块编号 | M4 |
| 状态 | 待开发 |
| 可并行 | ⚠️（需等 M1+M2 接口稳定） |
| 依赖 | M1 + M2 + M5 |

---

## 模块定位

FastAPI 后端，是系统的**胶水层**。串联 M1（图像处理）+ M2（数据层）+ M5（PDF 导出），对外提供 REST API，同时服务 M3 的静态文件。

- 不实现业务算法，只做编排：接收请求 → 调 M1/M2/M5 → 返回响应
- 文件落盘、目录创建、字段拼装等"脏活"集中在此层
- M3 前端、移动端浏览器都通过本模块的 HTTP 接口访问后端能力

---

## 前置阅读

- `docs/INTERFACE-CONTRACT.md` **全文**（特别是第四节 4.4）
- `docs/INTERFACE-CONTRACT.md` **第四节 4.1**（M1 接口）
- `docs/INTERFACE-CONTRACT.md` **第四节 4.2**（M2 接口）
- `docs/INTERFACE-CONTRACT.md` **第四节 4.5**（M5 接口）

读完上述章节再开始编码。M4 调用 M1/M2/M5 时，参数与返回值必须严格匹配契约。

---

## 目录结构

```
src/m4_web_backend/
├── __init__.py
├── app.py              # FastAPI 应用入口
├── routes/
│   ├── __init__.py
│   ├── papers.py       # /api/papers/* 路由
│   ├── mistakes.py     # /api/mistakes/* 路由
│   └── exports.py      # /api/export/* 路由
├── schemas.py          # Pydantic 请求/响应模型
├── config.py           # 配置（路径、端口等）
└── deps.py             # 依赖注入（Database 实例等）
```

`tests/m4/` 目录单独存放测试，不混入 `src/`。

---

## API 路由完整定义

以下定义复制自 `INTERFACE-CONTRACT.md` 4.4 节。**禁止改动签名**，如需变更必须先改契约文档。

### 试卷相关 (routes/papers.py)

```python
@app.post('/api/papers/upload')
async def upload_paper(file: UploadFile, child_id: str, subject: str,
                       paper_type: str = '其他', title: str = None):
    """
    上传试卷图片。
    1. 验证文件类型（jpg/jpeg/png/heic）
    2. 保存原图到 data/originals/{child_id}/{subject}/
    3. 写入 DB (status='pending')
    4. 返回 paper_id
    """
    # Response: {"paper_id": 1, "status": "pending"}

@app.post('/api/papers/{paper_id}/process')
async def process_paper(paper_id: int):
    """
    触发图像处理。
    1. 从 DB 获取 paper 信息
    2. 调用 M1.process_paper()
    3. 更新 DB 状态
    4. 返回处理结果
    """
    # Response: {"status": "processed", "quality_score": 0.75, "warnings": [...]}

@app.get('/api/papers')
async def list_papers(child_id: str = None, subject: str = None,
                      status: str = None, limit: int = 50, offset: int = 0):
    # Response: {"papers": [...], "total": 42}

@app.get('/api/papers/{paper_id}')
async def get_paper(paper_id: int):
    # Response: Paper 对象 + 图片 URL
```

### 错题相关 (routes/mistakes.py)

```python
@app.post('/api/mistakes')
async def create_mistake(paper_id: int, crop_x: int, crop_y: int,
                         crop_width: int, crop_height: int,
                         note: str = None, error_type: str = None):
    """
    创建错题。
    1. 从 processed/cleaned 图片中裁切指定区域
    2. 保存裁切图到 data/mistakes/{id}/
    3. 写入 DB
    """
    # Response: {"mistake_id": 1}

@app.get('/api/mistakes')
async def list_mistakes(child_id: str = None, subject: str = None,
                        status: str = None, limit: int = 100, offset: int = 0):
    # Response: {"mistakes": [...], "total": 15}

@app.patch('/api/mistakes/{mistake_id}')
async def update_mistake(mistake_id: int, status: str = None, note: str = None,
                         error_type: str = None):
    # Response: {"success": true}

@app.delete('/api/mistakes/{mistake_id}')
async def delete_mistake(mistake_id: int):
    # Response: {"success": true}
```

### 导出相关 (routes/exports.py)

```python
@app.post('/api/export/pdf')
async def export_pdf(child_id: str, mistake_ids: list[int],
                     layout: str = 'one_per_page'):
    """
    导出错题 PDF。
    1. 从 DB 查询错题图片路径
    2. 调用 M5.export_pdf()
    3. 记录导出日志
    4. 返回 PDF 下载链接
    """
    # Response: {"pdf_url": "/static/data/exports/1.pdf", "export_id": 1}

@app.get('/api/export/history')
async def export_history(child_id: str = None, limit: int = 20):
    # Response: {"exports": [...]}
```

每个路由必须包含：
- HTTP 方法 + 路径（与契约一致）
- 请求参数（Query / Body / Form）
- 响应格式（用 Pydantic 模型约束）
- 内部逻辑步骤（如上注释所述）

---

## 实现要求

### app.py

- 启动时初始化 `Database` 实例（M2），通过依赖注入下发给路由
- 挂载静态文件服务（服务 M3 前端）
- 挂载 `data/` 目录为静态资源（图片访问）
- CORS 允许所有来源（局域网使用，无需鉴权）
- 监听 `0.0.0.0:8900`
- `if __name__ == '__main__'` 入口可直接 `python -m src.m4_web_backend.app` 启动

### 上传流程 (routes/papers.py)

1. 接收 `multipart/form-data`
2. 验证文件类型（jpg / jpeg / png / heic）
3. 验证文件大小（不超过 16MB）
4. 生成文件名：`{timestamp}_{uuid4_short}.jpg`，timestamp 格式 `20260531_153022`
5. 保存到 `data/originals/{child_id}/{subject}/`（目录不存在自动创建）
6. 调用 `db.create_paper(...)` 写入 DB
7. 返回 `{"paper_id": ..., "status": "pending"}`

### 处理流程 (routes/papers.py)

1. 调用 `db.get_paper(paper_id)` 获取 paper 信息，不存在返回 404
2. 调用 `db.update_paper_status(paper_id, status='processing')`
3. 创建输出目录 `data/processed/{paper_id}/`
4. 调用 `M1.process_paper(original_path, output_dir)`
5. 根据 `ProcessResult.success`：
   - 成功：`update_paper_status(status='processed', processed_path, cleaned_path, quality_score)`
   - 失败：`update_paper_status(status='failed', error_message=result.error)`
6. 返回处理结果（包含 status / quality_score / warnings）

### 错题流程 (routes/mistakes.py)

1. 接收框选坐标（crop_x, crop_y, crop_width, crop_height）
2. 用 Pillow 从 `processed_path` 和 `cleaned_path` 分别裁切指定区域
3. 保存裁切图到 `data/mistakes/{mistake_id}/`，文件名 `original.jpg` 和 `clean.jpg`
4. 调用 `db.create_mistake(...)` 写入 DB（注意：mistake_id 由 DB 生成，需先 create 再用 id 建目录并回填路径，或者先生成 uuid 再建路径）
5. 返回 `{"mistake_id": ...}`

> 实现提示：mistake_id 是 DB 自增主键，可先调用 `create_mistake(...)` 拿到 id，再裁切保存图片，最后用 `update_mistake(...)` 回填路径。或者先建一个临时目录，create 后改名。两种方案都可，选清晰的。

### 导出流程 (routes/exports.py)

1. 调用 `db.list_mistakes` 或循环 `db.get_mistake` 查询错题图片路径列表
2. 拼装 `ExportConfig`（layout 由请求传入）
3. 输出路径 `data/exports/{export_id}.pdf`，export_id 来自 `db.create_export_log` 返回值
4. 调用 `M5.export_pdf(image_paths, output_path, config)`
5. 返回 `{"pdf_url": "/static/data/exports/{export_id}.pdf", "export_id": ...}`

### Pydantic 模型 (schemas.py)

定义所有请求和响应的数据模型，确保类型安全。至少包含：

```python
class UploadResponse(BaseModel):
    paper_id: int
    status: str

class ProcessResponse(BaseModel):
    status: str
    quality_score: float | None
    warnings: list[str] = []
    error: str | None = None

class PaperListResponse(BaseModel):
    papers: list[PaperOut]
    total: int

class MistakeCreateRequest(BaseModel):
    paper_id: int
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    note: str | None = None
    error_type: str | None = None

class ExportPdfRequest(BaseModel):
    child_id: str
    mistake_ids: list[int]
    layout: str = 'one_per_page'
```

其余模型按 4.4 节响应注释补全。

### config.py

集中管理路径与端口：

```python
DATA_DIR = Path('data')
ORIGINALS_DIR = DATA_DIR / 'originals'
PROCESSED_DIR = DATA_DIR / 'processed'
MISTAKES_DIR = DATA_DIR / 'mistakes'
EXPORTS_DIR = DATA_DIR / 'exports'
DB_PATH = DATA_DIR / 'exam_paper.db'
FRONTEND_DIR = Path('src/m3_web_frontend')
HOST = '0.0.0.0'
PORT = 8900
MAX_UPLOAD_SIZE = 16 * 1024 * 1024
ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.heic'}
```

### deps.py

```python
from functools import lru_cache
from src.m2_data_layer import Database
from .config import DB_PATH

@lru_cache(maxsize=1)
def get_db() -> Database:
    return Database(str(DB_PATH))
```

路由函数通过 `db: Database = Depends(get_db)` 获取实例。

---

## 测试要求

- 用 FastAPI `TestClient`
- 测试所有 API 端点（上传、处理、列表、详情、错题 CRUD、导出、历史）
- 可以 mock M1 和 M5（它们是外部依赖，不依赖真实图像处理与 PDF 生成）
- M2 用真实的临时 SQLite 文件（每个测试 fixture 独立）
- 测试命令：

```bash
pytest tests/m4/ -v
```

测试用例至少覆盖：
- 上传成功 / 文件类型非法 / 超大文件
- 处理成功 / 处理失败（M1 返回 success=False）
- 错题创建并校验图片落盘
- 错题列表 / 更新 / 删除
- 导出 PDF（mock M5，仅校验调用参数）
- 导出历史

---

## 验收标准

- 所有 API 端点可调用，签名与 4.4 节一致
- Swagger UI 可访问 `http://localhost:8900/docs`
- 上传 → 处理 → 框选 → 导出 全流程走通
- 静态文件服务正常（前端页面 `http://localhost:8900/` 可访问）
- 手机同局域网可通过 `http://{Mac的IP}:8900` 访问
- `pytest tests/m4/ -v` 全绿

---

## 技术要点

```python
# FastAPI 静态文件（服务 M3 前端）
from fastapi.staticfiles import StaticFiles
app.mount('/static', StaticFiles(directory='src/m3_web_frontend'), name='static')

# 数据目录静态服务（图片访问）
app.mount('/static/data', StaticFiles(directory='data'), name='data')

# 上传文件
from fastapi import UploadFile, File, Form

# CORS（局域网无鉴权，允许所有来源）
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

# 启动
import uvicorn
uvicorn.run(app, host='0.0.0.0', port=8900)
```

### 文件命名工具

```python
from datetime import datetime
import uuid

def make_filename(ext: str = '.jpg') -> str:
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    short = uuid.uuid4().hex[:8]
    return f'{ts}_{short}{ext}'
```

### Pillow 裁切

```python
from PIL import Image

def crop_and_save(src_path: str, dst_path: str,
                  x: int, y: int, w: int, h: int) -> None:
    with Image.open(src_path) as img:
        img.crop((x, y, x + w, y + h)).save(dst_path, quality=92)
```

---

## 与其他模块的协作边界

- **M1**：只调用 `process_paper(input_path, output_dir)`，处理 `ProcessResult`。不直接调用 `generate_mask` / `apply_mask`。
- **M2**：所有数据库操作走 `Database` 实例方法，**不允许**在路由里写 SQL。
- **M3**：M4 仅提供静态文件挂载，前端代码由 M3 维护，M4 不修改 HTML/JS。
- **M5**：只调用 `export_pdf(image_paths, output_path, config)`，处理布尔返回值。
