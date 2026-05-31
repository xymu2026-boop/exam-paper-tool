# 试卷宝接口契约文档（最终版）

> **版本**: v1.0-FINAL  
> **日期**: 2026-05-31  
> **性质**: 最终版接口契约，所有模块开发必须遵守此文档

---

## 一、文档定位

- 这是所有模块开发的**唯一权威接口定义**
- OpenCode Agent 开发任何模块前，**必须先读此文档**
- 模块间通信**只能通过本文档定义的接口**进行
- 任何接口变更必须**先修改本文档，再修改代码**

---

## 二、系统架构总览

### 2.1 模块划分

| 模块 | 目录 | 职责 | 技术特性 |
|------|------|------|----------|
| M1 | `src/m1_image_engine/` | 图像处理引擎 | 纯 Python，无 UI 依赖 |
| M2 | `src/m2_data_layer/` | 数据层 | SQLite + CRUD API |
| M3 | `src/m3_web_frontend/` | Web 前端 | HTML + Alpine.js + Canvas |
| M4 | `src/m4_web_backend/` | Web 后端 | FastAPI, 串联 M1+M2 |
| M5 | `src/m5_pdf_export/` | PDF 导出 | 纯 Python，无 UI 依赖 |

### 2.2 数据流

```
用户上传图片 → [M4 API] → 保存原图 → [M2 写入DB]
                         → 调用 [M1 处理] → 预处理图 + 擦除图
                         → [M2 更新状态]
用户框选错题 → [M4 API] → [M2 写入错题]
用户导出PDF → [M4 API] → [M2 查询错题] → [M5 生成PDF]
```

---

## 三、共享数据模型（所有模块必须遵守）

### 3.1 数据库 Schema (SQLite)

```sql
-- 文件位置: data/exam_paper.db

CREATE TABLE IF NOT EXISTS paper (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL CHECK(child_id IN ('K1', 'K2')),
    subject TEXT NOT NULL CHECK(subject IN ('数学','语文','英语','科学','其他')),
    paper_type TEXT DEFAULT '其他' CHECK(paper_type IN ('作业','单元卷','考试卷','练习册','其他')),
    title TEXT,
    original_path TEXT NOT NULL,
    processed_path TEXT,
    cleaned_path TEXT,
    upload_time TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','processing','processed','failed')),
    quality_score REAL,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS mistake (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id INTEGER NOT NULL REFERENCES paper(id),
    child_id TEXT NOT NULL,
    subject TEXT NOT NULL,
    crop_x INTEGER NOT NULL,
    crop_y INTEGER NOT NULL,
    crop_width INTEGER NOT NULL,
    crop_height INTEGER NOT NULL,
    mistake_image_path TEXT,
    clean_mistake_image_path TEXT,
    note TEXT,
    error_type TEXT CHECK(error_type IN ('粗心','概念不清','计算错误','不会做','其他',NULL)),
    status TEXT NOT NULL DEFAULT 'new' CHECK(status IN ('new','printed','practiced','passed','retry')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS export_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    child_id TEXT NOT NULL,
    subject TEXT,
    mistake_ids TEXT NOT NULL,  -- JSON array of mistake IDs
    pdf_path TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
```

### 3.2 文件存储约定

```
data/
├── exam_paper.db          # SQLite 数据库
├── samples/               # 测试样本（不进 git）
├── originals/             # 原图归档
│   ├── K1/
│   │   ├── 数学/
│   │   └── 英语/
│   └── K2/
├── processed/             # 预处理后
│   └── {paper_id}/
│       ├── processed.jpg  # 预处理图
│       └── cleaned.jpg    # 擦除图
├── mistakes/              # 错题截图
│   └── {mistake_id}/
│       ├── original.jpg   # 原图裁切
│       └── clean.jpg      # 擦除版裁切
└── exports/               # 导出的 PDF
    └── {export_id}.pdf
```

### 3.3 文件命名规则

- 原图: `data/originals/{child_id}/{subject}/{timestamp}_{uuid4_short}.jpg`
- timestamp 格式: `20260531_153022`
- uuid4_short: uuid4 前 8 位

---

## 四、模块接口定义

### 4.1 M1: 图像处理引擎

**位置**: `src/m1_image_engine/`  
**入口**: `src/m1_image_engine/engine.py`  
**依赖**: opencv-python, Pillow, numpy, pillow-heif  
**特性**: 纯函数式，无状态，不访问数据库

```python
# === 主接口 ===

from dataclasses import dataclass
from typing import Optional

@dataclass
class ProcessResult:
    """图像处理结果"""
    success: bool
    processed_path: Optional[str] = None  # 预处理后图片路径
    cleaned_path: Optional[str] = None    # 擦除后图片路径
    quality_score: float = 0.0            # 0.0-1.0, >=0.6 视为可打印
    warnings: list[str] = None            # 处理过程中的警告
    error: Optional[str] = None           # 失败时的错误信息

def process_paper(input_path: str, output_dir: str) -> ProcessResult:
    """
    处理单张试卷图片。
    
    Args:
        input_path: 原始图片的绝对路径
        output_dir: 输出目录的绝对路径（会在其中生成 processed.jpg 和 cleaned.jpg）
    
    Returns:
        ProcessResult 数据类
    
    处理流程:
        1. EXIF 方向修正
        2. 缩放到合理尺寸（长边不超过 3000px）
        3. 纸张检测 + 透视矫正
        4. 去阴影（CLAHE）
        5. 二值化增强
        6. 手写 mask 生成
        7. 区域填充（擦除）
        8. 质量评分
    
    不变量:
        - 不修改 input_path 指向的原图
        - output_dir 不存在时自动创建
        - 失败时 success=False, error 字段有描述
    """

def generate_mask(input_path: str, output_path: str) -> bool:
    """
    仅生成手写 mask（用于调试和人工修正场景）。
    
    Args:
        input_path: 预处理后的图片路径
        output_path: mask 图片输出路径（白色=手写区域，黑色=保留区域）
    
    Returns:
        是否成功
    """

def apply_mask(input_path: str, mask_path: str, output_path: str, method: str = 'white') -> bool:
    """
    根据 mask 擦除手写内容。
    
    Args:
        input_path: 预处理后的图片路径
        mask_path: mask 图片路径
        output_path: 擦除结果输出路径
        method: 'white'(白色填充) | 'inpaint'(图像修复)
    
    Returns:
        是否成功
    """
```

**CLI 入口** (用于独立测试):

```bash
# 处理单张图片
python -m src.m1_image_engine.cli process input.jpg output_dir/

# 仅生成 mask
python -m src.m1_image_engine.cli mask input.jpg mask.jpg

# 批量处理目录
python -m src.m1_image_engine.cli batch input_dir/ output_dir/
```

---

### 4.2 M2: 数据层

**位置**: `src/m2_data_layer/`  
**入口**: `src/m2_data_layer/db.py`  
**依赖**: 仅 Python 标准库 (sqlite3)  
**特性**: 所有数据库操作的唯一入口，其他模块不得直接操作 SQLite

```python
# === 主接口 ===

from dataclasses import dataclass
from typing import Optional

@dataclass
class Paper:
    id: int
    child_id: str
    subject: str
    paper_type: str
    title: Optional[str]
    original_path: str
    processed_path: Optional[str]
    cleaned_path: Optional[str]
    upload_time: str
    status: str
    quality_score: Optional[float]
    error_message: Optional[str]

@dataclass
class Mistake:
    id: int
    paper_id: int
    child_id: str
    subject: str
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    mistake_image_path: Optional[str]
    clean_mistake_image_path: Optional[str]
    note: Optional[str]
    error_type: Optional[str]
    status: str
    created_at: str
    reviewed_at: Optional[str]

class Database:
    def __init__(self, db_path: str = 'data/exam_paper.db'):
        """初始化数据库连接，自动建表"""
    
    # --- Paper CRUD ---
    def create_paper(self, child_id: str, subject: str, original_path: str,
                     paper_type: str = '其他', title: str = None) -> Optional[int]:
        """创建试卷记录，返回 paper_id"""
    
    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """获取单张试卷"""
    
    def update_paper_status(self, paper_id: int, status: str,
                           processed_path: str = None,
                           cleaned_path: str = None,
                           quality_score: float = None,
                           error_message: str = None) -> bool:
        """更新试卷处理状态"""
    
    def list_papers(self, child_id: str = None, subject: str = None,
                    status: str = None, limit: int = 50, offset: int = 0) -> list[Paper]:
        """查询试卷列表"""
    
    # --- Mistake CRUD ---
    def create_mistake(self, paper_id: int, child_id: str, subject: str,
                       crop_x: int, crop_y: int, crop_width: int, crop_height: int,
                       mistake_image_path: str = None,
                       clean_mistake_image_path: str = None,
                       note: str = None, error_type: str = None) -> Optional[int]:
        """创建错题记录，返回 mistake_id"""
    
    def get_mistake(self, mistake_id: int) -> Optional[Mistake]:
        """获取单个错题"""
    
    def update_mistake_status(self, mistake_id: int, status: str) -> bool:
        """更新错题状态"""
    
    def list_mistakes(self, child_id: str = None, subject: str = None,
                      status: str = None, paper_id: int = None,
                      limit: int = 100, offset: int = 0) -> list[Mistake]:
        """查询错题列表"""
    
    def update_mistake_paths(self, mistake_id: int,
                           mistake_image_path: str = None,
                           clean_mistake_image_path: str = None) -> bool:
        """更新错题图片路径（用于 create 后回填）"""

    def delete_mistake(self, mistake_id: int) -> bool:
        """删除错题"""
    
    def update_mistake_paths(self, mistake_id: int,
                           mistake_image_path: str = None,
                           clean_mistake_image_path: str = None) -> bool:

    # --- Export Log ---
    def create_export_log(self, child_id: str, mistake_ids: list[int],
                          pdf_path: str, subject: str = None) -> Optional[int]:
        """记录导出操作"""
    
    def list_export_logs(self, child_id: str = None, limit: int = 20) -> list[dict]:
        """查询导出历史"""
```

---

### 4.3 M3: Web 前端

**位置**: `src/m3_web_frontend/`  
**技术**: HTML + Alpine.js (CDN) + Canvas API  
**特性**: 零构建，所有文件由 M4 的 FastAPI 静态文件服务

**文件结构**:

```
src/m3_web_frontend/
├── index.html          # 主页（上传入口）
├── paper.html          # 试卷详情页（预览 + 框选）
├── mistakes.html       # 错题库列表页
├── export.html         # 导出页
├── static/
│   ├── app.js          # 主逻辑
│   ├── crop.js         # Canvas 框选逻辑
│   └── style.css       # 样式
└── components/         # 可复用 HTML 片段
```

**前端调用的 API 端点**（由 M4 提供）:

```
POST   /api/papers/upload          # 上传图片
GET    /api/papers                  # 试卷列表
GET    /api/papers/{id}             # 试卷详情
POST   /api/papers/{id}/process     # 触发处理
POST   /api/mistakes                # 创建错题（框选）
GET    /api/mistakes                # 错题列表
DELETE /api/mistakes/{id}           # 删除错题
PATCH  /api/mistakes/{id}           # 更新错题状态/备注
POST   /api/export/pdf              # 导出 PDF (body: child_id, mistake_ids, layout, title?)
GET    /api/export/history           # 导出历史
GET    /static/data/{path}          # 访问图片文件
```

---

### 4.4 M4: Web 后端

**位置**: `src/m4_web_backend/`  
**入口**: `src/m4_web_backend/app.py`  
**依赖**: fastapi, uvicorn, python-multipart  
**特性**: 胶水层，串联 M1+M2，提供 REST API

```python
# === API 路由定义 ===

# --- 试卷相关 ---
@app.post('/api/papers/upload')
async def upload_paper(file: UploadFile, child_id: str = Form(...), subject: str = Form(...),
                       paper_type: str = Form('其他'), title: str = Form(None)):
    """
    上传试卷图片。
    1. 验证文件类型（jpg/jpeg/png/heic）
    2. 保存原图到 data/originals/{child_id}/{subject}/
    3. 写入 DB (status='pending')
    4. 返回 paper_id
    
    注: child_id/subject/paper_type/title 为 Form 字段（multipart/form-data）
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

# --- 错题相关 ---
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

# --- 导出相关 ---
@app.post('/api/export/pdf')
async def export_pdf(child_id: str, mistake_ids: list[int],
                     layout: str = 'one_per_page', title: str = None):
    """
    导出错题 PDF。
    1. 从 DB 查询错题图片路径
    2. 调用 M5.export_pdf()
    3. 记录导出日志
    4. 返回 PDF 下载链接
    """
    # Response: {"pdf_url": "/static/data/exports/1.pdf", "export_id": 1}
    # title 可选，传入后会作为 PDF 首页标题

@app.get('/api/export/history')
async def export_history(child_id: str = None, limit: int = 20):
    # Response: {"exports": [...]}
```

**启动方式**:

```bash
cd /Users/limuxy/Projects/exam-paper-tool
python -m src.m4_web_backend.app
# 监听 0.0.0.0:8900
```

---

### 4.5 M5: PDF 导出

**位置**: `src/m5_pdf_export/`  
**入口**: `src/m5_pdf_export/exporter.py`  
**依赖**: fpdf2  
**特性**: 纯函数式，输入图片路径列表，输出 PDF 文件

```python
# === 主接口 ===

from dataclasses import dataclass

@dataclass
class ExportConfig:
    """导出配置"""
    layout: str = 'one_per_page'  # 'one_per_page' | 'two_per_page' | 'compact'
    page_size: str = 'A4'         # 'A4' | 'A3'
    margin_mm: int = 15           # 页边距
    spacing_mm: int = 20          # 题目间距（留答题空间）
    title: str = ''               # PDF 标题（如 "K1 数学错题 2026-05-31"）
    show_number: bool = True      # 是否显示题号

def export_pdf(image_paths: list[str], output_path: str,
               config: ExportConfig = None) -> bool:
    """
    将错题图片列表导出为 PDF。
    
    Args:
        image_paths: 错题图片的绝对路径列表（按顺序排列）
        output_path: PDF 输出的绝对路径
        config: 导出配置，None 时使用默认值
    
    Returns:
        是否成功
    
    行为:
        - 每张图片按比例缩放到页面宽度
        - layout='one_per_page': 每题一页，下方留空
        - layout='two_per_page': 每页两题
        - layout='compact': 尽量紧凑排列
        - 自动分页
        - 首页可选标题
    """
```

**CLI 入口**:

```bash
# 导出指定图片为 PDF
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf

# 指定布局
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf --layout two_per_page
```

---

## 五、模块依赖关系

```
M1 (图像引擎)  ←── 无依赖，独立开发
M2 (数据层)    ←── 无依赖，独立开发
M3 (前端)      ←── 依赖 M4 的 API 定义（可用 mock）
M4 (后端)      ←── 依赖 M1 + M2 的接口
M5 (PDF导出)   ←── 无依赖，独立开发
```

**并行开发策略**:

- **Phase 1**: M1 + M2 + M5 三路并行（零依赖）
- **Phase 2**: M3 并行开发（用 mock API）
- **Phase 3**: M4 集成（等 M1+M2 接口稳定）

---

## 六、错误处理约定

所有模块统一的错误处理模式:

```python
# M1/M5: 返回 dataclass，success=False 时查看 error 字段
result = process_paper(input_path, output_dir)
if not result.success:
    print(f"处理失败: {result.error}")

# M2: 操作失败返回 None 或 False，不抛异常
paper = db.get_paper(999)
if paper is None:
    # 不存在

# M4: HTTP 状态码 + JSON error body
# 400: 参数错误
# 404: 资源不存在
# 500: 内部错误
# Response: {"error": "描述信息"}
```

---

## 七、技术栈与依赖版本

```
# requirements.txt (最终版)

# M1: 图像处理
opencv-python>=4.8.0
Pillow>=10.0.0
numpy>=1.24.0
pillow-heif>=0.14.0

# M2: 数据层
# (仅标准库 sqlite3)

# M4: Web 后端
fastapi>=0.104.0
uvicorn>=0.24.0
python-multipart>=0.0.6

# M5: PDF 导出
fpdf2>=2.7.0
```

---

## 八、开发规范

### 8.1 代码规范

- Python 3.11+
- 类型注解必须写
- docstring 必须写（Google style）
- 每个模块必须有 `__init__.py` 导出主接口

### 8.2 测试规范

- 每个模块在 `tests/` 下有对应目录
- M1 测试: 用 `data/samples/` 下的真实图片
- M2 测试: 用内存 SQLite (`:memory:`)
- M5 测试: 用固定尺寸的测试图片
- 运行: `pytest tests/m1/` `pytest tests/m2/` etc.

### 8.3 隐私规范

- 代码和文档中只用 K1/K2，不出现真名
- `data/` 目录不进 git（.gitignore）
- 图片不上传云端

---

## 九、端口与服务

| 服务 | 端口 | 说明 |
|------|------|------|
| FastAPI (M4) | 8900 | Web 后端 + 静态文件 |

**启动命令**:

```bash
cd /Users/limuxy/Projects/exam-paper-tool
python -m src.m4_web_backend.app
# 浏览器打开 http://localhost:8900
# 手机同局域网访问 http://<mac-ip>:8900
```

---

## 十、变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-05-31 | v1.0-FINAL | 初始最终版 |
