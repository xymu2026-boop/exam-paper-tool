# TextIn 实验模块 — 多角色开发计划

> 版本: v1.0 | 日期: 2026-06-01
> 基于: docs/dev/TextIn实验模块技术实施方案.md
> 状态: 待青山确认 → 待 OpenCode 执行

---

## 一、多角色分工表

| 角色 | 代号 | 模型 | 职责 |
|------|------|------|------|
| 架构负责人 | Architect | DeepSeek V4 Pro (`deep`) | 确认隔离边界、文件清单、风险点 |
| API 后端 | Backend-Dev | DeepSeek V4 Pro (`writing`) | client.py 实现 + 错误处理 |
| 实验流水线 | Pipeline-Dev | DeepSeek V4 Pro (`deep`) | presets.py + experiment.py 调度逻辑 |
| 结果页面 | Frontend-Dev | DeepSeek V4 Pro (`visual-engineering`) | compare.html + comparison/index.html |
| 测试验收 | QA | DeepSeek V4 Pro (`deep`) | 测试清单 + 验收跑通 |

### 执行模式

```
Commit 1: Architect 做边界确认 → Backend-Dev 写 client.py
Commit 2: Pipeline-Dev 写 presets.py + A 线
Commit 3: Pipeline-Dev 追加 B 线
Commit 4: Frontend-Dev 写 compare.html + QA 跑验收
```

Commit 1/2/3 串行（有依赖），Commit 4 的前端和 QA 可并行。

---

## 二、每个角色负责的文件

### Architect (架构负责人)

| 类型 | 文件 |
|------|------|
| 新增 | `src/m1_image_engine/providers/__init__.py` |
| 新增 | `src/m1_image_engine/providers/textin/__init__.py` |
| 新增 | `src/m1_image_engine/providers/textin/client.py` (签名骨架) |
| 新增 | `.env.example` |
| 不修改 | `src/m1_image_engine/mask.py` |
| 不修改 | `src/m1_image_engine/eraser.py` |
| 不修改 | `src/m1_image_engine/preprocess.py` |
| 不修改 | `src/m1_image_engine/engine.py` |
| 不修改 | `src/m4_web_backend/` (所有文件) |
| 不修改 | `src/m3_web_frontend/paper.html` |

### Backend-Dev (TextIn API 后端)

| 类型 | 文件 |
|------|------|
| 新增/编辑 | `src/m1_image_engine/providers/textin/client.py` |
| 新增 | `requirements.txt` 追加 `requests`, `python-dotenv` |
| 不修改 | 其他所有文件 |

### Pipeline-Dev (Preset 与流水线)

| 类型 | 文件 |
|------|------|
| 新增 | `src/m1_image_engine/providers/textin/presets.py` |
| 新增 | `src/m1_image_engine/providers/textin/experiment.py` |
| 新增 | `data/api_eval/textin/` (目录结构 + meta.json) |
| 不修改 | `client.py` 的接口签名（只调不改） |

### Frontend-Dev (结果页面)

| 类型 | 文件 |
|------|------|
| 新增 | `data/api_eval/textin/comparison/index.html` |
| 新增 | experiment.py 内 `generate_compare_html()` 函数 |
| 不修改 | `src/m3_web_frontend/` (所有文件) |

### QA (测试验收负责人)

| 类型 | 文件 |
|------|------|
| 编辑 | `src/m1_image_engine/providers/textin/README.md` (补充运行命令) |
| 不创建 | 本轮不写 pytest 测试文件 |
| 验证 | `.gitignore` 包含 `.env` |

---

## 三、每个角色的输入输出

### Architect

**输入**:
- `docs/dev/TextIn实验模块技术实施方案.md` (完整方案)
- `src/m1_image_engine/` 当前代码
- `docs/INTERFACE-CONTRACT.md` 模块边界定义

**输出**:
- 新增文件列表确认
- 不修改文件清单确认
- 依赖变更: `requests`, `python-dotenv`
- 风险点报告:
  - TextIn API 限流 (40306) — 单次不可重试
  - B 线 dewarp 二次形变 — 已在 preset 中修复
  - 大图超时 — 已设 60s
  - .env 泄漏 — 已配置 .gitignore
- 确认 `src/m1_image_engine/providers/` 与现有 `src/m1_image_engine/` 隔离

### Backend-Dev

**输入**:
- Claude 扩展方案 §9.3 (client.py 签名)
- TextIn API 官方文档 (接口 URL, 鉴权方式, 错误码)
- 技术实施方案 §6 (错误处理规范)

**输出**:
- `TextInClient` 类, 两个方法:
  - `handwritten_erase(image_bytes, *, crop, doc_direction, dewarp, binarization, image_type, mask_position=None, crop_position=None) → dict`
  - `crop_enhance_image(image_bytes, *, enhance_mode, crop_image, dewarp_image, correct_direction, deblur_image, jpeg_quality, only_position=0, round_image=0, size_and_positon=None) → dict`
- 返回 dict 结构: `{ok: bool, image_bytes: bytes|None, response_json: dict, duration_ms: int, error: str|None, x_request_id: str|None}`
- crop_enhance_image 额外字段: `position: list|None, angle: int|None`
- BASE URL: `https://api.textin.com/ai/service/v1`
- 鉴权 headers: `x-ti-app-id` + `x-ti-secret-code`
- 请求格式: binary body (`Content-Type: application/octet-stream`)
- 超时: 60s
- 错误码 40306: 不重试, 直接返回失败

### Pipeline-Dev

**输入**:
- client.py 接口签名
- 技术实施方案 §4 (4 个 preset 参数表)
- 技术实施方案 §5 (输出目录设计)

**输出**:
- `PRESETS` 列表: 4 个 dict, 每个含 name/pipeline/description/erase_params/增强_params
- `experiment.py` 主流程:
  - `run_one_sample(sample_path, preset, client, output_dir)`
  - `run_all_samples()`
  - `generate_meta_json(...)`
  - `generate_compare_html(...)`
- A 线逻辑: `image_bytes → client.handwritten_erase(**erase_params) → 保存结果`
- B 线逻辑: `image_bytes → client.crop_enhance_image(**enhance_params) → 保存 enhanced.jpg → client.handwritten_erase(enhanced_result, **erase_params) → 保存最终结果`
- 失败处理: 每个 preset 独立 try/except, stage_failed 写入 meta.json

### Frontend-Dev

**输入**:
- meta.json 结构 (含 stage_failed, error, duration_ms, output_dimensions)
- 每个样本目录下的图片文件路径
- 技术实施方案 §8.4 (compare.html 设计要求)

**输出**:
- `comparison/index.html` 静态页面
- 布局: 每样本一个 section, 5 张图等宽并排
- 每张图下方信息条: 文件名 / 尺寸 / 耗时 / 状态
- 失败 preset: 红色背景卡片 + error message + stage_failed
- 无 JavaScript 依赖, 纯 HTML + inline CSS
- 鼠标 hover 图片 1.5x 放大

### QA

**输入**:
- 完整代码 (client.py + presets.py + experiment.py)
- .env.example 模板
- input/ 目录下的样本图

**输出**:
- 测试清单 (6 条, 见 §六)
- 验收清单 (每个 commit 的验收标准)
- README.md 补充: 运行命令, 预期输出, 常见问题
- 确认 `.env` 在 `.gitignore` 中

---

## 四、4 个 Commit 的执行顺序

```
Commit 1 ──▶ Commit 2 ──▶ Commit 3 ──▶ Commit 4
(Architect +  (Pipeline-   (Pipeline-   (Frontend-Dev
 Backend-Dev)  Dev A线)     Dev B线)     + QA)

Commit 1 依赖: 无
Commit 2 依赖: Commit 1 (client.py 接口就绪)
Commit 3 依赖: Commit 2 (presets.py + A线框架就绪)
Commit 4 依赖: Commit 3 (meta.json 数据就绪)
```

### Commit 1: 配置与 client 骨架

**执行角色**: Architect + Backend-Dev

**操作**:
1. Architect 创建目录 `src/m1_image_engine/providers/` 和 `providers/textin/`
2. Architect 创建 `__init__.py` 文件
3. Backend-Dev 创建 `.env.example`
4. Backend-Dev 实现 `client.py` — TextInClient 类, 两个接口方法
5. Backend-Dev 追加 `requests` `python-dotenv` 到 requirements.txt
6. QA 确认 `.gitignore` 包含 `.env`

**验收标准**:
- [ ] `.env.example` 包含 TEXTIN_APP_ID= 和 TEXTIN_SECRET_CODE= 两行
- [ ] `python -c "from src.m1_image_engine.providers.textin.client import TextInClient"` 不报错
- [ ] 不设置 env var 时 `TextInClient()` 抛出明确提示 (如 "未设置 TEXTIN_APP_ID")
- [ ] `handwritten_erase()` 和 `crop_enhance_image()` 签名符合 §9.3 规范
- [ ] 参数全部 keyword-only (函数签名用 `*`)
- [ ] 返回 dict 包含 `ok, image_bytes, response_json, duration_ms, error, x_request_id`
- [ ] `mask_position`, `crop_position`, `size_and_positon` 为可选 kwarg
- [ ] 二进制流 body, Content-Type application/octet-stream

### Commit 2: Preset 与 A 线

**执行角色**: Pipeline-Dev

**操作**:
1. 创建 `presets.py` — 4 个 preset 配置 (A1/A2/B1/B2)
2. 创建 `experiment.py` — 骨架 + A 线调度
3. 创建 `data/api_eval/textin/input/` 目录 (放 README 说明放什么图)
4. 实现 `run_one_sample()` — 对单个样本跑所有 preset
5. 实现 A 线: 直接调 handwritten_erase

**验收标准**:
- [ ] `presets.py` 包含 4 个 preset, 每个有 name/pipeline/description/erase_params
- [ ] `python -m src.m1_image_engine.providers.textin.experiment` 不设 key 时提示缺少配置并退出
- [ ] 设置 key 后, 对 input/ 下 1 张图跑通 A1/A2
- [ ] `output/sample_xxx/A1_default.jpg` 和 `A2_no_sharpen.jpg` 生成
- [ ] `output/sample_xxx/responses/A1.json` 和 `A2.json` 包含完整 TextIn 响应
- [ ] `output/sample_xxx/original.jpg` 从 input 复制
- [ ] `output/sample_xxx/meta.json` 记录 A1/A2 两条结果

### Commit 3: B 线

**执行角色**: Pipeline-Dev

**操作**:
1. 在 `experiment.py` 增加 B 线调度逻辑
2. B 线: crop_enhance_image → 保存 enhanced.jpg → handwritten_erase → 保存最终输出
3. 前置失败 → 标记 `stage_failed="crop_enhance_image"`, 不调后置
4. meta.json 增加 `stage_failed` 字段

**验收标准**:
- [ ] 对 input/ 下 1 张图跑通 B1/B2
- [ ] `B1_enhanced.jpg` 和 `B2_enhanced.jpg` (中间产物) 生成
- [ ] `B1_geom_only.jpg` 和 `B2_deshadow.jpg` (最终输出) 生成
- [ ] `responses/B1_enhance.json`, `B1_erase.json`, `B2_enhance.json`, `B2_erase.json` 各 1 份
- [ ] meta.json 对 B1/B2 记录 `stage_failed=null`
- [ ] 模拟前置失败: crop_enhance_image 返回错误 → meta.json 记录 stage_failed, 不调后置
- [ ] A1/A2 不受 B 线任何失败影响

### Commit 4: HTML 对比页

**执行角色**: Frontend-Dev + QA

**操作**:
1. Frontend-Dev 在 experiment.py 增加 `generate_compare_html()` 函数
2. Frontend-Dev 生成 `comparison/index.html` (5 联屏)
3. Frontend-Dev 生成每样本的 `output/sample_xxx/compare.html`
4. QA 补全 README.md (运行命令 / 验收清单 / 常见问题)
5. QA 跑完整验收流程

**验收标准**:
- [ ] `comparison/index.html` 用浏览器打开, 每样本 5 图并排
- [ ] 失败 preset 显示红色背景 + error + stage_failed
- [ ] 图片下方显示文件名 / 尺寸 / 耗时
- [ ] 不需要启动 Web 服务即可查看 (file:// 协议)
- [ ] README.md 包含: `python -m src.m1_image_engine.providers.textin.experiment`
- [ ] `.env` 确认在 `.gitignore` 中且未提交
- [ ] 旧的 `src/m1_image_engine/mask.py` 等文件未被修改 (`git diff --name-only` 不含它们)

---

## 五、文件修改权限矩阵

### ✅ 允许修改

```
src/m1_image_engine/providers/__init__.py            (新建)
src/m1_image_engine/providers/textin/__init__.py     (新建)
src/m1_image_engine/providers/textin/client.py        (新建→编辑)
src/m1_image_engine/providers/textin/presets.py       (新建)
src/m1_image_engine/providers/textin/experiment.py    (新建)
src/m1_image_engine/providers/textin/README.md        (新建→编辑)
.env.example                                          (新建)
requirements.txt                                      (追加 requests, python-dotenv)
data/api_eval/textin/                                 (新建全目录)
```

### ❌ 禁止修改

```
src/m1_image_engine/mask.py           # OpenCV 管线
src/m1_image_engine/eraser.py         # OpenCV 管线
src/m1_image_engine/preprocess.py     # OpenCV 管线
src/m1_image_engine/engine.py         # OpenCV 管线
src/m1_image_engine/quality.py        # OpenCV 管线
src/m1_image_engine/utils.py          # OpenCV 管线
src/m1_image_engine/cli.py            # OpenCV 管线
src/m2_data_layer/                    # 数据层
src/m3_web_frontend/paper.html        # 主调试页
src/m3_web_frontend/debug.html        # 调试页
src/m4_web_backend/                   # Web 后端
src/m5_pdf_export/                    # PDF 导出
docs/INTERFACE-CONTRACT.md            # 接口契约
.env                                  # 密钥文件
```

---

## 六、QA 测试清单

| # | 场景 | 验证方法 | 通过标准 |
|---|------|---------|---------|
| 1 | 无 API key 运行 | `python -m ...experiment` (不设 env var) | 打印 "未设置 TEXTIN_APP_ID" 并 exit 1 |
| 2 | input 目录为空 | 清空 input/ 后运行 | 打印 "input 目录无图片" 并退出 |
| 3 | 单样本 A 线 | input/ 放 1 张图, 跑 experiment | A1/A2 两张输出图 + 两份 response.json |
| 4 | B 线前置失败 | 故意传非法参数给 enhance | meta.json stage_failed="crop_enhance_image", 不崩溃 |
| 5 | B 线后置失败 | 模拟 enhance 成功但 erase 失败 | meta.json stage_failed="handwritten_erase" |
| 6 | .env 未提交 | `git status` + cat `.gitignore` | .env 不在 staged files 中 |

---

## 七、最终确认清单

| 问题 | 答案 |
|------|------|
| 角色数量 | 5 |
| 计划 commit 数 | 4 |
| 允许修改文件 | 10 个 (见 §五 白名单) |
| 禁止修改文件 | 18 个 (见 §五 黑名单) |
| 新增依赖 | `requests`, `python-dotenv` |
| 是否需要 TextIn API key | ✅ 是 — Commit 2 开始就需要, 提前准备好 |
| 是否需要样本图片 | ✅ 是 — 放 4 张到 `data/api_eval/textin/input/`, 建议提前放 |
| 预计开发风险 | 低 — 独立模块, 不碰主流程, 失败成本可控 |
| 是否建议开始写代码 | ✅ 是 — 计划完整, 确认后立即启动 |
