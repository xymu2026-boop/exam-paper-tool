# 试卷宝 (Exam Paper Tool)

家庭试卷处理系统 — 拍照 → 预处理 → 擦除手写 → 框选错题 → 导出 PDF 复练。

## 项目定位

面向青山家庭学习场景的本地工具，全流程本地处理，不上传云端。

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 启动服务（开发完成后）
python -m src.m4_web_backend.app
# 浏览器打开 http://localhost:8900
```

## 项目结构

```
exam-paper-tool/
├── docs/
│   ├── INTERFACE-CONTRACT.md   # 接口契约（最终版，所有开发必读）
│   └── modules/                # 各模块开发任务卡
│       ├── M1-IMAGE-ENGINE.md
│       ├── M2-DATA-LAYER.md
│       ├── M3-WEB-FRONTEND.md
│       ├── M4-WEB-BACKEND.md
│       └── M5-PDF-EXPORT.md
├── src/
│   ├── m1_image_engine/        # 图像处理引擎
│   ├── m2_data_layer/          # 数据层 (SQLite)
│   ├── m3_web_frontend/        # Web 前端 (HTML/JS)
│   ├── m4_web_backend/         # Web 后端 (FastAPI)
│   └── m5_pdf_export/          # PDF 导出
├── data/                       # 运行时数据（不进 git）
│   ├── samples/                # 测试样本图片
│   ├── originals/              # 原图归档
│   ├── processed/              # 处理结果
│   ├── mistakes/               # 错题截图
│   └── exports/                # 导出的 PDF
├── tests/                      # 测试
│   ├── m1/
│   ├── m2/
│   ├── m3/
│   └── m5/
├── experiments/                # 实验记录
├── requirements.txt            # Python 依赖
└── 家庭版试卷宝需求总文档_v1.0.md  # 产品需求母版
```

## 模块架构

```
M1 (图像引擎)  ←── 无依赖，独立开发
M2 (数据层)    ←── 无依赖，独立开发
M3 (前端)      ←── 依赖 M4 的 API 定义（可用 mock）
M4 (后端)      ←── 依赖 M1 + M2 + M5 的接口
M5 (PDF导出)   ←── 无依赖，独立开发
```

**并行开发策略**：M1 + M2 + M5 三路并行 → M3 用 mock 并行 → M4 集成。

## 开发指南

1. 先读 `docs/INTERFACE-CONTRACT.md`（接口契约）
2. 再读对应模块的 task card（`docs/modules/M{n}-*.md`）
3. 按 task card 中的目录结构和接口定义开发
4. 用 `pytest tests/m{n}/` 验证

## 技术栈

| 层级 | 技术 |
|------|------|
| 图像处理 | OpenCV + Pillow |
| 数据库 | SQLite |
| 后端 | FastAPI |
| 前端 | HTML + Alpine.js + Canvas |
| PDF | fpdf2 |
| 测试 | pytest |

## 隐私规范

- 代码和文档中只用 K1/K2，不出现真名
- data/ 目录不进 git
- 图片不上传云端
