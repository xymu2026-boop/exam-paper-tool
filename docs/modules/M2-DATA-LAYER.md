# M2: 数据层 — 开发任务卡

| 项目 | 内容 |
|------|------|
| 模块编号 | M2 |
| 状态 | 待开发 |
| 可并行 | ✅ |
| 依赖 | 无 |

---

## 模块定位

SQLite 数据库操作的**唯一入口**。其他模块（主要是 M4）通过 `import` 此模块来读写数据，**不允许**绕过本模块直接操作 SQLite。

- 不依赖任何其他模块（仅使用 Python 标准库 `sqlite3`）
- 对外暴露 `Database` 类 + `Paper` / `Mistake` 数据类
- 隐藏所有 SQL 细节，调用方不感知 schema 变化

---

## 前置阅读

- `docs/INTERFACE-CONTRACT.md` **第三节**（共享数据模型 / Schema / 文件存储约定）
- `docs/INTERFACE-CONTRACT.md` **第四节 4.2**（M2 数据层接口定义）

读完上述章节再开始编码。所有方法签名、字段命名必须严格匹配契约。

---

## 目录结构

```
src/m2_data_layer/
├── __init__.py        # 导出 Database, Paper, Mistake
├── db.py              # Database 类主实现
├── models.py          # Paper, Mistake, ExportLog dataclass
├── migrations.py      # 建表和迁移
└── utils.py           # 辅助函数（Row → dataclass、JSON 序列化等）
```

`tests/m2/` 目录单独存放测试，不混入 `src/`。

---

## 核心接口

### 数据类（models.py）

```python
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

@dataclass
class ExportLog:
    id: int
    child_id: str
    subject: Optional[str]
    mistake_ids: list[int]   # 已从 JSON 解析为 list
    pdf_path: str
    created_at: str
```

### Database 类（db.py）

```python
class Database:
    def __init__(self, db_path: str = 'data/exam_paper.db'):
        """初始化数据库连接，自动建表"""

    # --- Paper CRUD ---
    def create_paper(self, child_id: str, subject: str, original_path: str,
                     paper_type: str = '其他', title: str = None) -> int:
        """创建试卷记录，返回 paper_id；失败返回 None"""

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """获取单张试卷；不存在返回 None"""

    def update_paper_status(self, paper_id: int, status: str,
                            processed_path: str = None,
                            cleaned_path: str = None,
                            quality_score: float = None,
                            error_message: str = None) -> bool:
        """更新试卷处理状态；成功返回 True"""

    def list_papers(self, child_id: str = None, subject: str = None,
                    status: str = None, limit: int = 50, offset: int = 0) -> list[Paper]:
        """查询试卷列表，多条件可组合"""

    # --- Mistake CRUD ---
    def create_mistake(self, paper_id: int, child_id: str, subject: str,
                       crop_x: int, crop_y: int, crop_width: int, crop_height: int,
                       mistake_image_path: str = None,
                       clean_mistake_image_path: str = None,
                       note: str = None, error_type: str = None) -> int:
        """创建错题记录，返回 mistake_id；失败返回 None"""

    def get_mistake(self, mistake_id: int) -> Optional[Mistake]:
        """获取单个错题"""

    def update_mistake_status(self, mistake_id: int, status: str) -> bool:
        """更新错题状态"""

    def list_mistakes(self, child_id: str = None, subject: str = None,
                      status: str = None, paper_id: int = None,
                      limit: int = 100, offset: int = 0) -> list[Mistake]:
        """查询错题列表，多条件可组合"""

    def delete_mistake(self, mistake_id: int) -> bool:
        """删除错题"""

    # --- Export Log ---
    def create_export_log(self, child_id: str, mistake_ids: list[int],
                          pdf_path: str, subject: str = None) -> int:
        """记录导出操作，mistake_ids 内部 json.dumps"""

    def list_export_logs(self, child_id: str = None, limit: int = 20) -> list[dict]:
        """查询导出历史，mistake_ids 字段返回时已 json.loads 为 list"""
```

> 字段名、参数名、默认值、返回类型必须与契约文档第 4.2 节**完全一致**，不要私自改名。

---

## 实现要求

### 数据库初始化

- `Database.__init__()` 时自动建表（`CREATE TABLE IF NOT EXISTS`），不要把建表放在外部脚本
- 支持传入自定义 `db_path`（测试用 `:memory:`，生产用默认 `data/exam_paper.db`）
- 父目录不存在时自动创建（`os.makedirs(..., exist_ok=True)`）
- 启用 WAL 模式提高并发性能：`PRAGMA journal_mode=WAL`
- 开启外键约束：`PRAGMA foreign_keys=ON`
- `row_factory = sqlite3.Row`，方便按列名取值

### CRUD 实现

- 所有 SQL 必须使用**参数化查询**（`?` 占位符），禁止字符串拼接，防注入
- `list_*` 方法支持分页（`limit` + `offset`），默认值见接口签名
- `list_*` 方法支持多条件**组合筛选**（动态拼接 `WHERE` 子句，但参数仍走占位符）
- 操作失败（如违反 CHECK 约束、外键不存在）返回 `None`（create/get）或 `False`（update/delete），**不抛异常**给上层
- `create_*` 方法返回新记录的自增 ID（`cursor.lastrowid`）
- `update_*` 方法通过 `cursor.rowcount > 0` 判断是否真正影响了行

### 数据验证（在写库前主动校验）

- `child_id` 只能是 `'K1'` 或 `'K2'`
- `subject` 只能是 `'数学' | '语文' | '英语' | '科学' | '其他'`
- `paper.status` 只能是 `'pending' | 'processing' | 'processed' | 'failed'`
- `mistake.status` 只能是 `'new' | 'printed' | 'practiced' | 'passed' | 'retry'`
- `mistake.error_type` 可为 `None`，否则必须是 `'粗心' | '概念不清' | '计算错误' | '不会做' | '其他'`
- `paper.paper_type` 只能是 `'作业' | '单元卷' | '考试卷' | '练习册' | '其他'`
- 验证失败立即返回 `None` / `False`，不进入 SQL 层

> 虽然 SQLite CHECK 约束会兜底，但应用层先校验可以给出更清晰的失败语义，且对 `:memory:` 测试更友好。

---

## 测试要求

- 测试目录：`tests/m2/`
- 全部使用 `Database(':memory:')`，**不写磁盘**
- 每个测试独立创建 `Database` 实例（pytest fixture 推荐 `scope='function'`）
- 必须覆盖：
  - 所有 CRUD 方法的正常路径
  - 边界情况：空表查询、不存在的 ID、重复创建、分页越界
  - 数据验证：非法 `child_id`、`subject`、`status` 应返回 `None`/`False`
  - 多条件组合筛选（如 `child_id='K1' AND subject='数学' AND status='new'`）
  - `export_log.mistake_ids` 的 JSON 序列化/反序列化往返
- 测试命令：

```bash
pytest tests/m2/ -v
pytest tests/m2/ --cov=src.m2_data_layer --cov-report=term-missing
```

---

## 验收标准

- [ ] 所有 CRUD 方法签名与 `INTERFACE-CONTRACT.md` 4.2 节完全一致
- [ ] 所有 CRUD 方法行为正确（含分页、多条件筛选）
- [ ] 数据验证拦截非法输入，返回 `None`/`False` 而不抛异常
- [ ] 测试覆盖率 > 90%
- [ ] 不依赖任何其他模块（`src/m2_data_layer/` 内只 import 标准库）
- [ ] `from src.m2_data_layer import Database, Paper, Mistake` 可直接被 M4 使用
- [ ] `pytest tests/m2/ -v` 全部通过

---

## 技术要点

- **Row → dataclass 映射**：在 `utils.py` 写一个 `row_to_paper(row) -> Paper` 辅助函数，集中处理字段映射，避免在每个 query 方法里重复
- **datetime 一致性**：所有时间字段用 SQLite 的 `datetime('now', 'localtime')` 默认值生成，应用层不要传 `datetime.now()`，避免时区漂移
- **JSON 字段**：`export_log.mistake_ids` 在 DB 中是 TEXT，写入用 `json.dumps(ids)`，读出用 `json.loads(text)`；`list_export_logs` 返回 dict 时 `mistake_ids` 应已是 `list[int]`
- **线程安全**：连接创建时传 `check_same_thread=False`，配合 FastAPI 多线程；如果担心并发写，可在 `Database` 内加 `threading.Lock` 包裹写操作
- **资源管理**：`Database` 提供 `close()` 方法；测试时显式 close，生产环境进程退出时自动释放即可
- **避免常见坑**：
  - `INSERT` 后取 ID 用 `cursor.lastrowid`（不是 `SELECT last_insert_rowid()`）
  - 动态 `WHERE` 子句用列表收集条件再 `' AND '.join(...)`，参数同步收集到 list，最后一次性 execute
  - `CHECK` 约束失败会抛 `sqlite3.IntegrityError`，需在方法里 `try/except` 转为 `None`/`False`
