# Deepseek 学习 Claude 复核报告后的推进建议

> 生成时间：2026-06-01 | 作者：Deepseek 小马
> 学习对象：`docs/reference/Claude复核_试卷手写擦除开源方案补充调研.md`（697行）
> 性质：行动建议，非重新调研

---

## 一、我从 Claude 报告中确认的共识

Claude 认可我前面调研中以下几个判断是正确的，不需要再争论：

1. **HSV 阈值路线到头了** — 黑笔手写和印刷字在像素级不可区分，继续调 RED_S_MIN / CANNY_LO 是边际收益递减。这一点 Claude 给了"完全正确"的评价。
2. **正确路线是 mask + inpainting** — 先生成手写区域的 mask，再用修复算法填充。这是学术界和工业界的共识结构，我们的 `combined_mask.png` 方向是对的。
3. **IOPaint/LaMa 应该接入** — 但不是作为"银弹"，而是作为多后端中的一种可选方案。
4. **debug 页面和中间结果可视化极其关键** — 在这个"效果不可量化、参数空间大"的项目里，能肉眼看到每一步是唯一可靠的调试手段。
5. **Agent Skill 生态没有现成方案** — 我们需要自己沉淀 skill，同时可以贡献给社区。

---

## 二、Claude 对我前面调研的修正

Claude 指出了我几处需要正视的问题：

### 2.1 IOPaint/LaMa 不是"修复神药"

我在前面报告里说"LaMa 比 cv2.inpaint 效果好 3-5 倍"。Claude 纠正：这个数字在纯白 A4 试卷的细笔迹场景下是夸张的。LaMa 的真正优势在两个场景：(1) 大面积红字/红圈遮挡，(2) 横线/格子背景的练习册。在纯白纸细笔迹上，LaMa 提升是"从可见瑕疵→几乎无瑕疵"，而 cv2.inpaint 已经是"可见但可接受"。

**我的修正**：不要把 LaMa 当成默认后端，它应该和 OpenCV、背景色填充并列展示，让用户（现阶段是我们自己）用肉眼选。

### 2.2 真正决定效果上限的是 mask 质量，不是修复算法

这是 Claude 最重要的纠偏。LaMa 不知道哪里是手写——它只按你给的 mask 修。如果 mask 把印刷字的半边盖住了，LaMa 会同样忠实地把印刷字"修掉"。所以**下一阶段的主战场是 mask 生成，不是修复后端选型**。我前面调研把太多篇幅给了 inpainting 对比，对 mask 质量提升的讨论不够。

### 2.3 商业 API 不能进入产品流水线

我前面多次推荐"先用有道 API 跑 baseline"。Claude 指出这与家庭场景的隐私要求直接冲突——孩子作业含姓名、学校、教师批注。正确做法：**用 1-2 张脱敏图片做一次性效果对照，不接入产品代码**。真正能做 ground truth 的是 SCUT-EnsExam 数据集或 Inoob/HandwritingSegmentationDataset。

### 2.4 部分开源项目的描述需要更严谨

- **Hand-Text-Erasure**：我说它是"百度大赛第一名"，实际是亚军/参赛方案。真正的冠军是 zdyshine 的仓库。
- **EraseNet 是远期目标**：实际上已被 GaRNet（ECCV 2022, PSNR 41.37）全面超越，远期应该看 GaRNet。
- **IOPaint Python API**：我写的 `from iopaint import InpaintModel` 在 1.x 版本中已过时。
- **IOPaint CLI**：不是单文件 `--image --mask --output`，而是目录级批次模式。

---

## 三、我认为当前项目的主线判断

### 3.1 现在是否应该继续调研？

**不应该。** Claude 的报告已经把项目清单从我的 12 个扩展到 14 个，覆盖了数据集、论文、商业 API。信息已经足够做决策。再调研就是"调研的调研"，边际收益为零。

### 3.2 是否应该进入 OpenCode 开发阶段？

**应该。** 而且不是因为"准备好了"，而是因为**只有进入开发、跑出真实效果，才能驱动下一轮决策**。现在所有关于"LaMa 到底比 cv2.inpaint 好多少""DIS mask 适不适合家庭拍照场景"的判断，都是基于论文和他人报告的推测。唯一可靠的依据是我们自己上传真实试卷跑出来的结果。

### 3.3 为什么当前重点是"把 debug 实验台跑通"而不是"继续找最强模型"？

因为我们现在不知道问题出在哪里：
- 是 mask 把印刷字标进去了？
- 还是 mask 根本没找到手写？
- 还是 inpainting 把背景修坏了？

不把实验台做好（每一步都能看中间结果），我们永远在猜。

### 3.4 为什么 A 阶段不应该引入 OCR、DIS、SegFormer？

每个新模块引入都会让调试空间指数级膨胀：
- OCR 引入 → 需要调 OCR 参数 → OCR 可能把工整手写当印刷字保护 → 需要额外修正逻辑 → 新 bug
- DIS 引入 → 需要 PyTorch 环境 → MPS 兼容性 → 推理速度 → 模型输出格式适配

A 阶段的目标是**先把当前链路跑通**，确认 mask→inpainting 的结构本身没有问题，再考虑升级单一模块。

### 3.5 为什么要用真实试卷效果来驱动下一轮判断？

因为我们在 Mac mini 本地跑，不是 Kaggle 比赛。论文里的 SCUT-EnsText PSNR 41.37 是在 GPU 上跑的，我们的约束完全不同。只有真实跑完才知道：
- 手机上 3000px 宽的照片在这台机器上处理一帧是 1 秒还是 30 秒？
- 红笔擦除后背景真的自然吗？
- mask overlay 看着对吗？

---

## 四、下一步 A 阶段行动建议

### A 阶段目标

1. 不追求最终完美效果；
2. 先把工程链路跑通；
3. 让我们能在 debug 页面看到每一步；
4. 能对比不同修复后端；
5. 能知道问题到底出在 mask，还是出在 inpainting。

### Step 1：修好并增强 debug 页面

**做什么**：
- 确认 6 张中间图（original / preprocessed / red_mask / handwriting_mask / combined_mask / cleaned）都能稳定显示
- 新增 mask overlay 4 联屏：原图 + red_mask overlay + handwriting_mask overlay + combined_mask overlay，每张下标注 mask 覆盖率%
- 显示图片 URL、尺寸、文件大小
- 失败时展示错误信息（而非空白或假图）

**验收**：上传试卷后，6 个标签页全部可见，无报错。

### Step 2：接入 IOPaint/LaMa 作为可选修复后端

**做什么**：
- `pip install iopaint`
- 新增 `src/m1_image_engine/eraser_iopaint.py`
- 函数：`erase_with_iopaint(image_path, mask_path, output_path, model="lama", device="mps") -> dict`
- 首次调用 lazy-load 模型，后续复用
- **失败自动 fallback 到 cv2.inpaint**，并在响应中记 warning

**验收**：同一张图的 `cleaned_opencv.jpg` 和 `cleaned_iopaint_lama.jpg` 都能生成，肉眼可对比。

### Step 3：后端支持多 backend

**做什么**：
- `eraser.py` 重构成路由：根据 `backend` 参数调用不同实现
- 支持 `backend=opencv | iopaint_lama | bg_fill`
- 每个 backend 输出独立文件（`cleaned_opencv.jpg` / `cleaned_iopaint_lama.jpg` / `cleaned_bg_fill.jpg`）

**验收**：API 传入不同 backend 参数，输出到不同文件。

### Step 4：增强 mask overlay 四联屏

**做什么**：
- paper.html 新增"全 mask 全景"标签页
- 一页四屏并排显示 mask overlay
- 每张下方：mask 名称 + 覆盖率百分比 + 像素数
- 如果某张 mask 为空（如当前 handwriting_mask 可能全黑），也要显示并标注"mask 为空"

**验收**：四联屏全部可见，覆盖率数据正确。

### Step 5：增加 quality_signals 和 warnings/errors

**做什么**：
- API 返回 JSON 增加 `quality_signals` 字段：
  - `mask_coverage_pct`：combined mask 占总像素比例（>20% 警告）
  - `red_residual_pct`：cleaned 图重新跑 red_mask 剩余红像素比例
  - `processing_time_ms_per_stage`：每步耗时
- 增加 `warnings` 数组：纸张检测失败、IOPaint 不可用回退等
- 增加 `errors` 数组：致命错误
- 底部折叠"处理日志"展示

**验收**：
- API 返回 JSON 含 quality_signals
- warnings 区分"非致命"和"致命"
- 前端用颜色徽章展示指标

---

## 五、B 阶段暂缓事项

| 暂缓事项 | 为什么先不做 | 什么条件下可以进入 B 阶段 |
|---------|------------|------------------------|
| OCR 保护（PaddleOCR/EasyOCR） | 引入新依赖 + 调试空间爆炸 + Paddle MPS 不稳 | A 阶段所有 5 个 Step 完成 + mask overlay 确认 mask 问题不是印刷误检时 |
| DIS-Handwriting-Remover | 需要 PyTorch 环境 + HF 权重下载 + 推理脚本自写 | A 阶段稳定 + 已有 20+ 张试卷的"传统 mask"效果数据做对比基线 |
| SegFormer / U-Net | 需要训练/微调 + GPU | 积累 ≥100 张标注 mask 后 |
| HandWritingEraser-Pytorch | PyTorch 1.x 旧依赖，会拖累整个项目环境 | 不引入，直接跳到 DIS 或 SegFormer |
| 商业 API（有道/TextIn） | 家庭隐私，孩子作业不能上传云端 | 仅用 1-2 张脱敏图片做一次性对照截图，写进文档 |
| 错题库 / PDF 导出 | 擦除效果都不稳定，先做下游没意义 | 擦除成功率 ≥70% 且 A+B 阶段完成 |
| 自训练模型 | 没有标注数据 | B 阶段积累 ≥100 张标注 mask |
| 账号/多用户系统 | 家庭场景不需要 | 不做 |

---

## 六、给 OpenCode 的下一步开发指令草案

直接复制发给 OpenCode：

```
## 任务：试卷宝 A 阶段 — 多后端 inpainting + debug 页增强

基线仓库：https://github.com/xymu2026-boop/exam-paper-tool
工作目录：~/Projects/exam-paper-tool

## 不要做
- 不改 mask.py 核心算法（保持当前 HSV + Canny + 连通域过滤）
- 不引入 OCR / DIS / SegFormer / 任何深度模型
- 不改前端框架
- 不调商业 API
- 不做错题/PDF导出

## 要做（5 Steps，每个独立 commit）

### Step 1: 多后端 inpainting
- pip install iopaint
- 新建 src/m1_image_engine/eraser_iopaint.py
- 函数: erase_with_iopaint(image_path, mask_path, output_path, model="lama", device="mps") -> dict
- 首次调用 lazy-load 模型，返回 {"ok": True/False, "duration_ms": ..., "device": ...}
- 失败不抛异常，返回 {"ok": False, "error": "..."}

### Step 2: eraser.py 重构成 backend 路由
- 拆出 eraser_opencv.py / eraser_bg_fill.py
- eraser.py 只做路由: backend="opencv"|"iopaint_lama"|"bg_fill"
- IOPaint 失败自动 fallback 到 opencv，记 warning

### Step 3: API 接受 backend 参数
- POST /api/papers/{id}/process?backend=opencv
- 不同 backend 输出到不同文件名（cleaned_opencv.jpg等）
- 返回 JSON 含 stages / outputs / quality_signals / warnings / errors

### Step 4: 质量信号
- mask_coverage_pct(combined_mask) -> float
- red_residual_pct(cleaned_image) -> float
- 加进 API 响应 quality_signals

### Step 5: 前端增强
- mask 标签页：4 联屏（原图/red/hw/combined overlay + 覆盖率%）
- 新增"对比"标签页：cleaned_opencv / cleaned_iopaint / cleaned_bg_fill 三栏
- 顶部 backend 下拉框 + 重新处理按钮
- 底部折叠处理日志

## 验收
- 上传红笔试卷，debug 页可切换 3 个 backend 肉眼对比
- mask 4 联屏可见，覆盖率%可见
- JSON 含 quality_signals 和 warnings
- IOPaint 不可用时自动回退
- 现有测试不挂

## 提交
每个 Step 一个 commit: feat(eraser): ... / refactor(eraser): ... / feat(api): ... / feat(quality): ... / feat(ui): ...
完成后开 PR
```

---

## 七、长文档生成经验总结

这次 Claude 写 697 行报告采用了"框架先行 → 分段追加 → 每段落盘 → 每段检查 → 最后补齐"的策略。我总结为今后的工作流规则：

**默认行为**：遇到 5000 字以上的报告/方案/调研时，不要一次性写完整全文。改为：

```
1. 框架先行：先写章节目录（只有 # 标题，不留正文），write_file 落盘
2. 分段追加：每次只写 1-2 章，用 patch 追加到文件末尾
3. 每段落盘：每写完一段，用 wc -l / wc -m / tail -3 确认内容正确写入
4. 每段检查：读一下刚写的段落，确认没有截断或乱码
5. 最后补齐：全部写完后，统一补充"总结"和"参考链接"章节
6. 终审：全文件读一遍，检查章节编号连续、链接有效
```

**触发条件**：
- 用户要求 ≥5000 字 → 自动采用分段写入
- 章节数 ≥8 个 → 自动采用分段写入
- 包含大量链接/表格 → 每写 3-4 个表格就落盘一次

---

*Deepseek 学习总结完成。不重新调研，直接进入 A 阶段开发。*
