# 任务索引（OpenCode Agent 入口）

本文档是 OpenCode Agent 的入口路标。开发任何模块前，按以下顺序读取。

## 一、必读文档（按顺序）

1. **`docs/INTERFACE-CONTRACT.md`** — 最终版接口契约
   - 性质：所有模块开发的唯一权威定义
   - 内容：数据库 schema、文件存储约定、模块接口签名、错误处理约定
   - 规则：未经修改本文档，不得变更任何接口

2. **对应模块的任务卡** — `docs/modules/M{n}-*.md`
   - 性质：单模块的完整开发指引
   - 内容：目录结构、实现要求、测试要求、验收标准
   - 与契约的关系：任务卡是契约的实施细则，两者冲突以契约为准

3. **`家庭版试卷宝需求总文档_v1.0.md`** — 产品需求母版
   - 用于理解模块的业务背景，不直接指导技术实现

## 二、模块认领指南

| 模块 | 文件 | 可并行 | 依赖 | 推荐认领顺序 |
|------|------|--------|------|--------------|
| M1 图像引擎 | `docs/modules/M1-IMAGE-ENGINE.md` | ✅ | 无 | Phase 1 |
| M2 数据层 | `docs/modules/M2-DATA-LAYER.md` | ✅ | 无 | Phase 1 |
| M5 PDF 导出 | `docs/modules/M5-PDF-EXPORT.md` | ✅ | 无 | Phase 1 |
| M3 前端 | `docs/modules/M3-WEB-FRONTEND.md` | ✅（用 mock） | M4 API 定义 | Phase 2 |
| M4 后端 | `docs/modules/M4-WEB-BACKEND.md` | ⚠️ | M1+M2+M5 | Phase 3 |

**Phase 1（并行起跑）**：M1、M2、M5 三个 Agent 同时开工，零依赖。
**Phase 2（前端跟进）**：M3 Agent 基于契约的 API 定义用 mock 服务器开发。
**Phase 3（集成收口）**：M4 Agent 等 M1+M2 接口稳定后做胶水层。

## 三、开发流程（每个 Agent）

```
1. 读 docs/INTERFACE-CONTRACT.md
   ↓
2. 读 docs/modules/M{你的编号}-*.md
   ↓
3. 在 src/m{你的编号}_*/ 目录下开发
   ↓
4. 在 tests/m{你的编号}/ 目录下写测试
   ↓
5. pytest tests/m{你的编号}/ -v 全绿
   ↓
6. 提交（参考下方 git 规范）
```

## 四、跨模块协作规则

### 规则 1：契约先行
任何接口变更必须先改 `INTERFACE-CONTRACT.md`，再改代码。绝不允许代码和契约不一致。

### 规则 2：模块边界
- M1/M5 是纯函数式库，不读数据库、不发 HTTP 请求
- M2 是数据库唯一入口，其他模块通过 import 调用，禁止其他模块直接执行 SQL
- M3 是纯静态资源，不直接读文件系统
- M4 是唯一的 HTTP 服务，是 M1/M2/M5 的协调者

### 规则 3：错误处理
- M1/M5：返回 dataclass，`success` 字段表示成败
- M2：失败返回 `None` 或 `False`，不抛异常
- M4：HTTP 状态码 + JSON `{"error": "..."}`

### 规则 4：测试隔离
每个模块的测试只测自己，不依赖其他模块运行。M4 测试时 mock M1/M5。

## 五、Git 提交规范

```
<模块编号>: <动作> <对象>

例：
M1: 实现 process_paper 主流程
M2: 添加 list_mistakes 分页查询
M3: 完成 Canvas 框选交互
M4: /api/papers/upload 接入 M1 处理
M5: 实现 two_per_page 排版
docs: 更新 INTERFACE-CONTRACT 第 4.4 节
```

每个模块在自己的目录下工作（`src/m{n}_*/` + `tests/m{n}/`），冲突概率极低。

## 六、问答与同步

- 接口疑问：先看契约，仍有歧义时在 `docs/INTERFACE-CONTRACT.md` 末尾的"待澄清问题"里追加，由项目经理统一裁决
- 进度同步：每个模块在自己目录下工作，git pull 不会冲突
- 远端同步：本地频繁开发，每 1-2 小时同步一次到 GitHub

## 七、当前状态（2026-05-31）

| 模块 | 状态 | 说明 |
|------|------|------|
| 接口契约 | ✅ 最终版 | v1.0-FINAL |
| M1 任务卡 | ✅ | 待 Agent 认领 |
| M2 任务卡 | ✅ | 待 Agent 认领 |
| M3 任务卡 | ✅ | 待 Agent 认领（Phase 2） |
| M4 任务卡 | ✅ | 待 Agent 认领（Phase 3） |
| M5 任务卡 | ✅ | 待 Agent 认领 |
| 项目骨架 | ✅ | 目录、依赖、git 已就绪 |
