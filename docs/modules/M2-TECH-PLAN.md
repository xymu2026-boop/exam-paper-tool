# M2 数据层技术实现计划

> **模块**: M2 (Data Layer)
> **对应文件**: `src/m2_data_layer/`
> **版本**: v1.0
> **日期**: 2026-05-31

---

## 1. 模块职责

M2 是试卷宝系统中**所有数据库操作的唯一入口**，封装 SQLite 的全部 SQL 细节，对外暴露 `Database` 类与 `Paper` / `Mistake` / `ExportLog` 数据类。

**关键约束**: M2 是数据库访问的**唯一通道**。其他模块（主要是 M4）只能通过 `from src.m2_data_layer import Database` 来读写数据，任何模块都**不允许**直接导入 `sqlite3` 或操作数据库文件。这一约束保证了 schema 变更时只需修改 M2 内部实现，调用方完全无感知。

---

## 2. 输入输出

### 2.1 初始化输入

`Database.__init__(db_path: str = 'data/exam_paper.db')` 接受一个数据库路径字符串：

- **生产环境**: 使用默认值 `'data/exam_paper.db'，数据库文件位于项目根目录的 `data/` 文件夹下
- **测试环境**: 传入 `':memory:'`，SQLite 在内存中创建临时数据库，测试结束后自动销毁，永不触碰磁盘
- **自定义路径**: 支持传入任意绝对或相对路径，父目录不存在时自动创建

### 2.2 CRUD 方法输入输出概览

| 方法 | 输入 | 输出 | 失败语义 |
|------|------|------|----------|
| `create_paper(...)` | child_id, subject, original_path, paper_type, title | `int` (paper_id) | `None` |
| `get_paper(paper_id)` | paper_id: int | `Paper` 实例 | `None` |
| `update_paper_status(...)` | paper_id, status, processed_path, cleaned_path, quality_score, error_message | `bool` | `False` |
| `list_papers(...)` | child_id, subject, status, limit, offset | `list[Paper]` | 空列表 |
| `create_mistake(...)` | paper_id, child_id, subject, crop_x, crop_y, crop_width, crop_height, image paths, note, error_type | `int` (mistake_id) | `None` |
| `get_mistake(mistake_id)` | mistake_id: int | `Mistake` 实例 | `None` |
| `update_mistake_status(...)` | mistake_id, status | `bool` | `False` |
| `list_mistakes(...)` | child_id, subject, status, paper_id, limit, offset | `list[Mistake]` | 空列表 |
| `delete_mistake(mistake_id)` | mistake_id: int | `bool` | `False` |
| `create_export_log(...)` | child_id, mistake_ids, pdf_path, subject | `int` (export_id) | `None` |
| `list_export_logs(...)` | child_id, limit | `list[dict]` | 空列表 |

### 2.3 输出数据类型

M2 返回三种 dataclass 实例（或包含它们的列表 / 字典）：

**Paper 结构**

- `id: int`
- `child_id: str`
- `subject: str`
- `paper_type: str`
- `title: Optional[str]`
- `original_path: str`
- `processed_path: Optional[str]`
- `cleaned_path: Optional[str]`
- `upload_time: str`
- `status: str`
- `quality_score: Optional[float]`
- `error_message: Optional[str]`

**Mistake 结构**

- `id: int`
- `paper_id: int`
- `child_id: str`
- `subject: str`
- `crop_x: int`
- `crop_y: int`
- `crop_width: int`
- `crop_height: int`
- `mistake_image_path: Optional[str]`
- `clean_mistake_image_path: Optional[str]`
- `note: Optional[str]`
- `error_type: Optional[str]`
- `status: str`
- `created_at: str`
- `reviewed_at: Optional[str]`

**ExportLog 结构（内部使用）**

- `id: int`
- `child_id: str`
- `subject: Optional[str]`
- `mistake_ids: list[int]`
- `pdf_path: str`
- `created_at: str`

### 2.4 数据库文件位置

生产数据库文件固定位于 `data/exam_paper.db`。`Database.__init__` 在连接前通过 `os.makedirs(os.path.dirname(db_path), exist_ok=True)` 确保 `data/` 目录存在。

---

## 3. 技术选型

### 3.1 sqlite3 (Python 标准库)

选择 `sqlite3` 作为数据库驱动的原因：

- **零外部依赖**: 项目整体依赖策略要求 M2 仅使用 Python 标准库，避免增加 requirements.txt 条目和安装复杂度
- **足够支撑当前规模**: 试卷宝面向家庭教育场景，数据量级为数百至数千条记录，SQLite 单机性能完全满足
- **单文件部署**: 整个数据库就是一个 `.db` 文件，备份、迁移、排查都极其简单

### 3.2 不使用 ORM

明确不引入 SQLAlchemy、Peewee 或其他 ORM：

- **复杂度不匹配**: ORM 的学习成本和抽象 overhead 对于仅有 3 张表、11 个 CRUD 方法的模块是过度设计
- **直接控制 SQL**: 手写 SQL 使得动态 WHERE 拼接、JSON 字段处理、PRAGMA 设置等行为完全透明可控
- **减少依赖**: 不引入额外包，降低维护面和版本冲突风险

### 3.3 WAL 模式

连接建立后立即执行 `PRAGMA journal_mode=WAL`。

WAL (Write-Ahead Logging) 将写操作追加到独立的 `.db-wal` 文件，而非直接修改主数据库文件。这带来的好处：

- **读操作不阻塞写操作**: 当 M4 的 FastAPI 多线程同时处理请求时，一个线程写入 export_log 不会阻塞另一个线程读取 paper 列表
- **并发性能提升**: 对于读多写少的试卷宝场景，WAL 显著降低锁竞争
- **崩溃恢复更可靠**: WAL 文件在异常退出后自动回放，数据完整性有保障

### 3.4 线程安全方案

SQLite 的默认连接在 `check_same_thread=True` 时禁止跨线程使用，但 FastAPI 会在线程池中分发请求，因此：

- 连接创建时显式传入 `check_same_thread=False`
- `Database` 类内部持有一个 `threading.Lock` 实例
- **所有写操作**（INSERT / UPDATE / DELETE）在进入 `cursor.execute()` 之前先 `acquire()` 该锁，执行完毕后 `release()`
- **读操作**（SELECT）不加锁，利用 WAL 模式的读不阻塞特性提升并发

### 3.5 Row Factory 选择

设置 `self.conn.row_factory = sqlite3.Row`。`sqlite3.Row` 既支持整数索引访问，也支持列名字符串索引访问（如 `row['child_id']`）。这使得查询结果到 dataclass 的映射代码清晰可读，且当 SQL 的 SELECT 列顺序变化时不会导致字段错位。

---

## 4. 核心算法与流程

### 4.1 数据库初始化流程

`Database.__init__` 按以下顺序执行：

1. **路径准备**: 若 `db_path` 不是 `':memory:'`，调用 `os.makedirs` 创建父目录
2. **建立连接**: `sqlite3.connect(db_path, check_same_thread=False)`
3. **设置 Row Factory**: `conn.row_factory = sqlite3.Row`
4. **启用 WAL 模式**: `PRAGMA journal_mode=WAL`
5. **启用外键约束**: `PRAGMA foreign_keys=ON`
6. **创建表**: 依次执行 `paper` / `mistake` / `export_log` 三张表的 `CREATE TABLE IF NOT EXISTS` 语句
7. **验证**: 可选地执行一次 `SELECT name FROM sqlite_master WHERE type='table'` 确认三张表存在

所有步骤封装在 `try/except` 中，任何一步失败都将关闭连接并抛出异常（初始化失败属于致命错误，不应静默处理）。

### 4.2 动态 WHERE 子句构造算法

`list_papers` 和 `list_mistakes` 支持多条件组合筛选（如 `child_id='K1' AND subject='数学' AND status='new'`）。构造算法如下：

```text
输入: child_id, subject, status, paper_id 等可选过滤参数
输出: (where_clause_string, params_list)

1. 初始化空列表 conditions = []，空列表 params = []
2. 对每个过滤参数:
   a. 若参数值不为 None:
      - conditions.append(f"{column_name} = ?")
      - params.append(参数值)
3. 若 conditions 非空:
   - where_clause = "WHERE " + " AND ".join(conditions)
   否则:
   - where_clause = ""
4. 拼接完整 SQL: "SELECT * FROM table {where_clause} ORDER BY id DESC LIMIT ? OFFSET ?"
5. params.extend([limit, offset])
6. 执行 cursor.execute(sql, params)
```

关键点：

- 条件列名使用硬编码字符串，**值**使用 `?` 占位符，彻底杜绝 SQL 注入
- `LIMIT` 和 `OFFSET` 同样走参数化，不拼接进 SQL 字符串
- 无过滤条件时直接执行全表查询（带分页）

### 4.3 Row 到 Dataclass 的映射算法

查询返回的 `sqlite3.Row` 通过集中式辅助函数转换为 dataclass，避免在每个方法内重复字段映射。

以 `Paper` 为例：

```text
输入: sqlite3.Row (来自 SELECT * FROM paper WHERE id = ?)
输出: Paper 实例

1. 将 Row 转为字典: row_dict = dict(row)
2. 检查必要字段是否存在（防御性编程）
3. 调用 Paper(**row_dict) 构造实例
4. 返回实例
```

由于 `sqlite3.Row` 的键名与 dataclass 字段名完全一致，这一步可以直接解包。若后续 schema 增加字段，只需同步更新 dataclass 定义，映射函数无需改动。

对于 `ExportLog`，在映射前需额外处理 `mistake_ids` 字段：

1. 从 Row 中取出 `mistake_ids` 字符串值
2. 执行 `json.loads(value)` 得到 `list[int]`
3. 将解析后的列表放入字典，再构造 `ExportLog`

### 4.4 JSON 序列化与反序列化

`export_log.mistake_ids` 在数据库中以 `TEXT` 存储，格式为 JSON 数组字符串（如 `'[1, 3, 7]'`）。

**写入流程**（`create_export_log`）:

1. 接收 `mistake_ids: list[int]`
2. 调用 `json.dumps(mistake_ids)` 得到 JSON 字符串
3. 将字符串作为参数执行 INSERT

**读取流程**（`list_export_logs`）:

1. 从数据库查询 `mistake_ids` 列，得到字符串
2. 调用 `json.loads(row['mistake_ids'])` 还原为 `list[int]`
3. 最终返回的 `dict` 中 `mistake_ids` 已是 Python 列表类型

错误处理：若 `json.loads` 抛出 `JSONDecodeError`，说明数据已损坏，该条记录跳过或返回空列表，不中断整个查询。

### 4.5 错误处理决策树

M2 承诺操作失败时返回 `None` 或 `False`，绝不向上层抛异常。内部决策树如下：

```text
开始执行数据库操作
│
├─ 应用层参数校验失败？
│   ├─ child_id 不在 ('K1', 'K2') → 返回 None/False
│   ├─ subject 不在合法集合 → 返回 None/False
│   ├─ status 不在合法集合 → 返回 None/False
│   ├─ error_type 不在合法集合 → 返回 None/False
│   └─ paper_type 不在合法集合 → 返回 None/False
│
├─ 进入 SQL 执行
│   ├─ 捕获 sqlite3.IntegrityError
│   │   ├─ CHECK 约束违反 → 返回 None/False
│   │   └─ FOREIGN KEY 约束违反 → 返回 None/False
│   ├─ 捕获 sqlite3.OperationalError
│   │   └─ 数据库锁定/只读 → 返回 None/False
│   └─ 其他 sqlite3.Error → 返回 None/False
│
├─ 执行成功
│   ├─ create_* 方法 → 返回 cursor.lastrowid (int)
│   ├─ update_* / delete 方法 → 返回 cursor.rowcount > 0 (bool)
│   ├─ get_* 方法 → 返回 dataclass 实例或 None
│   └─ list_* 方法 → 返回 list（可能为空）
```

---

## 5. 接口设计

### 5.1 Database 类完整方法签名

以下签名与 `INTERFACE-CONTRACT.md` 第 4.2 节**完全一致**，不得更改参数名、顺序、默认值或返回类型。

```python
class Database:
    def __init__(self, db_path: str = 'data/exam_paper.db') -> None:
        """初始化数据库连接，自动建表。"""

    # --- Paper CRUD ---
    def create_paper(self, child_id: str, subject: str, original_path: str,
                     paper_type: str = '其他', title: str = None) -> Optional[int]:
        """创建试卷记录，返回 paper_id；失败返回 None。"""

    def get_paper(self, paper_id: int) -> Optional[Paper]:
        """获取单张试卷；不存在返回 None。"""

    def update_paper_status(self, paper_id: int, status: str,
                            processed_path: str = None,
                            cleaned_path: str = None,
                            quality_score: float = None,
                            error_message: str = None) -> bool:
        """更新试卷处理状态；成功返回 True，失败返回 False。"""

    def list_papers(self, child_id: str = None, subject: str = None,
                    status: str = None, limit: int = 50, offset: int = 0) -> list[Paper]:
        """查询试卷列表，多条件可组合；无结果返回空列表。"""

    # --- Mistake CRUD ---
    def create_mistake(self, paper_id: int, child_id: str, subject: str,
                       crop_x: int, crop_y: int, crop_width: int, crop_height: int,
                       mistake_image_path: str = None,
                       clean_mistake_image_path: str = None,
                       note: str = None, error_type: str = None) -> Optional[int]:
        """创建错题记录，返回 mistake_id；失败返回 None。"""

    def get_mistake(self, mistake_id: int) -> Optional[Mistake]:
        """获取单个错题；不存在返回 None。"""

    def update_mistake_status(self, mistake_id: int, status: str) -> bool:
        """更新错题状态；成功返回 True，失败返回 False。"""

    def list_mistakes(self, child_id: str = None, subject: str = None,
                      status: str = None, paper_id: int = None,
                      limit: int = 100, offset: int = 0) -> list[Mistake]:
        """查询错题列表，多条件可组合；无结果返回空列表。"""

    def delete_mistake(self, mistake_id: int) -> bool:
        """删除错题；成功返回 True，失败返回 False。"""

    def update_mistake_paths(self, mistake_id: int,
                           mistake_image_path: str = None,
                           clean_mistake_image_path: str = None) -> bool:
        """更新错题图片路径（用于 create 后回填）；成功返回 True，失败返回 False。"""

    # --- Export Log ---
    def create_export_log(self, child_id: str, mistake_ids: list[int],
                          pdf_path: str, subject: str = None) -> Optional[int]:
        """记录导出操作，mistake_ids 内部做 json.dumps；返回 export_id 或 None。"""

    def list_export_logs(self, child_id: str = None, limit: int = 20) -> list[dict]:
        """查询导出历史，返回 dict 列表，mistake_ids 字段已是 list[int]。"""

    def close(self) -> None:
        """关闭数据库连接，释放资源。"""
```

### 5.2 参数与返回值详细说明

| 方法 | 关键参数说明 | 返回值说明 |
|------|-------------|-----------|
| `create_paper` | `original_path` 为必填原图路径；`paper_type` 默认 `'其他'`；`title` 可为 None | 成功时返回自增 `paper_id`（正整数）；任何校验失败或数据库错误返回 `None` |
| `get_paper` | `paper_id` 为正整数 | 存在返回 `Paper` 实例；不存在返回 `None` |
| `update_paper_status` | 除 `paper_id` 和 `status` 外，其余参数可选；传入 None 表示不更新该字段 | 至少影响一行返回 `True`；`paper_id` 不存在或参数非法返回 `False` |
| `list_papers` | 所有过滤参数可选；`limit` 默认 50，`offset` 默认 0 | 返回 `Paper` 列表；无任何记录返回 `[]` |
| `create_mistake` | `crop_*` 为像素坐标；`error_type` 可为 None | 成功返回 `mistake_id`；`paper_id` 不存在（外键失败）或参数非法返回 `None` |
| `get_mistake` | `mistake_id` 为正整数 | 存在返回 `Mistake`；不存在返回 `None` |
| `update_mistake_status` | `status` 必填 | 成功返回 `True`；失败返回 `False` |
| `list_mistakes` | 支持按 `paper_id` 筛选某试卷下的全部错题 | 返回 `Mistake` 列表，默认 limit=100 |
| `delete_mistake` | 物理删除，不可恢复 | 删除成功返回 `True`；`mistake_id` 不存在也返回 `False` |
| `create_export_log` | `mistake_ids` 为 Python 列表，内部自动 JSON 序列化 | 成功返回 `export_id`；失败返回 `None` |
| `list_export_logs` | `child_id` 可选；`limit` 默认 20 | 返回 `list[dict]`，每个 dict 包含导出记录全部字段，其中 `mistake_ids` 为 `list[int]` |

### 5.3 数据验证规则

所有写操作在构造 SQL 之前先执行应用层校验，非法输入直接短路返回 `None` 或 `False`，不进入数据库层。

| 字段 | 合法值集合 | 校验位置 |
|------|-----------|----------|
| `child_id` | `'K1'`, `'K2'` | `create_paper`, `create_mistake`, `create_export_log`, `list_papers`, `list_mistakes`, `list_export_logs` |
| `subject` | `'数学'`, `'语文'`, `'英语'`, `'科学'`, `'其他'` | `create_paper`, `create_mistake`, `create_export_log`, `list_papers`, `list_mistakes`, `list_export_logs` |
| `paper.status` | `'pending'`, `'processing'`, `'processed'`, `'failed'` | `create_paper`（默认 `pending` 合法）, `update_paper_status`, `list_papers` |
| `mistake.status` | `'new'`, `'printed'`, `'practiced'`, `'passed'`, `'retry'` | `create_mistake`（默认 `new` 合法）, `update_mistake_status`, `list_mistakes` |
| `error_type` | `None`, `'粗心'`, `'概念不清'`, `'计算错误'`, `'不会做'`, `'其他'` | `create_mistake`, `list_mistakes` |
| `paper_type` | `'作业'`, `'单元卷'`, `'考试卷'`, `'练习册'`, `'其他'` | `create_paper`, `list_papers` |

校验实现方式：每个方法开头使用独立私有辅助函数（如 `_validate_child_id(value) -> bool`），返回布尔值表示是否通过。未通过时方法立即返回 `None`（创建/查询单条）或 `False`（更新/删除）。

### 5.4 Database 类生命周期

```text
1. 实例化: db = Database('data/exam_paper.db')
   └─ 连接建立、建表、WAL/外键设置完成

2. 使用阶段: 反复调用 db.create_paper(...) / db.list_mistakes(...) 等
   └─ 读操作直接执行，写操作内部加锁后执行

3. 关闭: db.close()
   └─ conn.close()，释放文件句柄
```

**生产环境**: FastAPI 进程启动时创建 `Database` 实例作为全局依赖，进程运行期间持续复用同一连接；进程退出时操作系统自动回收句柄，不强制要求显式 `close()`。

**测试环境**: 每个测试函数通过 pytest fixture 创建 `Database(':memory:')` 实例，测试结束后显式调用 `close()`，确保内存资源及时释放，避免测试间干扰。

---

## 6. 数据结构

### 6.1 Paper Dataclass

```python
@dataclass
class Paper:
    id: int                           # 自增主键
    child_id: str                     # 'K1' 或 'K2'
    subject: str                      # 学科名称
    paper_type: str                   # 试卷类型
    title: Optional[str]              # 用户自定义标题，可为 None
    original_path: str                # 原图文件绝对路径
    processed_path: Optional[str]     # 预处理后图片路径
    cleaned_path: Optional[str]      # 擦除后图片路径
    upload_time: str                  # 上传时间，SQLite localtime 格式
    status: str                       # 处理状态
    quality_score: Optional[float]   # 质量评分 0.0-1.0
    error_message: Optional[str]     # 处理失败时的错误描述
```

### 6.2 Mistake Dataclass

```python
@dataclass
class Mistake:
    id: int                           # 自增主键
    paper_id: int                     # 关联试卷 ID（外键）
    child_id: str                     # 所属孩子
    subject: str                      # 所属学科
    crop_x: int                       # 裁切区域左上角 x 坐标（像素）
    crop_y: int                       # 裁切区域左上角 y 坐标（像素）
    crop_width: int                   # 裁切区域宽度（像素）
    crop_height: int                  # 裁切区域高度（像素）
    mistake_image_path: Optional[str]  # 裁切后原图路径
    clean_mistake_image_path: Optional[str]  # 裁切后擦除图路径
    note: Optional[str]               # 用户备注
    error_type: Optional[str]         # 错误归类
    status: str                       # 错题状态
    created_at: str                   # 创建时间
    reviewed_at: Optional[str]       # 复习/通关时间
```

### 6.3 ExportLog Dataclass

```python
@dataclass
class ExportLog:
    id: int                           # 自增主键
    child_id: str                     # 导出对象
    subject: Optional[str]            # 学科过滤条件，全学科导出时为 None
    mistake_ids: list[int]            # 本次导出包含的错题 ID 列表
    pdf_path: str                     # 生成 PDF 的绝对路径
    created_at: str                   # 导出时间
```

### 6.4 内部辅助结构

**查询构建器（QueryBuilder）**

虽然模块规模小，但 `list_papers` 与 `list_mistakes` 的动态 WHERE 逻辑可以提取为内部辅助函数，避免重复代码：

```python
# 伪结构示意，实际为函数而非类
_BuildWhereResult = tuple[str, list]  # (where_clause_str, params_list)
```

辅助函数签名：

```python
def _build_where(conditions: dict[str, Any]) -> _BuildWhereResult:
    """
    输入: {'child_id': 'K1', 'status': 'new'}
    输出: ('WHERE child_id = ? AND status = ?', ['K1', 'new'])
    """
```

**Row 映射辅助函数**

```python
def _row_to_paper(row: sqlite3.Row) -> Paper:
    """将查询行转换为 Paper dataclass。"""

def _row_to_mistake(row: sqlite3.Row) -> Mistake:
    """将查询行转换为 Mistake dataclass。"""

def _row_to_export_log(row: sqlite3.Row) -> ExportLog:
    """将查询行转换为 ExportLog dataclass，内部处理 JSON 解析。"""
```

### 6.5 JSON 编码规范

`export_log` 表的 `mistake_ids` 列类型为 `TEXT`，存储规则如下：

- **写入前**: `list[int]` → `json.dumps([1, 3, 7])` → `'[1, 3, 7]'`
- **读取后**: `'[1, 3, 7]'` → `json.loads(...)` → `[1, 3, 7]`
- **空列表**: `json.dumps([])` → `'[]'`
- **排序**: 写入前按升序排序（`sorted(mistake_ids)`），保证存储一致性，便于对比和调试

`json.dumps` 和 `json.loads` 使用默认参数即可，不需要自定义编码器，因为 `mistake_ids` 的元素均为整数。

---

## 7. 测试策略

### 7.1 测试环境原则

- **全部使用内存数据库**: 每个测试通过 `Database(':memory:')` 创建独立实例，测试运行期间不读写磁盘，测试结束后内存自动释放
- **每个测试独立**: pytest fixture 使用默认 `scope='function'`，确保每个测试函数获得全新的空数据库，杜绝测试间数据污染
- **显式关闭连接**: fixture 的 yield 后调用 `db.close()`，避免连接泄漏

### 7.2 CRUD 全覆盖

对三张表的全部操作编写正向测试用例：

| 测试类别 | 覆盖点 |
|----------|--------|
| Paper 创建 | 合法参数创建成功，返回正整数 ID |
| Paper 读取 | 创建后通过 `get_paper` 读取，字段值完全匹配 |
| Paper 更新 | `update_paper_status` 更新各字段后再次读取确认 |
| Paper 列表 | `list_papers` 返回正确列表，支持分页 |
| Mistake 创建 | 关联已存在 paper_id，创建成功 |
| Mistake 读取/更新/删除 | 正常生命周期验证 |
| Mistake 列表 | 多条件组合筛选验证 |
| ExportLog 创建/列表 | JSON 序列化往返验证 |

### 7.3 数据校验覆盖

为所有应用层校验规则编写负向测试，确保非法输入返回 `None` 或 `False` 且不抛异常：

- `child_id='K3'` → `create_paper` 返回 `None`
- `subject='物理'` → `create_paper` 返回 `None`
- `status='done'` → `update_paper_status` 返回 `False`
- `paper_type='期中卷'` → `create_paper` 返回 `None`
- `error_type='笔误'` → `create_mistake` 返回 `None`
- `mistake.status='unknown'` → `update_mistake_status` 返回 `False`

### 7.4 边界与异常场景

| 场景 | 预期行为 |
|------|----------|
| 空表查询 | `list_papers()` / `list_mistakes()` 返回 `[]` |
| 不存在的 ID | `get_paper(999)` 返回 `None`；`update_paper_status(999, ...)` 返回 `False`；`delete_mistake(999)` 返回 `False` |
| 分页越界 | `offset` 大于总记录数时返回 `[]`，不报错 |
| 外键不存在 | `create_mistake(paper_id=999, ...)` 返回 `None`（SQLite 外键检查开启后抛出 IntegrityError，内部捕获转 None） |
| 多条件组合 | 同时传入 `child_id='K1'`, `subject='数学'`, `status='new'`，结果严格满足全部条件 |
| JSON 往返 | `create_export_log` 写入 `[5, 2, 8]`，`list_export_logs` 返回相同列表（验证排序后应为 `[2, 5, 8]`） |
| 重复删除 | 对同一 `mistake_id` 连续调用两次 `delete_mistake`，第一次返回 `True`，第二次返回 `False` |

### 7.5 覆盖率目标

- 行覆盖率目标: **> 90%**
- 分支覆盖率目标: **> 85%**
- 运行命令:

```bash
pytest tests/m2/ -v
pytest tests/m2/ --cov=src.m2_data_layer --cov-report=term-missing
```

### 7.6 Pytest Fixture 设计

```python
import pytest
from src.m2_data_layer import Database

@pytest.fixture
def db():
    """为每个测试函数提供全新的内存数据库实例。"""
    database = Database(':memory:')
    yield database
    database.close()
```

所有测试函数接收 `db` fixture 作为参数，直接使用而无需重复实例化逻辑。

---

## 8. 风险与对策

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| **并发写入冲突** (FastAPI 多线程同时操作数据库) | 中 | 高 | 启用 WAL 模式减少锁竞争；`Database` 内部对写操作加 `threading.Lock`；读操作不加锁，利用 WAL 的读不阻塞特性 |
| **Schema 迁移** (未来新增字段或表结构变更) | 中 | 中 | 所有建表语句使用 `IF NOT EXISTS`；新增字段时采用 `ALTER TABLE ADD COLUMN IF NOT EXISTS` 策略；版本化的 `migrations.py` 文件集中管理 schema 变更脚本 |
| **大数据集性能下降** (记录增长至数千条时 list 查询变慢) | 低 | 中 | 所有 `list_*` 方法强制分页（limit/offset）；在 `paper` 和 `mistake` 的常用筛选列（child_id, subject, status）上预先创建索引：`CREATE INDEX IF NOT EXISTS idx_paper_child ON paper(child_id)` 等 |
| **SQL 注入** (动态 WHERE 拼接时误将用户输入嵌入 SQL 字符串) | 低 | 高 | 严格区分"条件列名"（硬编码）与"条件值"（`?` 占位符）；所有动态值通过参数化查询传入；代码审查时重点检查 list 方法的 SQL 拼接逻辑 |
| **JSON 字段损坏** (export_log.mistake_ids 被外部直接修改为非法 JSON) | 极低 | 低 | M2 作为唯一数据入口，外部无法直接修改数据库；读取时 `json.loads` 包裹 try/except，解析失败时返回空列表并记录警告，不影响其他记录 |

---

> **下一动作**: 本计划通过评审后，进入 `src/m2_data_layer/` 的代码实现阶段，按此计划中的接口签名、数据结构、算法流程和测试策略进行开发。
