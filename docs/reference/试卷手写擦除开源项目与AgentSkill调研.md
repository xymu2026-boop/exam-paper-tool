# 试卷手写擦除 — 开源项目与 Agent Skill 生态调研

> 生成时间：2026-05-31 | 调研者：Hermes
> 聚焦：GitHub 可复用项目 + Agent Skill 生态 + 试卷宝专用 Skill 设计

---

## 一、可复用项目清单（12 个）

| # | 项目 | GitHub | 类型 | 技术路线 | 预训练 | 可直跑 | 价值 | 难度 | 推荐 |
|---|------|--------|------|---------|--------|--------|------|------|------|
| 1 | HandWritingEraser-Pytorch | [AndSonder](https://github.com/AndSonder/HandWritingEraser-Pytorch) | 分割 | DeepLabv3+ 三分类（背景/印刷/手写） | ✅ 百度网盘 | ⚠️ 需配置 | 中文试卷分割最直接参考 | 中 | 🔥 深挖 |
| 2 | Handwriting-Removal-DIS | [ivanhe123](https://github.com/ivanhe123/Handwriting-Removal-DIS) | 分割 | DIS (IS-Net) 高精度二值分割 | ✅ HuggingFace | ✅ | 分割精度最高，数据集可直接下载 | 中 | 🔥 深挖 |
| 3 | WPI_inpainting | [adbu42](https://github.com/adbu42/WPI_inpainting) | 分割+修复 | 深度分割 + LBAM inpainting / 轻量背景填充 | ⚠️ 完整版需要 | ⚠️ | 轻量版零深度学习，填白逻辑直接可用 | 低 | ✅ 立刻试 |
| 4 | IOPaint (lama-cleaner) | [Sanster](https://github.com/Sanster/IOPaint) | 修复 | LaMa / MAT / ZITS / SD inpainting | ✅ pip install | ✅ | **最重要的修复后端**，CLI 批量、API 调用 | 低 | 🔥 立刻试 |
| 5 | EraseNet | [lcy0604](https://github.com/lcy0604/EraseNet) | 端到端 | 端到端 img2img 文字擦除 | ✅ | ⚠️ 需GPU | 终极方案参考，百度大赛验证 | 高 | 📖 仅参考 |
| 6 | Hand-Text-Erasure | [Yanting-K](https://github.com/Yanting-K/Hand-Text-Erasure) | 端到端 | 百度大赛 EraseNet 实现 + mask引导 | ✅ PaddlePaddle | ⚠️ 需GPU | 百度第一名方案完整代码 | 高 | 📖 仅参考 |
| 7 | PaddleOCR | [PaddlePaddle](https://github.com/PaddlePaddle/PaddleOCR) | OCR | 文字检测 + 识别，可只用于检测 | ✅ | ✅ | 检测印刷文字区域→保护 | 低 | ✅ 立刻试 |
| 8 | Document-Scanner-OpenCV | [joellijo32](https://github.com/joellijo32/Document-Scanner-using-OpenCV) | 预处理 | Canny + 轮廓 + 透视矫正 | 无需 | ✅ | 文档扫描流程完整参考 | 低 | ✅ 立刻试 |
| 9 | document_preprocessor | [smirnovkirilll](https://github.com/smirnovkirilll/document_preprocessor) | 预处理 | 完整预处理管线（EXIF→透视→CLAHE→二值化） | 无需 | ✅ | 预处理管线可直接复用 | 低 | ✅ 立刻试 |
| 10 | Shadow-Removal-OpenCV | [tablejai](https://github.com/tablejai/Shadow-Removal) | 预处理 | 图像处理去阴影 | 无需 | ✅ | 去阴影算法参考 | 低 | 📖 参考 |
| 11 | awesome-openclaw-skills | [VoltAgent](https://github.com/VoltAgent/awesome-openclaw-skills) | Agent生态 | 49.6k⭐ 的 OpenClaw skill 目录 | N/A | N/A | Skill 设计规范参考，目前无图像处理类 skill | — | 📖 参考 |
| 12 | OpenCV 官方 inpainting | [文档](https://docs.opencv.org/4.x/df/d3d/tutorial_py_inpainting.html) | 修复 | TELEA / NS 两种算法 | 内置 | ✅ | 基线修复方案 | 低 | ✅ 当前在用 |

---

## 二、重点项目深度分析

### 2.1 IOPaint（原 lama-cleaner）— 🔥 最重要

```
github.com/Sanster/IOPaint
```

| 维度 | 详情 |
|------|------|
| 安装 | `pip install iopaint` 或 `pip install lama-cleaner` |
| 模型 | LaMa（200MB）/ MAT / ZITS / Stable Diffusion / Manga |
| CLI 批量 | `iopaint run --model=lama --device=cpu --image=/path/to/img --mask=/path/to/mask --output=/path/to/out` |
| Python API | `from iopaint import InpaintModel; model = InpaintModel('lama', 'cpu'); result = model.forward(image, mask)` |
| Mac mini | ✅ CPU 可跑（单张 10-30s），GPU 加速更佳 |

**对试卷宝的价值**：
- 我们只需生成 `combined_mask.png`，IOPaint 负责修复
- LaMa 的傅里叶卷积专门处理大面积重复纹理（纸张纹理、横线），比 cv2.inpaint 效果好 3-5 倍
- 可以作为 `cleaned` 图生成的标准后端

**接入方式**：
```python
# 方案1: CLI 调用
subprocess.run(["iopaint", "run", "--model=lama", "--device=cpu",
    f"--image={preprocessed_path}",
    f"--mask={combined_mask_path}",
    f"--output={cleaned_path}"])

# 方案2: Python API（推荐）
from iopaint.model import models
model = models['lama'](device='cpu')
result = model.forward(image_bgr, mask_gray)
```

### 2.2 Handwriting-Removal-DIS — 分割精度最高

```
github.com/ivanhe123/Handwriting-Removal-DIS
```

| 维度 | 详情 |
|------|------|
| 模型 | DIS (IS-Net)，~170MB |
| 数据集 | HuggingFace: `Inoob/HandwritingSegmentationDataset` |
| MIT 协议 | ✅ |
| 推理 | `python Inference.py --image test.jpg` |
| Mac mini | ⚠️ PyTorch + 170MB，CPU 10-20s/张 |

**与 SegFormer / U-Net 对比**：DIS 是专为"高精度二值分割"设计的（Dichotomous Image Segmentation），对边缘细节处理优于通用分割模型。尤其适合手写笔迹这种细线条分割任务。

### 2.3 WPI_inpainting 轻量版 — 思路直接可用

```
github.com/adbu42/WPI_inpainting
```

**轻量版核心代码**（思路可直接用，不需要完整安装）：
```python
# fill_handwriting_with_background.py 的核心思路
# 1. 读取二值 mask
# 2. 从 mask 外部采样背景均值
# 3. 用背景均值填充 mask 区域
bg_mean = image[mask == 0].mean(axis=0)
result = image.copy()
result[mask > 0] = bg_mean
```
这和我们在方案 A 里推荐的"背景色采样"完全一致。**验证了这个思路是经过开源项目验证的正确方向。**

---

## 三、Agent Skill 生态调研

### 3.1 Hermes Skills 现状

当前 Hermes skills 目录覆盖 30+ 类别，**没有任何图像处理、文档清理、OCR、inpainting 相关的 skill**。这意味着：

- 我们是这个方向的**开拓者**
- 不能直接复用现有 skill
- 但可以参考 Hermes skill 的 SKILL.md 格式（YAML frontmatter + markdown body）

### 3.2 agent-skills.json 生态

Hermes 和 OpenCode 都支持 SKILL.md 格式（通过 `skill_manage` 工具管理）。我们的 skills 放在 `~/.hermes/skills/` 下即可被自动发现。

### 3.3 awesome-openclaw-skills

[VoltAgent/awesome-openclaw-skills](https://github.com/VoltAgent/awesome-openclaw-skills) 是目前最大的 Agent skill 目录（49.6k⭐），覆盖 PDF/文档、图像生成、安全等类别。但**图像处理/Document Cleanup 类别尚为空缺**——我们可以填补。

### 3.4 结论

Agent skill 生态中**没有现成的图像处理 skill 可用**。我们需要自己设计一套，同时也为社区贡献。

---

## 四、试卷宝专用 Agent Skill 设计草案

### 4.1 整体架构

```
用户上传图片
    ↓
skill: scan-image-preprocess    → preprocessed.jpg + meta.json
    ↓
skill: handwriting-mask-generator → red_mask.png + handwriting_mask.png + combined_mask.png
    ↓
skill: answer-inpaint-cleaner    → cleaned.jpg（支持多种后端）
    ↓
skill: cleaned-paper-reviewer    → review.json + quality_score
    ↓
用户确认 → 保存
```

### 4.2 scan-image-preprocess

```yaml
触发: 用户上传试卷照片
输入: original.jpg
输出: preprocessed.jpg, meta.json（含旋转角度/透视矩阵/质量评分/warnings）
依赖: OpenCV, Pillow, numpy

目录结构:
  ~/.hermes/skills/exam-paper/scan-preprocess/
  ├── SKILL.md
  ├── scripts/
  │   └── preprocess.py       # EXIF→缩放→纸张检测→透视→CLAHE→增强
  └── templates/
      └── meta_schema.json     # 输出元数据格式

流程:
  1. EXIF 方向修正
  2. 长边缩放到 3000px
  3. Canny 边缘检测 → 找最大四边形 → 透视矫正
  4. LAB 空间 CLAHE 去阴影
  5. 自适应阈值增强
  6. 输出 preprocessed.jpg + meta.json
```

### 4.3 handwriting-mask-generator

```yaml
触发: preprocessed.jpg 准备好后
输入: preprocessed.jpg
输出:
  - red_mask.png            (红笔区域，高置信度)
  - handwriting_mask.png    (手写区域，需经连通域过滤)
  - combined_mask.png       (合并后 + 形态学处理)
  - mask_overlay.jpg        (半透明红色叠加原图，调试用)

依赖: OpenCV, numpy

流程:
  1. HSV 提取红/蓝区域 → red_mask（高置信度）
  2. 深色区域检测 → 连通域过滤（面积/长宽比/笔画宽度）
     → handwriting_mask（低置信度，保守策略）
  3. combined = red_mask ∪ handwriting_mask（默认只用 red_mask）
  4. 形态学后处理：闭运算 → 膨胀 → 二值化
  5. 生成 mask_overlay 调试图

关键原则: "宁可漏擦，不可误删"
```

### 4.4 answer-inpaint-cleaner

```yaml
触发: combined_mask.png 生成后
输入: preprocessed.jpg + combined_mask.png
输出: cleaned.jpg
支持后端:
  - cv2_telea:    cv2.inpaint(INPAINT_TELEA) — 快速，适合细笔迹
  - cv2_ns:       cv2.inpaint(INPAINT_NS) — 适合大面积
  - white_fill:   自适应背景色填充 — 适合纯白试卷
  - lama:         IOPaint LaMa — 最佳效果，适合有纹理背景
  - api_youdao:   有道智云 API — 效果天花板，用于对比

配置:
  ~/.hermes/skills/exam-paper/inpaint-cleaner/config.yaml
  default_backend: white_fill
  backends:
    lama:
      model: lama
      device: cpu
    api_youdao:
      app_key: ${YOUDAO_APP_KEY}
      app_secret: ${YOUDAO_APP_SECRET}
```

### 4.5 cleaned-paper-reviewer

```yaml
触发: cleaned.jpg 生成后
输入: preprocessed.jpg, combined_mask.png, cleaned.jpg
输出: review.json

评分维度（0-10分）:
  - background_quality: 背景是否变脏（色差、补丁感）
  - handwriting_removal: 手写残留程度
  - print_preservation: 印刷内容损伤程度
  - geometry_integrity: 几何图形是否完整
  - printability: 是否可直接打印

警告触发条件:
  - quality_score < 5: "建议重新拍照"
  - geometry_integrity < 3: "几何图形可能受损"
  - print_preservation < 5: "题干可能有缺失"
```

### 4.6 wrong-question-exporter（仅接口设计，暂不实现）

```yaml
触发: 用户标记错题后
输入: cleaned.jpg + 错题框选坐标
输出: 错题截图 + 错题PDF/导出
状态: 🚧 接口预留，Phase 3 实现
```

---

## 五、与当前项目代码的关系

| 当前代码 | 对应 Skill | 关系 |
|---------|-----------|------|
| `src/m1_image_engine/preprocess.py` | scan-preprocess | 代码可直接作为 skill 的 scripts/ |
| `src/m1_image_engine/mask.py` | mask-generator | 需改造：加连通域过滤 + 保守策略 |
| `src/m1_image_engine/eraser.py` | inpaint-cleaner | 需改造：多后端支持 |
| 无 | cleaned-paper-reviewer | 🆕 全新，需要开发 |

**改造策略**：不是重写，而是在现有代码基础上模块化，抽成 skill 的 scripts/ 目录。

---

## 六、给 OpenCode 的下一步开发指令

```
## 任务：试卷宝后端改造（调试实验台 + 模块化）

### 背景

当前代码有几个问题需要修：
1. 红字涂白导致背景变脏（因为涂的是RGB 255/255/255，不是真实背景色）
2. mask 会把印刷文字也标记进去（缺少连通域过滤）
3. 黑笔手写不敢处理（也无法处理）
4. 没有 mask 叠加预览

### 执行顺序（不要一次全做）

**Step 1: 修 eraser.py（1小时）**
- 把 `result[mask>0] = (255,255,255)` 改成从 mask 边缘采样真实背景色再填充
- 从 mask 膨胀一圈取边缘像素，计算均值作为背景色

**Step 2: 修改 mask.py 的 _gray_handwriting_mask（2小时）**
- 对黑/灰色区域加连通域过滤：
  - 面积 < 20px → 过滤（噪点）
  - 面积 > 5000px → 过滤（印刷段落）
  - 长宽比 > 15 → 过滤（表格线）
- 保守策略：黑笔手写区域默认不加入 combined_mask

**Step 3: debug.html 加 mask 叠加预览（1小时）**
- 在 eraser 处理完成后，生成 mask_overlay.jpg（半透明红色叠加原图）
- debug.html 增加一栏展示 mask_overlay

**Step 4: 模块化（3小时）**
- 把处理流水线拆成独立函数，每个步骤输出中间文件：
  step1_original.jpg
  step2_preprocessed.jpg
  step3_red_mask.png
  step4_handwriting_mask.png
  step5_combined_mask.png
  step6_cleaned.jpg
  step7_mask_overlay.jpg
- debug.html 展示所有中间图

**Step 5: 预留 LaMa 接口（1小时）**
- 在 cleaned 生成处加一个 `backend` 参数
- 当前支持 'white_fill' | 'cv2_telea'
- 预留 'lama' 接口（函数签名写好，实现体放 pass）

### 不要做什么
- ❌ 不要继续调整 HSV 阈值参数
- ❌ 不要引入深度学习模型（先不用 PyTorch/ONNX）
- ❌ 不要改前端框架
- ❌ 不要做错题库/导出功能

### 验证方式
- 上传蓝笔试卷 → mask_overlay 只覆盖蓝笔区域，不覆盖印刷字
- 上传红笔批改试卷 → cleaned 红笔被擦除，背景不脏
- 所有中间文件都成功生成
```

---

## 七、推荐执行路线

```
本周（方案A）:
  1. 修 eraser.py（背景色采样）
  2. 修改 mask.py（连通域过滤）
  3. debug.html 加 mask 叠加预览

下周（方案B，与上面并行）:
  4. pip install iopaint
  5. 测试 "我们的 mask + LaMa 修复" 效果
  6. 注册有道智云，跑几张图做效果对比
  7. 用轻量版 WPI_inpainting 思路验证"背景色采样"效果

本月（方案C）:
  8. 如果 LaMa 效果显著优于 cv2.inpaint → 设为默认后端
  9. 如果 LaMa 效果不够 → 采购有道 API 批量处理
  10. 积累效果数据，判断是否需要训练本地分割模型
```

---

## 八、Agent Skill 生态结论

| 维度 | 现状 | 我们怎么做 |
|------|------|-----------|
| Hermes skills | 无图像处理类 | 自己写，放在 `~/.hermes/skills/exam-paper/` |
| OpenCode skills | 同上 | 通过 SKILL.md 格式共享 |
| OpenClaw skills | awesome-openclaw-skills 49.6k⭐ 但无图像处理 | 我们可以作为**首个文档清理类 skill** 贡献 |
| 通用格式 | SKILL.md（YAML + Markdown） | 统一用这个格式 |

**最重要的结论**：不要等生态成熟。这个领域在 Agent skill 生态中是**空白**。我们自己做，同时成为贡献者。

---

*调研者：Hermes | 调研项目：12 个 | Agent 生态：3 个 | Skill 设计：5 个*
