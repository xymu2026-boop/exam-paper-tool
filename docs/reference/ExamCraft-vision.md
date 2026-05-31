> ⚠️ 本文档来自已归档的独立项目 ExamCraft（在线试卷创作平台），与 exam-paper-tool（试卷手写擦除工具）是不同的项目。\n> 保留此文档仅供架构参考。\n\n---\n\n# ExamCraft — 下一代智能试卷工坊

> **愿景**：从 CLI 试卷生成脚本，进化为一个**开放、模块化的智能考试创作平台**——"试卷领域的 VS Code"。

---

## 📋 项目背景

### 对标项目分析：`riyuexing/wordpapergenerate`

**`wordpapergenerate`** 是一款基于 Node.js 的动态试卷生成工具，核心能力：

| 维度 | 详情 |
|------|------|
| **定位** | CLI 试卷生成工具，输出 `.docx` 格式 Word 试卷 |
| **技术栈** | Node.js · `docx` 库 · `adm-zip` · `xlsx` |
| **题库规模** | 4661 道煤矿安全题目（单选 1626 / 多选 1241 / 判断 1794） |
| **题型** | 单选 · 多选 · 判断 · 问答 |
| **排版** | A3/A4/B4 · 横向/纵向 · 2栏分隔线 · 装订线（奇偶页） |
| **模式** | 模板模式（复杂排版）+ 简单模式（快速生成） |
| **许可证** | MIT |

**优点**：排版专业（装订线/分栏/奇偶页眉）、API 可编程、一键生成、大容量题库。

**核心局限**：CLI 专用 · JSON 文件存储无数据库 · 纯随机抽题无智能算法 · 无 Web 界面 · 无在线考试功能 · 无用户/角色管理 · 单次提交无版本演进。

---

## 🌍 竞品横向分析

基于全网 15+ 同类项目的调研，市场呈现三类产品：

### 1. 纯生成工具（CLI / 库）
> `wordpapergenerate`, `hecun0000/examCreate`, `TUD-RST/examgenerator`

特点：专注 "生成" 本身，无 Web 界面，轻量，适合技术用户。

### 2. 在线考试系统（Web 全栈）
> `mindskip/xzs` (3853⭐), `Alanosy/online-exam-system-backend` (884⭐), `wells2333/sg-exam` (536⭐), `yf-team/yf-boot-exam`, `baymaxsjj/exam`（遗传算法组卷）

特点：前后端分离 · 多角色（管理员/教师/学生）· 在线答题 · 自动评分 · 有数据库 · Java 技术栈为主。

### 3. AI 驱动的新一代
> `reneverland/CBIT-AiExam-plus` (276⭐), `xiehust/ai-exam-generator`, `Goppai/exam`（多模态）, `QuAIz`（流式生成）

特点：大模型出题 · 多模态 · 语义判分 · 学情分析。

### 竞品功能矩阵

```
                      AI能力
                       ↑ 高
                       │  CBIT-AiExam-plus (276★)
                       │  Goppai/exam (多模态)
                       │  QuAIz / ai-exam-generator
                       │
                       │                       mindskip/xzs (3853★)  在线考试
                       │                       Alanosy (884★)
                       │                       sg-exam (536★)
                       │
                       │  wordpapergenerate     ← 对标项目（2★）
                       │  TestPapaerGen-WebApp  纯组卷
                       │
                       └──────────────────────────────────→ 功能完整度
                        纯工具                     完整系统
```

---

## 🔴 市场差距 — wordpapergenerate v2.0 的机会窗口

经过系统性分析，现有所有工具的 **6 大共同短板**：

| # | 短板 | 现状 | ExamCraft 方案 |
|---|------|------|----------------|
| 1 | **无可视化试卷编辑器** | 所有工具都是 "盲生成"，没有 WYSIWYG 实时预览 | TipTap 富文本编辑器 + 实时渲染预览 |
| 2 | **AI 模型强绑定** | 每个工具锁死单一 LLM（Gemini / GLM / Dify），无法切换 | Vercel AI SDK 抽象层，支持 20+ 模型热切换 |
| 3 | **输出格式单一** | 要么 Word，要么 PDF，要么 HTML，没有统一的多格式出口 | 插件化 Export Engine（DOCX / PDF / HTML / Markdown） |
| 4 | **无协作能力** | 所有工具都是单人操作，没有教师协作出卷 | Google Docs 风格的多人实时协作编辑 |
| 5 | **无难度校准** | 难度是人工标签，不是数据驱动的 | IRT / ELO 难度自动校准算法 |
| 6 | **无 LMS 集成** | 零工具支持 Moodle / Canvas / Google Classroom | LTI 1.3 标准接口 |

---

## 🎯 ExamCraft 产品定位

```
┌─────────────────────────────────────────────────┐
│                                                 │
│   wordpapergenerate v1           ExamCraft v2   │
│   ┌──────────┐                  ┌─────────────┐ │
│   │ CLI 工具  │  ── 进化 ──▶   │ 创作平台     │ │
│   │ JSON题库  │                 │ 可视化编辑   │ │
│   │ Word 输出 │                 │ 多格式导出   │ │
│   │ 单人使用  │                 │ 多人协作     │ │
│   └──────────┘                  │ AI 辅助出题  │ │
│                                 │ 在线考试     │ │
│                                 │ LMS 集成     │ │
│                                 └─────────────┘ │
│                                                 │
│   Slogan: "从想到考，一站式试卷工作流"          │
└─────────────────────────────────────────────────┘
```

---

## 🏗️ 技术架构总览

```
┌──────────────────────────────────────────────────┐
│                  Frontend                         │
│   Next.js 14 (App Router)                        │
│   TipTap Editor · tRPC · shadcn/ui · Tailwind    │
│   PWA (next-pwa) · i18n (next-intl)              │
├──────────────────────────────────────────────────┤
│              API Layer (tRPC / Hono)              │
│   Auth (NextAuth.js) · Rate Limiting · Logging   │
├──────────┬──────────┬──────────┬─────────────────┤
│  Paper   │  Bank    │   AI     │  Export Engine  │
│  Service │  Service │  Service │  ┌─ DOCX        │
│          │          │  ┌───────│  ├─ PDF/LaTeX   │
│          │          │  │  LLM   │  ├─ HTML        │
│          │          │  │  Proxy │  ├─ Markdown    │
│          │          │  └───────│  └─ Plugin API   │
│          │          │  Provider Interface         │
│          │          │  (OpenAI/Claude/Gemini/     │
│          │          │   Ollama/Custom)            │
├──────────┴──────────┴──────────┴─────────────────┤
│              Data Layer                           │
│   PostgreSQL + Prisma · Redis (cache/session)     │
│   MinIO (file storage)                            │
└──────────────────────────────────────────────────┘
```

### 核心技术选型

| 层级 | 技术 | 选型理由 |
|------|------|----------|
| **前端框架** | Next.js 14 (App Router) | SSR + PWA + 文件路由，一石三鸟 |
| **富文本编辑器** | TipTap (ProseMirror) | 可扩展、无头 UI、支持协作 |
| **API 层** | tRPC | 端到端类型安全，零样板代码 |
| **UI 组件** | shadcn/ui + Tailwind CSS | 可定制、可访问、开发速度快 |
| **ORM** | Prisma | 类型安全，迁移管理完善 |
| **数据库** | PostgreSQL | ACID、全文搜索、JSONB 灵活存储 |
| **AI 抽象** | Vercel AI SDK | 模型无关，支持流式，统一接口 |
| **认证** | NextAuth.js v5 | 多 Provider、JWT、RBAC |
| **文档导出** | Pandoc + 自研模板 | 万能转换，生态最强 |
| **公式渲染** | KaTeX / MathJax | LaTeX 渲染，学术级 |
| **文件存储** | MinIO | S3 兼容，自托管 |

---

## 📅 分阶段路线图

### Phase 1: 核心引擎 — 试卷创作工作台（MVP）
> 目标：让教师能**可视化地**创建、编辑、预览、导出试卷。

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **WYSIWYG 试卷编辑器** | TipTap 驱动，实时预览分页/分栏/装订线效果 | P0 |
| **题库管理界面** | 卡片/表格视图，CRUD，批量导入（CSV/JSON/Quizlet） | P0 |
| **题型全覆盖** | 单选/多选/判断/填空/问答/匹配，可扩展插件 | P0 |
| **多格式导出** | DOCX · PDF(LaTeX) · HTML · Markdown，一键导出 | P0 |
| **LaTeX 公式** | KaTeX 实时渲染数学/化学公式 | P0 |
| **排版预设** | A3/A4/B4 · 横向/纵向 · 分栏 · 装订线 · 水印 | P0 |
| **用户系统** | 注册/登录 · 基础 RBAC（管理员/教师） | P1 |
| **试卷模板** | 预设模板 + 自定义模板保存 | P1 |

### Phase 2: 智能化 — AI 辅助出题
> 目标：让 AI 成为教师的**副驾驶**，而非替代者。

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **AI 出题引擎** | 基于知识点/参考资料自动生成题目 | P0 |
| **多模型支持** | OpenAI / Claude / Gemini / 智谱 / DeepSeek / Ollama | P0 |
| **题目难度校准** | IRT/ELO 算法，基于作答数据自动修正难度 | P1 |
| **智能组卷** | 遗传算法 + 约束求解器（题型/难度/知识点分布） | P1 |
| **题目去重/改写** | 检测重复题，AI 改写保持考查点不变 | P2 |
| **反作弊变体** | 等难度随机变体（每个考生不同试卷） | P2 |

### Phase 3: 平台化 — 在线考试 + 协作
> 目标：从 "创作工具" 升级为 "考试平台"。

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **在线考试** | 限时答题 · 自动保存 · 断点续考 | P0 |
| **自动评分** | 客观题秒批 · 主观题 AI 辅助评分 | P0 |
| **考试监控** | 切屏检测 · 时间日志 · 异常行为标记 | P1 |
| **多人协作编辑** | Yjs + TipTap Collaboration，实时同步 | P1 |
| **版本历史** | 试卷/题目维度的 Git-like 历史与 Diff | P1 |
| **成绩分析** | 题目统计（难度/区分度/选项分析）· 学生画像 | P1 |
| **学生端** | 我的考试 · 成绩查询 · 错题本 | P1 |

### Phase 4: 生态化 — 开放与集成
> 目标：成为可被集成、可扩展的平台。

| 功能 | 描述 | 优先级 |
|------|------|--------|
| **LMS 集成** | LTI 1.3 标准接口（Moodle/Canvas/Google Classroom） | P1 |
| **PWA 离线** | Service Worker + IndexedDB，离线创建/批改，联网同步 | P2 |
| **Plugin 市场** | 第三方导出格式 · AI 模型 · 题型扩展 | P2 |
| **多租户** | 学校/机构独立空间，品牌化定制 | P2 |
| **无障碍** | WCAG 2.1 AA，屏幕阅读器，键盘导航 | P2 |

---

## 📐 核心数据模型设计

```
┌──────────┐     ┌──────────────┐     ┌──────────┐
│   User   │────→│ Organization │←────│  Role    │
└──────────┘     └──────────────┘     └──────────┘
      │                  │
      ▼                  ▼
┌──────────┐     ┌──────────────┐
│ Question │────→│ QuestionBank │
│  - stem  │     │  - name      │
│  - type  │     │  - subject   │
│  - options│    │  - tags      │
│  - answer │     └──────────────┘
│  - difficulty│         │
│  - tags  │              ▼
│  - media │     ┌──────────────┐
└──────────┘     │    Paper     │
      │          │  - title     │
      ▼          │  - config    │
┌──────────┐     │  - sections  │
│PaperItem │────→│  - status    │
│ - order  │     │  - version   │
│ - score  │     └──────────────┘
│ - section│            │
└──────────┘            ▼
                 ┌──────────────┐
                 │    Exam      │
                 │  - startTime │
                 │  - duration  │
                 │  - rules     │
                 └──────────────┘
                        │
                        ▼
                 ┌──────────────┐
                 │ Submission   │
                 │  - answers   │
                 │  - score     │
                 │  - feedback  │
                 └──────────────┘
```

---

## 🚀 快速启动（本地开发）

```bash
# 克隆项目
git clone https://github.com/xymu2026-boop/ExamCraft.git
cd ExamCraft

# 安装依赖
pnpm install

# 启动数据库
docker compose up -d postgres redis minio

# 初始化数据库
pnpm prisma migrate dev
pnpm prisma db seed

# 启动开发服务器
pnpm dev
# → http://localhost:3000

# 运行测试
pnpm test
```

---

## 🧪 测试策略

| 层级 | 工具 | 覆盖率目标 |
|------|------|-----------|
| 单元测试 | Vitest | ≥ 80% |
| 组件测试 | Testing Library + Vitest | ≥ 70% |
| E2E | Playwright | 核心流程 100% |
| API 测试 | Supertest + Vitest | ≥ 90% |
| 性能测试 | k6 / Lighthouse | PWA score ≥ 90 |

---

## 📦 项目结构预览

```
ExamCraft/
├── apps/
│   ├── web/                  # Next.js 主应用
│   │   ├── app/              # App Router 页面
│   │   ├── components/       # UI 组件
│   │   │   ├── editor/       # TipTap 试卷编辑器
│   │   │   ├── bank/         # 题库管理
│   │   │   ├── exam/         # 在线考试组件
│   │   │   └── ui/           # shadcn/ui 基础组件
│   │   ├── lib/              # 工具函数
│   │   └── server/           # tRPC 路由
│   └── export-engine/        # 导出引擎服务
├── packages/
│   ├── ai/                   # AI 抽象层 (Vercel AI SDK)
│   ├── db/                   # Prisma Schema + 迁移
│   ├── paper-core/           # 试卷核心逻辑
│   ├── scoring/              # 评分引擎
│   └── shared/               # 共享类型和工具
├── docker/
│   └── compose.yml           # 开发环境
├── docs/                     # 文档
└── scripts/                  # 构建/部署脚本
```

---

## 🔗 相关项目

| 项目 | 说明 | Stars |
|------|------|-------|
| [riyuexing/wordpapergenerate](https://github.com/riyuexing/wordpapergenerate) | 对标项目 — Node.js Word 试卷生成器 | 2 |
| [mindskip/xzs](https://github.com/mindskip/xzs) | 最流行的在线考试系统 — SpringBoot+Vue | 3853 |
| [reneverland/CBIT-AiExam-plus](https://github.com/reneverland/CBIT-AiExam-plus) | AI 通用考试平台 | 276 |
| [Goppai/exam](https://github.com/Goppai/exam) | 多模态 AI 试卷解析 | — |
| [yf-team/yf-boot-exam](https://github.com/yf-team/yf-boot-exam) | SpringBoot 3.0 考试系统 | 6 |
| [baymaxsjj/exam](https://github.com/baymaxsjj/exam) | 遗传算法组卷系统 | 99 |

---

## 📄 License

MIT — 与上游 wordpapergenerate 保持一致。

---

> *"一份好试卷，是教师专业能力的结晶。好的工具，应该让这份结晶更容易诞生。"*
