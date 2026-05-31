# 家庭版试卷宝 — Hermes 审核补充与对齐建议

> 版本：v1.0 | 日期：2026-05-31 | 制定者：Hermes
> 关联文档：《家庭版试卷宝需求总文档 v1.0》
> 性质：**补充文档**，不修改原文，仅追加审核意见、技术对齐建议和差异化思路

---

## 〇、总评

原文是一份**产品思维非常成熟**的需求文档。1420 行，8 条主线，P0/P1/P2 优先级清晰，5 个阶段规划合理，验收标准可量化。

**Hermes 审核结论：通过。** 以下内容不是推翻，而是在四个方向上做补充。

---

## 一、用家庭代号替换真名（对齐家庭 AI 体系）

**问题**：文档中反复出现孩子真名（李沐阳、李沐熙），违反了家庭 AI 体系的隐私约定。

**建议**：后续所有文档、代码、数据库字段、页面文案统一使用：

| 真名 | 家庭代号 |
|------|---------|
| 李沐阳 | K1（初中七年级） |
| 李沐熙 | K2（小学五年级） |

**对齐规则**：
- 数据库字段：`child_id: "K1" | "K2"`
- 页面下拉框：K1 / K2（不显示真名）
- 文件路径：不含真名
- GitHub 公开仓库：绝不出现真名

> ⚠️ 原文不改（那是你的文档），但从这份补充文档开始，Hermes 产出的所有内容都用 K1/K2。

---

## 二、技术架构补充（原文偏产品，补技术）

### 2.1 推荐的技术栈（比原文更具体的选型建议）

| 层级 | 原文 | Hermes 建议 | 理由 |
|------|------|-----------|------|
| 前端 | 网页（未指定技术） | **纯 HTML + Vanilla JS + Canvas**，单文件 | 零构建、零依赖、双击打开、Phase 2 不引入框架 |
| 后端 | 未指定 | **Python Flask**（轻量，50 行起跑） | Phase 1 的 Python 脚本直接 import 复用 |
| 图像处理 | OpenCV + Pillow | OpenCV + Pillow + **scikit-image**（可选） | scikit-image 的去阴影算法（`rgb2gray` + `equalize_adapthist`）比纯 OpenCV 效果好 |
| 数据库 | 未指定 | **SQLite**（单文件，零配置） | 家庭场景不需要 PostgreSQL，SQLite 够用且易备份 |
| PDF 导出 | 未指定 | **ReportLab**（纯 Python）或 **img2pdf** | img2pdf 最简单：`img2pdf.convert(["1.jpg","2.jpg"]) → PDF` |
| 部署 | 本地 | `python app.py` → `localhost:5000` | 局域网手机访问：`--host 0.0.0.0` |

### 2.2 为什么不用 React / Next.js

这是一个**家庭自用工具**，不是 SaaS 产品。对比：

| | React/Next.js | 纯 HTML + Flask |
|---|---|---|
| 学习成本 | 高 | 零（HTML 人人会写） |
| 构建步骤 | npm install → build → serve | 无 |
| 部署 | 需要 Node.js | 只需要 Python |
| 维护 | 依赖地狱 | pip install 3 个包 |
| 适合场景 | 多人协作 / SaaS | **单人开发 / 家庭自用** ✅ |

### 2.3 图像处理管线设计（比原文更具体的 Pipeline）

```
输入：手机照片（任意分辨率、任意方向）

Step 1: EXIF 方向修正
  → PIL.ImageOps.exif_transpose() 或 piexif 库
  → 解决手机拍照自动旋转元数据问题

Step 2: 纸张检测 + 透视矫正
  → cv2.Canny() 边缘检测
  → cv2.findContours() 找最大四边形
  → cv2.getPerspectiveTransform() + warpPerspective()
  → 输出：A4 比例正视图（2480×3508 @ 300dpi）

Step 3: 去阴影（关键改进）
  → 原文说"去阴影"，但没有说怎么做
  → 推荐：cv2.createCLAHE() 自适应直方图均衡化
  → 通道分离 → 对 L 通道做 CLAHE → 合并
  → 效果：光照不均的试卷变均匀

Step 4: 二值化 + 增强
  → cv2.adaptiveThreshold() 自适应阈值（比全局 Otsu 更好）
  → 或 cv2.fastNlMeansDenoising() 去噪
  → 输出：清晰黑白文档

Step 5: 手写 mask 生成
  → HSV 颜色空间：蓝色 H∈[100,130]、红色 H∈[0,10]∪[170,180]
  → morphologyEx(MORPH_CLOSE) 闭合小孔
  → dilate() 膨胀覆盖笔迹边缘
  → 输出：二值 mask 图

Step 6: 区域填充
  → 白色填充（首选，纯白背景）
  → INPAINT_TELEA（备选，有纹理背景）
  → 输出：干净试卷图
```

### 2.4 数据模型建议（原文只描述了功能，补数据结构）

```sql
-- SQLite 表结构建议

CREATE TABLE child (
    id TEXT PRIMARY KEY,        -- 'K1' | 'K2'
    grade TEXT,                 -- '七年级' | '五年级'
    created_at TEXT
);

CREATE TABLE paper (
    id INTEGER PRIMARY KEY,
    child_id TEXT REFERENCES child(id),
    subject TEXT,               -- '数学'|'语文'|'英语'|'科学'|'其他'
    paper_type TEXT,            -- '作业'|'单元卷'|'考试卷'|'练习册'|'其他'
    title TEXT,                 -- 可选，如"5月单元测试"
    original_path TEXT,         -- 原图路径
    processed_path TEXT,        -- 预处理后路径
    cleaned_path TEXT,          -- 擦除后路径
    upload_time TEXT,
    status TEXT DEFAULT 'pending'  -- pending|processed|reviewed
);

CREATE TABLE mistake (
    id INTEGER PRIMARY KEY,
    paper_id INTEGER REFERENCES paper(id),
    child_id TEXT REFERENCES child(id),
    subject TEXT,
    x INTEGER, y INTEGER,       -- 错题在原图上的坐标
    width INTEGER, height INTEGER,
    mistake_image_path TEXT,     -- 错题截图
    clean_mistake_image_path TEXT, -- 擦除版错题
    note TEXT,                   -- 家长备注
    error_type TEXT,             -- '粗心'|'概念不清'|'计算错误'|'不会做'
    status TEXT DEFAULT 'new',   -- new|printed|practiced|passed|retry
    created_at TEXT,
    reviewed_at TEXT
);

CREATE TABLE export_log (
    id INTEGER PRIMARY KEY,
    child_id TEXT,
    subject TEXT,
    mistake_ids TEXT,           -- JSON array
    pdf_path TEXT,
    created_at TEXT
);
```

**为什么用 SQLite 而不是 JSON 文件**：
- JSON 文件在"多个操作同时读写"时会出问题
- SQLite 支持 SQL 查询，按孩子/学科/状态筛选非常自然
- SQLite 单文件，备份就是 cp 一个文件

---

## 三、阶段计划的对齐建议

### 3.1 原文的阶段拆分 vs Hermes v3 方案

| | 原文 | Hermes v3 方案 | 对齐建议 |
|---|------|---------------|---------|
| 阶段数 | 5 个（0→1→2→3→4→5） | 5 个（1→2→3→4→5） | 统一为 5 个 |
| Phase 0 | 需求收敛 + 样本准备 | 已基本完成（本文档） | ✅ 合并到 Phase 1 前置 |
| Phase 1 | 图片预处理 + 擦除实验 | CLI 擦除验证 | ✅ 一致 |
| Phase 2 | 本地网页 MVP | Web 上传 + 擦除 | ✅ 一致 |
| Phase 3 | 错题库 | 错题识别 + 导出 | ✅ 一致 |
| Phase 4 | 飞书入口 | 批量管理 + 归档 | ⚠️ 有分歧，见下 |
| Phase 5 | AI 增强 | 智能升级 | ✅ 一致 |

### 3.2 Phase 4 的分歧：飞书入口 vs 批量管理

**原文**：Phase 4 = 飞书入口
**Hermes 建议**：Phase 4 = 批量管理 + 按孩子/学科归档，飞书入口后置

**Hermes 的理由**：
1. 飞书开发涉及机器人注册、Webhook、权限回调，调试周期不可控
2. 飞书只是一个"入口"，核心能力（擦除+错题）如果不稳定，加飞书也没有意义
3. 先做批量管理（历史记录、筛选、归档），对家庭场景的价值更直接
4. 飞书入口可以放在 Phase 4.5 或 Phase 5

**建议**：以你的判断为准。如果你认为飞书入口对家庭使用频率更高，可以保留原文顺序。

---

## 四、线上调研补充

### 4.1 GitHub 上可参考的开源项目

| 项目 | 可借鉴的点 | 不适合的点 |
|------|----------|----------|
| **AndSonder/HandWritingEraser-Pytorch** | 中文试卷手写分割思路、三分类标注（背景/印刷/手写） | 需要 PyTorch + GPU，部署重 |
| **adbu42/WPI_inpainting** | 轻量版 `fill_handwriting_with_background.py`——用背景均值填充，零深度学习，对白色试卷极好 | 非白色背景效果差 |
| **smirnovkirilll/document_preprocessor** | 完整的文档预处理管线（EXIF→透视→灰度→增强→二值化→形态学），纯 Pillow/OpenCV，代码可直接复用 | 不直接做擦除 |

### 4.2 图像处理最佳实践（线上验证的）

1. **去阴影**：CLAHE（自适应直方图均衡化）比全局亮度调整好得多，特别适合"台灯侧照产生半边阴影"的场景
2. **二值化**：`cv2.adaptiveThreshold(ADAPTIVE_THRESH_GAUSSIAN_C)` 比全局 Otsu 更稳定，不受光照不均影响
3. **透视矫正**：先 `cv2.Canny` → `cv2.findContours` 找最大四边形 → 四点透视变换，这是文档扫描的标准套路
4. **白色填充 vs inpainting**：对纯白背景试卷，直接填白比 inpainting 更干净更快。inpainting 只用于有横线/格子/纹理的背景

### 4.3 Flask 上传最佳实践

来自 Flask 官方文档和社区验证：
```python
# 安全上传的核心代码
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'heic'}
MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/upload', methods=['POST'])
def upload():
    file = request.files['image']
    child = request.form['child']  # K1 / K2
    subject = request.form['subject']
    # 保存到 data/originals/{K1}/{subject}/{timestamp}.jpg
```

---

## 五、风险补充（原文已有 1 个风险点，补 4 个）

### 5.1 原文提到的风险
- ✅ 擦除是最大技术难点（阶段 1 优先验证）

### 5.2 Hermes 补充的风险

| # | 风险 | 概率 | 影响 | 缓解 |
|---|------|------|------|------|
| 1 | **HEIC 格式不兼容** — iPhone 默认拍照格式是 HEIC，Pillow 不直接支持 | 高 | 用户上传失败 | 前端用 JS 转换或后端加 `pillow-heif` 插件 |
| 2 | **大图内存溢出** — 手机照片 4000×3000 像素，OpenCV 处理可能 OOM | 中 | 处理失败 | 预处理第一步缩小到 2000px 宽度 |
| 3 | **局域网手机访问失败** — Flask 默认只监听 localhost | 中 | 手机打不开 | 启动时 `app.run(host='0.0.0.0', port=5000)` + 防火墙放行 |
| 4 | **样本不够导致误判** — 只在 30 张样本上测试通过，上线后新类型图片效果差 | 高 | 用户信任崩塌 | Phase 1 明确"当前支持"和"当前不支持"的图片类型清单，设低预期 |

### 5.3 不可突破的硬底线（与原文一致，Hermes 追加强调）

| # | 底线 | 违反后果 |
|---|------|---------|
| 1 | **不误删印刷题干** | 题目内容被改，孩子做错题不知道是题错了还是自己错了 |
| 2 | **不破坏公式/图形** | 分数线消失=整道数学题废了 |
| 3 | **图片不上传云端** | 含孩子笔迹、可能含姓名学校信息 |
| 4 | **原图永久保留** | 擦坏了有后悔药 |

---

## 六、对原文结构的建议（不改内容，只补结构）

原文已经非常好。建议在以下位置补充（Hermes 可以帮你写）：

| 补充位置 | 内容 | 优先级 |
|---------|------|--------|
| 主线 2 后 | 《图片预处理 Pipeline 技术方案》（含完整代码骨架） | P0 |
| 主线 3 后 | 《手写擦除技术选型报告》（涂白 vs inpainting 量化对比） | P0 |
| 主线 5 后 | 《数据库表结构设计 v1》（SQLite schema） | P1 |
| 主线 6 后 | 《PDF 导出技术方案》（img2pdf + ReportLab 对比） | P1 |
| 第 8 章 | 补充 Phase 1 的具体技术验证清单（验收项量化） | P0 |
| 第 10 章 | 补充"失败样本处理流程"（擦除失败的图片怎么办） | P1 |

---

## 七、下一步行动建议

| 优先级 | 行动 | 产出 |
|--------|------|------|
| 🔴 P0 | Phase 1 CLI 擦除实验 | 10-30 张样本，量化擦除成功率 |
| 🔴 P0 | 建 SQLite 数据库骨架 | 按第 2.4 节的 schema |
| 🟡 P1 | 拆原文 8 条主线为独立 PRD | 每份 PRD 200-500 字，重点写验收标准 |
| 🟡 P1 | 内部统一用 K1/K2 | 后续所有新文档和代码 |
| 🟢 P2 | 准备真实测试样本 | 按第 11 章的五维覆盖矩阵收集 |

---

## 八、结论

原文是一份**优秀的母版文档**。Hermes 的补充集中在四个方向：

1. **技术对齐**：补了具体的技术选型、Pipeline 设计、数据模型
2. **隐私对齐**：用 K1/K2 替换真名，和家庭 AI 体系统一
3. **阶段对齐**：指出 Phase 4 的分歧，提供理由但不强推
4. **风险对齐**：补了 4 个原文未覆盖的技术风险

**原文不需要改。** 这份补充文档作为 `docs/reference/hermes-review-supplement.md` 存档，后续开发时对照参考即可。

---

*审核者：Hermes | 审核基础：原文 1420 行 + GitHub 搜索结果 + OpenCV/Flask 社区最佳实践*
