<!-- 迁移自旧项目 exam-paper-tool，原始路径: docs/OpenCode_试卷擦除技术方案.md -->

# 试卷手写擦除工具 — 技术调研与实施方案

**版本**：v1.0 | **日期**：2026-05-31 | **场景**：家庭学习，全本地运行 | **调研执行**：OpenCode (Claude Sonnet 4.6)

---

## 一、背景与约束

| 项目 | 说明 |
|------|------|
| 使用场景 | 拍摄试卷照片 → 擦除手写答案 → 输出干净试卷供重复使用 |
| 隐私要求 | 全本地运行，零数据上传 |
| 硬件约束 | 普通家用 PC / Mac，无独立 GPU |
| 用户群体 | 家长或学生，非技术背景 |
| 当前思路 | Pillow 颜色阈值 + 人工框选 + OpenCV inpainting 半自动路线 |

---

## 二、搜索到的相关项目

### 2.1 AndSonder/HandWritingEraser-Pytorch

| 字段 | 内容 |
|------|------|
| 地址 | https://github.com/AndSonder/HandWritingEraser-Pytorch |
| 语言 | Python |
| 核心依赖 | PyTorch 1.7+, DeepLabv3+ (ResNet50) |
| 数据集 | 百度 AI Studio 中文试卷分割数据集（背景/印刷字/手写字三分类） |

**核心思路**：语义分割识别手写区域 → 置白或 inpainting 填充。专门针对中文试卷设计。

**优点**：分割精度高，有完整训练代码。**缺点**：依赖 PyTorch，模型 100MB+，CPU 推理 30-60秒/张，部署门槛高。

### 2.2 ivanhe123/Handwriting-Removal-DIS

| 字段 | 内容 |
|------|------|
| 地址 | https://github.com/ivanhe123/Handwriting-Removal-DIS |
| Stars | 15 |
| 语言 | Python, MIT 协议 |
| 核心依赖 | DIS (IS-Net, ~170MB) |
| 数据集 | HuggingFace: Inoob/HandwritingSegmentationDataset |

**核心思路**：DIS (IS-Net) 高精度二值分割 → mask → 背景填充。比 DeepLabv3+ 更新，边缘处理更好。

**优点**：分割精度最高，数据集在 HuggingFace 可直下。**缺点**：模型 170MB，CPU 推理 10-20秒/张。

### 2.3 adbu42/WPI_inpainting

| 字段 | 内容 |
|------|------|
| 地址 | https://github.com/adbu42/WPI_inpainting |
| 语言 | Python |

**核心思路**：两种模式——完整版（深度分割+LBAM inpainting），轻量版（背景均值填充，零深度学习）。

**关键发现**：轻量版对白色背景试卷效果出奇地好——白色填充比 inpainting 更干净。

### 2.4 smirnovkirilll/document_preprocessor

| 字段 | 内容 |
|------|------|
| 地址 | https://github.com/smirnovkirilll/document_preprocessor |
| 语言 | Python |
| 核心依赖 | pillow, opencv-python, numpy（无深度学习） |

**核心思路**：文档预处理流水线（透视矫正→去噪→对比度增强→二值化→形态学清理）。不直接做擦除，但预处理代码可复用。

### 2.5 OpenCV 官方 Inpainting

| 算法 | 原理 | 适用场景 |
|------|------|----------|
| INPAINT_TELEA | Fast Marching Method，边界向内加权平均 | 细线条、笔迹边缘 |
| INPAINT_NS | Navier-Stokes 流体方程，沿等照度线传播 | 大面积区域 |

**关键认知**：inpainting 不检测手写区域，只负责填充。mask 质量决定最终效果上限。

### 2.6 StackOverflow 实战方案

参考：https://stackoverflow.com/questions/56219829/

两种验证过的方案：(A) 形态学处理（threshold + MORPH_CLOSE + erode），(B) HSV颜色阈值 + dilate + INPAINT_TELEA。

---

## 三、竞品对比分析

| 项目 | 手写检测 | 填充方式 | GPU需求 | 中文适配 | 部署难度 | 效果 |
|------|---------|---------|---------|---------|---------|------|
| HandWritingEraser-Pytorch | DeepLabv3+ 分割 | 置白/inpainting | 推荐 | ⭐⭐⭐⭐⭐ | 高 | ⭐⭐⭐⭐⭐ |
| Handwriting-Removal-DIS | DIS 分割 | 背景填充 | 推荐 | ⭐⭐⭐⭐⭐ | 高 | ⭐⭐⭐⭐⭐ |
| WPI_inpainting 完整版 | 深度分割 | LBAM inpainting | 推荐 | ⭐⭐⭐ | 高 | ⭐⭐⭐⭐ |
| WPI_inpainting 轻量版 | 任意mask | 背景均值填充 | 不需要 | ⭐⭐⭐ | 极低 | ⭐⭐ |
| **HSV阈值 + inpainting** | **颜色阈值+人工** | **cv2.inpaint** | **不需要** | **⭐⭐⭐⭐** | **低** | **⭐⭐⭐** |
| document_preprocessor | 不擦除 | — | 不需要 | ⭐⭐⭐ | 极低 | — |

### 关键结论

1. **黑笔是硬伤**：黑笔与印刷字同色，颜色阈值无效。应对：建议用蓝/红笔答题。
2. **白色填充 > inpainting**：试卷背景纯白时，直接填白更干净更快。
3. **深度学习暂时不需要**：效果虽好但部署成本高（100MB+模型、GPU需求），家庭场景不值得。

---

## 四、推荐技术路线

### 整体架构

```
拍照输入 → 预处理(透视矫正+去噪) → Mask生成(HSV颜色阈值+人工框选)
         → 区域填充(白色填充首选/inpainting备选) → 输出干净试卷
```

### 核心代码

**预处理**：Canny边缘检测 → 找最大四边形 → 透视变换矫正

**Mask生成**：HSV色彩空间阈值（蓝色 H:100-150, 红色 H:0-10或170-180）+ 形态学膨胀

**填充**：白色填充（首选）或 cv2.inpaint TELEA/NS（备选）

---

## 五、分阶段实施

### Phase 1：命令行 MVP（1-2天）

- pip install pillow opencv-python numpy（~50MB）
- 实现 HSV 颜色阈值 mask + 白色填充/inpainting
- CLI: `python eraser.py input.jpg --color blue --output clean.jpg`
- 用 5-10 张真实试卷验证

### Phase 2：半自动 GUI（3-5天）

- tkinter 构建（Python 内置，零额外依赖）
- 功能：图片拖拽打开、颜色选择+阈值滑块实时预览 mask、鼠标框选/橡皮擦、撤销重做、对比视图、批量处理

### Phase 3：质量提升（可选）

- 连通域过滤去噪点
- CLAHE 对比度增强改善铅笔检测
- 自适应阈值应对光照不均
- 如果积累 ≥200 张标注数据，可考虑训练轻量分割模型

---

## 六、风险与对策

| 风险 | 对策 |
|------|------|
| 黑笔无法检测 | 建议用蓝/红笔答题；或引入人工框选补充 |
| inpainting大面积模糊 | 白色填充替代 |
| 拍照歪斜 | Phase 1 加入透视矫正 |
| 用户操作门槛 | Phase 2 GUI 降低门槛 |
| 深度学习效果更好但门槛高 | Phase 3 作为远期升级路径 |

---

*方案由 OpenCode (Claude Sonnet 4.6) 调研并撰写，Hermes 审核。2026-05-31*
