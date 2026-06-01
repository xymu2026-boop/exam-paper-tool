# TextIn 实验模块技术实施方案

> 版本: v1.0 | 日期: 2026-06-01 | 基于: Claude 扩展_TextIn接口参数与实验矩阵方案.md
> 状态: 待青山审阅 → 待 OpenCode 执行

---

## 1. 当前项目结构检查结果

### 1.1 可复用的

| 资产 | 位置 | 复用方式 |
|------|------|---------|
| debug.html | `src/m3_web_frontend/debug.html` | 第一轮不集成，第二轮再加"TextIn Preset" Tab |
| M4 路由体系 | `src/m4_web_backend/routes/` | 第一轮不加路由，experiment.py 纯 CLI 运行 |
| data 目录惯例 | `data/input/`, `data/output_cleaned/` | 参照建 `data/api_eval/textin/input/` + `output/` |
| M1 现有结构 | `src/m1_image_engine/` | 在 `src/m1_image_engine/providers/textin/` 下新建，不动现有文件 |

### 1.2 暂时冻结的

| 代码 | 位置 | 冻结原因 |
|------|------|---------|
| mask.py / eraser.py / preprocess.py | `src/m1_image_engine/` | OpenCV 管线继续作为 fallback，不嵌入 TextIn 逻辑 |
| quality.py | `src/m1_image_engine/` | 质量评分算法不改，TextIn 评测用肉眼 |
| M4 routes | `src/m4_web_backend/routes/` | 不新增 TextIn API 端点 |
| paper.html | `src/m3_web_frontend/` | 主调试页不改，TextIn 对比用独立的 compare.html |

### 1.3 缺失的（本次新建）

| 资产 | 位置 | 说明 |
|------|------|------|
| data/api_eval/ | `data/api_eval/textin/` | 实验数据根目录 |
| .env / .env.example | 项目根目录 | API key 管理 |
| src/m1_image_engine/providers/ | `src/m1_image_engine/providers/textin/` | 新增 provider 包 |

---

## 2. 本次实验模块目标

**一句话**: 用 TextIn API 的 4 个 preset 跑 4 张真实试卷样本，产出一份对比页，回答 "TextIn 值不值得继续投入"。

**只做**:
- TextIn 单供应商
- A 线 (直接擦除) + B 线 (先增强再擦除) 两条实验线
- 4 个 preset: A1_default, A2_no_sharpen, B1_geom_only, B2_deshadow
- 4 张典型样本图
- 静态 compare.html 对比页

**不做**:
- 不接有道、百度、腾讯
- 不修改正式业务流程 (M1 engine/eraser/mask)
- 不接入 paper.html 主调试页
- 不写单元测试 (原型实验阶段)
- 不做账号系统、错题库、PDF 导出

---

## 3. 代码结构设计

```
src/m1_image_engine/providers/textin/
├── __init__.py          # 空文件，标记为 Python 包
├── client.py            # TextIn API 封装
├── presets.py           # 4 个 preset 配置
├── experiment.py        # 主入口 CLI 脚本
└── README.md            # 运行说明 + 参数速查 + 验收标准
```

### 3.1 client.py 职责

- 封装 `TextInClient` 类
- 提供 `handwritten_erase(image_bytes, **kwargs)` → dict
- 提供 `crop_enhance_image(image_bytes, **kwargs)` → dict
- 从环境变量读取 `TEXTIN_APP_ID` / `TEXTIN_SECRET_CODE`
- 所有参数 keyword-only (参数签名里的 `*`)
- 失败不 raise，返回 `{ok: False, error: "..."}`
- 请求体走二进制流 (`Content-Type: application/octet-stream`)
- 超时 60s，限流 40306 不重试
- 返回 dict 必须包含 `response_json` 全量原始响应

### 3.2 presets.py 职责

- 定义 `PRESETS: list[dict]` — 4 个 preset 配置
- 每个 preset 包含: name / pipeline / description / enhance_params(可选) / erase_params
- description 写 "想回答的问题"，不写参数罗列
- 第二轮要加 preset 直接在列表末尾追加

### 3.3 experiment.py 职责

- CLI 入口: `python -m src.m1_image_engine.providers.textin.experiment`
- 加载 .env (python-dotenv)，验证 API key 非空
- 遍历 `data/api_eval/textin/input/*.jpg`
- 对每个样本: 复制 original.jpg → 4 个 preset 串行跑 → 保存结果
- A 线: 直接调 handwritten_erase
- B 线: 先调 crop_enhance_image (保存 enhanced.jpg 中间产物) → 再调 handwritten_erase
- 任何 preset 失败不中断其他 preset
- 写 meta.json (含 stage_failed 字段)
- 最后生成 `data/api_eval/textin/comparison/index.html`

### 3.4 README.md 内容

- 运行命令
- Preset 速查表 (4 个 preset 的关键参数对比)
- 输入样本要求 (放什么图到 input/)
- 输出说明 (每个样本产出哪些文件)
- 验收标准 (6 条)
- 第一轮要回答的 5 个核心问题

### 3.5 新增依赖

```
python-dotenv  # .env 加载
requests       # HTTP 客户端
Pillow         # 图片尺寸读取 (已有)
```

### 3.6 .env.example 内容

```bash
TEXTIN_APP_ID=
TEXTIN_SECRET_CODE=
```

`.env` 加入 `.gitignore`，`.env.example` 提交到 git 作为模板。

---

## 4. Preset 设计

### 4.1 A1_default — 直接擦除，默认参数

| 字段 | 值 |
|------|-----|
| name | `A1_default` |
| pipeline | `direct_erase` |
| description | 直接擦除，全部默认参数（含官方默认 binarization=1 锐化）。回答：开箱即用效果如何。 |
| erase_params.crop | 1 |
| erase_params.doc_direction | 0 |
| erase_params.dewarp | 1 |
| erase_params.binarization | 1 |
| erase_params.image_type | 1 |
| 输出文件 | `A1_default.jpg` |

### 4.2 A2_no_sharpen — 直接擦除，关闭锐化

| 字段 | 值 |
|------|-----|
| name | `A2_no_sharpen` |
| pipeline | `direct_erase` |
| description | 直接擦除，关闭官方默认锐化（binarization=0）。回答：关锐化能否减少铅笔/红笔残影放大。 |
| erase_params.crop | 1 |
| erase_params.doc_direction | 0 |
| erase_params.dewarp | 1 |
| erase_params.binarization | **0** |
| erase_params.image_type | 1 |
| 输出文件 | `A2_no_sharpen.jpg` |

### 4.3 B1_geom_only — 先切边矫正，再擦除

| 字段 | 值 |
|------|-----|
| name | `B1_geom_only` |
| pipeline | `enhance_then_erase` |
| description | 前置只做切边+矫正不增强(enhance_mode=-1)，后置纯擦除。回答：前置专业切边是否优于 A 线自带切边。 |
| enhance_params.enhance_mode | -1 |
| enhance_params.crop_image | 1 |
| enhance_params.dewarp_image | 1 |
| enhance_params.correct_direction | 0 |
| enhance_params.deblur_image | 0 |
| enhance_params.jpeg_quality | 95 |
| erase_params.crop | **0** |
| erase_params.doc_direction | **0** |
| erase_params.dewarp | **0** |
| erase_params.binarization | **0** |
| erase_params.image_type | 1 |
| 中间产物 | `B1_enhanced.jpg` |
| 最终输出 | `B1_geom_only.jpg` |

### 4.4 B2_deshadow — 先切边矫正 + 去阴影增强，再擦除

| 字段 | 值 |
|------|-----|
| name | `B2_deshadow` |
| pipeline | `enhance_then_erase` |
| description | 前置切边+矫正+去阴影增强(enhance_mode=5)，后置纯擦除。回答：去阴影是否进一步提升擦除质量。 |
| enhance_params.enhance_mode | **5** |
| enhance_params.crop_image | 1 |
| enhance_params.dewarp_image | 1 |
| enhance_params.correct_direction | 0 |
| enhance_params.deblur_image | 0 |
| enhance_params.jpeg_quality | 95 |
| erase_params.crop | **0** |
| erase_params.doc_direction | **0** |
| erase_params.dewarp | **0** |
| erase_params.binarization | **0** |
| erase_params.image_type | 1 |
| 中间产物 | `B2_enhanced.jpg` |
| 最终输出 | `B2_deshadow.jpg` |

> **关键设计决策**: B 线后置 handwritten_erase 的 crop/dewarp 全部显式设为 0，因为前置 crop_enhance_image 已经做了这些。这是 Claude 修正案的核心点——两个接口重叠会导致 dewarp 二次形变。

---

## 5. 输出目录设计

每张样本输出以下文件:

```
data/api_eval/textin/output/sample_001/
├── original.jpg              # 从 input/ 复制
├── A1_default.jpg            # A1 输出
├── A2_no_sharpen.jpg         # A2 输出
├── B1_enhanced.jpg           # B1 中间产物 (crop_enhance_image 输出)
├── B1_geom_only.jpg          # B1 最终输出
├── B2_enhanced.jpg           # B2 中间产物
├── B2_deshadow.jpg           # B2 最终输出
├── responses/
│   ├── A1.json               # handwritten_erase 原始响应
│   ├── A2.json
│   ├── B1_enhance.json       # crop_enhance_image 原始响应
│   ├── B1_erase.json         # handwritten_erase 原始响应
│   ├── B2_enhance.json
│   └── B2_erase.json
└── meta.json                 # 处理元信息 (时长/尺寸/失败标记)
```

顶层对比页:

```
data/api_eval/textin/comparison/
└── index.html                # 5 联屏静态对比页 (original + 4 个 preset)
```

### meta.json 结构

```json
{
  "sample": "sample_001",
  "input_path": "input/sample_001.jpg",
  "input_size_bytes": 2456789,
  "input_dimensions": [3024, 4032],
  "results": [
    {
      "preset": "A1_default",
      "pipeline": "direct_erase",
      "ok": true,
      "duration_ms": 1834,
      "output_path": "output/sample_001/A1_default.jpg",
      "output_size_bytes": 1893456,
      "output_dimensions": [2856, 3782],
      "x_request_id": "abc123...",
      "error": null,
      "stage_failed": null
    }
  ]
}
```

- `stage_failed` 对 B 线关键: `"crop_enhance_image"` 或 `"handwritten_erase"` 明确失败发生在哪一步
- `x_request_id` 用于找 TextIn 客服排障

### compare.html 设计

- 静态 HTML，不需要后端服务
- 每张样本一组，5 张图等宽并排 (original + A1 + A2 + B1 + B2)
- 图片下方显示: 文件名 / 尺寸 / 耗时 / 文件大小
- 失败的 preset 显示红色错误信息而非空白
- 鼠标 hover 图片放大
- 底部留 "导出评价" 按钮接口 (第一轮不实现)

---

## 6. 错误处理

### 6.1 API key 缺失

```python
if not os.environ.get("TEXTIN_APP_ID") or not os.environ.get("TEXTIN_SECRET_CODE"):
    print("错误: 未设置 TEXTIN_APP_ID 或 TEXTIN_SECRET_CODE")
    print("请复制 .env.example 为 .env 并填入你的 TextIn API 密钥")
    sys.exit(1)
```

### 6.2 API 返回失败

- `client.handwritten_erase()` 返回 `{ok: False, error: "40101 鉴权失败", response_json: {...}}`
- experiment.py 收到 `ok=False` → 写入 `meta.json` 的 `stage_failed` + `error` 字段
- 不中断后续 preset

### 6.3 图片保存失败

- 写文件前检查目录存在 (`mkdir parents=True, exist_ok=True`)
- 写入失败 → 写入 meta.json error 字段，不中断

### 6.4 单个 preset 失败时

- try/except 包裹每个 preset 的执行
- 失败 → 记录到 meta.json，continue 下一个 preset
- B 线前置接口失败 → 不调用后置，直接标记 `stage_failed="crop_enhance_image"`
- 不设全局 try/except 吞掉所有错误

### 6.5 错误写入 compare.html

- 对于 `ok=False` 的 preset，compare.html 的卡片不显示图片，改为红色背景 + error 文字 + stage_failed 信息

---

## 7. 安全与配置

| 规则 | 实现 |
|------|------|
| API key 不进代码 | 从 `os.environ` 读取，通过 `python-dotenv` 加载 `.env` |
| .env 不进 git | 已在 `.gitignore` 中 |
| .env.example 提交 | 只有 key 名，值为空，作为模板 |
| response.json 全保存 | 每个 preset 的原始 JSON 响应完整写入 `responses/` 目录 |
| 日志不泄露 key | 打印错误信息时只 print error message，不 print 包含 key 的 headers |
| TextIn 限流 | 40306 错误不重试，记录并跳过，提示用户 30 秒后重试 |

---

## 8. 开发步骤

### Step 1: 配置与 client 骨架 (Commit 1)

**任务**:
- 创建 `src/m1_image_engine/providers/__init__.py`
- 创建 `src/m1_image_engine/providers/textin/__init__.py`
- 创建 `.env.example`
- 创建 `src/m1_image_engine/providers/textin/client.py` — TextInClient 类骨架
  - `__init__`: 加载环境变量
  - `handwritten_erase`: 签名完整但可以先 return fake response
  - `crop_enhance_image`: 同上
- 创建 `data/api_eval/textin/input/` 目录
- 创建 `data/api_eval/textin/README.md`

**验收**:
- `python -c "from src.m1_image_engine.providers.textin.client import TextInClient; c=TextInClient()"` 不报错
- `.env.example` 包含 TEXTIN_APP_ID= 和 TEXTIN_SECRET_CODE= 两行

### Step 2: presets.py 与 A 线 (Commit 2)

**任务**:
- 创建 `src/m1_image_engine/providers/textin/presets.py` — 4 个 preset 配置
- 完善 `client.py` 的 `handwritten_erase()` 真实实现
- 创建 `src/m1_image_engine/providers/textin/experiment.py` — 主入口骨架 + A 线调度
- 从 `input/` 读取样本 → 跑 A1/A2 → 保存结果 + response.json + meta.json

**验收**:
- 设置真实 API key 后 `python -m src.m1_image_engine.providers.textin.experiment` 成功跑通 A 线
- `output/sample_001/A1_default.jpg` 和 `A2_no_sharpen.jpg` 生成
- `responses/A1.json` 和 `A2.json` 包含完整 TextIn 响应
- meta.json 记录 A1/A2 两条记录

### Step 3: B 线串联调用 (Commit 3)

**任务**:
- 完善 `client.py` 的 `crop_enhance_image()` 真实实现
- experiment.py 增加 B 线逻辑:
  - 调 crop_enhance_image → 保存 `B1_enhanced.jpg` / `B2_enhanced.jpg`
  - 前置失败 → 标记 `stage_failed`，不调后置
  - 前置成功 → 调 handwritten_erase → 保存最终输出
- meta.json 增加 `stage_failed` 字段

**验收**:
- B1/B2 在 4 张样本上跑通 (或正确标记失败)
- `B1_enhanced.jpg` / `B2_enhanced.jpg` 中间产物存在
- meta.json `stage_failed` 字段填写正确
- 前置失败时，其他 preset 不受影响

### Step 4: compare.html 与 comparison/index.html (Commit 4)

**任务**:
- 创建 `src/m1_image_engine/providers/textin/README.md`
- experiment.py 增加 `generate_compare_html()` 函数
  - 读取 meta.json → 生成静态 HTML
  - 5 联屏: original + A1 + A2 + B1 + B2
  - 失败 preset 红色显示
- 输出 `data/api_eval/textin/comparison/index.html`

**验收**:
- `index.html` 用浏览器打开，5 联屏正确
- 失败 preset 显示错误信息
- 图片下显示文件名/尺寸/耗时
- README.md 包含完整的运行说明

---

## 9. 完成后输出

```
TextIn 实验模块技术方案完成:
- 阅读文档: Claude扩展_TextIn接口参数与实验矩阵方案.md (881行)
- 输出文档: docs/dev/TextIn实验模块技术实施方案.md
- 旧代码处理: src/m1_image_engine/ (mask.py/eraser.py/preprocess.py) 冻结不删
- 新增模块: src/m1_image_engine/providers/textin/ (4 文件)
- 新增数据: data/api_eval/textin/ (input/output/comparison)
- 开发步骤数: 4 个 commit 级任务
- 是否建议开始写代码: ✅ 是，文档已就绪
```
