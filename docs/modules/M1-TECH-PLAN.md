# M1 图像处理引擎 — 技术实现计划

> **模块编号**: M1
> **模块名称**: 图像处理引擎（Image Engine）
> **版本**: v1.0
> **日期**: 2026-05-31
> **性质**: 技术设计文档，指导后续编码实现

---

## 1. 模块职责

M1 图像处理引擎是一个纯 Python 图像处理库，输入一张手机拍摄的试卷照片，通过 8 步流水线输出预处理后的标准视角图像和手写内容已擦除的干净图像。

**本模块负责：**

- 读取原始图片（支持 JPG、PNG、HEIC 格式）并修正 EXIF 方向
- 将超大图片缩放到合理尺寸，防止内存溢出
- 检测试卷纸张轮廓并进行透视矫正
- 去除阴影和不均匀光照，增强印刷文字对比度
- 在 HSV 色彩空间中分离蓝色笔迹、红色笔迹和黑色/铅笔笔迹
- 生成手写区域的二值 mask（白色 = 手写，黑色 = 保留）
- 根据 mask 擦除手写内容，支持白色填充和图像修复两种模式
- 对处理结果进行多维度质量评分
- 提供独立 CLI 工具用于调试和批量处理

**本模块不负责：**

- 不访问数据库（M2 数据层的职责）
- 不提供 Web UI 或 HTTP 接口（M3 前端和 M4 后端的职责）
- 不生成 PDF 文件（M5 PDF 导出模块的职责）
- 不执行错题识别、内容分析或 OCR
- 不维护任何跨调用的状态或会话
- 不进行网络请求或外部 API 调用

---

## 2. 输入输出

### 2.1 输入

| 输入项 | 类型 | 来源 | 说明 |
|--------|------|------|------|
| `input_path` | `str` | 调用方传入 | 原始图片的绝对路径，格式为 `.jpg`、`.jpeg`、`.png` 或 `.heic` |
| `output_dir` | `str` | 调用方传入 | 输出目录的绝对路径，不存在时自动创建 |
| `mask_path` | `str` | 调用方传入（mask 子命令） | 手写 mask 图片的绝对路径 |
| `method` | `str` | 调用方传入（擦除时） | 擦除方法，值为 `'white'` 或 `'inpaint'` |
| `input_dir` | `str` | CLI batch 子命令 | 批量处理时的输入目录路径 |

**配置常量（模块内部硬编码）：**

- `MAX_LONG_EDGE = 3000`：缩放时长边像素上限
- `CLAHE_CLIP_LIMIT = 2.0`：CLAHE 对比度限制
- `CLAHE_TILE_SIZE = (8, 8)`：CLAHE 网格大小
- `ADAPTIVE_THRESH_BLOCK = 11`：自适应阈值邻域大小
- `ADAPTIVE_THRESH_C = 2`：自适应阈值常数偏移
- `BLUE_HUE_RANGE = (100, 130)`：蓝色笔迹 H 通道范围
- `RED_HUE_RANGE_1 = (0, 10)`：红色笔迹 H 通道范围下段
- `RED_HUE_RANGE_2 = (170, 180)`：红色笔迹 H 通道范围上段
- `MIN_SATURATION = 50`：颜色笔迹最低饱和度
- `MIN_VALUE = 50`：颜色笔迹最低亮度
- `DILATE_KERNEL_SIZE = 3`：mask 膨胀核大小
- `MIN_PAPER_AREA_RATIO = 0.3`：有效纸张面积占原图最小比例
- `QUALITY_THRESHOLD = 0.6`：质量分可打印门槛
- `JPEG_QUALITY = 95`：输出图片压缩质量

### 2.2 输出

| 输出项 | 类型 | 位置 | 说明 |
|--------|------|------|------|
| `processed.jpg` | 图片文件 | `{output_dir}/processed.jpg` | 预处理后图片（已矫正、去阴影、增强） |
| `cleaned.jpg` | 图片文件 | `{output_dir}/cleaned.jpg` | 手写擦除后的干净图片 |
| `ProcessResult` | `dataclass` | 函数返回值 | 包含 success、路径、质量分、警告和错误信息 |
| `mask.jpg` | 图片文件 | `output_path` 参数指定 | 调试模式下生成的二值 mask（白色 = 255，黑色 = 0） |

### 2.3 数据流图

```
input_path (.jpg/.heic)
         |
         v
+------------------+
| 1. 读取与解码     |
| (PIL + pillow-heif)|
+------------------+
         |
         v
   PIL Image (RGB)
         |
    +----+----+----+
    |    |    |
    v    v    v
+---------+ +---------+ +---------+
|2. EXIF  | |3. 长边  | |4. 纸张  |
|方向修正  | |缩放     | |检测     |
+---------+ +---------+ +----+----+
                             |
                             v
                      +-------------+
                      | 5. 透视矫正  |
                      +------+------+
                             |
                             v
+------------------+  +-------------+  +----------------+
| 6. 去阴影(CLAHE) |->|7. 二值化增强 |->| 8. mask 生成    |
| (LAB + CLAHE)    |  | (adaptive)  |  | (HSV + 形态学)  |
+------------------+  +-------------+  +--------+-------+
                                                |
                                                v
                                       +----------------+
                                       | 9. 区域填充/擦除|
                                       | (white/inpaint)|
                                       +--------+-------+
                                                |
                                                v
                                       +----------------+
                                       | 10. 质量评分    |
                                       | (三维加权)      |
                                       +--------+-------+
                                                |
                                                v
                                       +----------------+
                                       | ProcessResult  |
                                       | + 文件写入      |
                                       +----------------+
```

### 2.4 文件命名与目录约定

**模块内部输出规则：**

- `process_paper()` 在 `output_dir` 下固定生成两个文件：
  - `processed.jpg` —— 预处理后的标准图像
  - `cleaned.jpg` —— 手写擦除后的干净图像
- `generate_mask()` 输出路径由调用方的 `output_path` 参数决定，通常命名为 `mask.jpg`
- `apply_mask()` 输出路径由调用方的 `output_path` 参数决定，通常命名为 `cleaned_manual.jpg`

**模块内部不涉及但需知晓的边界约定：**

- 原图归档路径由 M4 后端在调用本模块前确定，格式为 `data/originals/{child_id}/{subject}/{timestamp}_{uuid4_short}.jpg`
- 输出目录在完整系统中通常对应 `data/processed/{paper_id}/`
- 这些路径由调用方（M4）构造并传入，本模块仅负责在指定目录中生成 `processed.jpg` 和 `cleaned.jpg`

---

## 3. 技术选型

### 3.1 opencv-python

**在模块中的作用：**

OpenCV 是图像处理流水线的计算核心，负责 Canny 边缘检测、轮廓查找、透视变换、CLAHE 自适应直方图均衡化、自适应阈值二值化、形态学操作（闭运算、膨胀）、HSV 色彩空间转换、图像修复（inpaint）以及 numpy 数组层面的像素操作。

**选择理由：**

- 计算机视觉领域事实标准，文档完备，社区庞大
- 内置 `cv2.findContours`、`cv2.getPerspectiveTransform`、`cv2.warpPerspective` 等纸张检测与矫正所需的原语，无需从零实现
- `cv2.inpaint` 提供开箱即用的图像修复算法（TELEA 和 NS 两种方法）
- 相比 scikit-image，OpenCV 在形态学操作和几何变换上速度更快、内存占用更可控
- 纯 Python 封装，无需编译，通过 pip 即可安装

**版本约束：** `opencv-python>=4.8.0,<5.0.0`

- 4.8.0 起修复了若干 HEIC 相关内存泄漏问题
- 4.x 系列 API 稳定，5.0 可能存在破坏性变更

**导入失败降级策略：**

`opencv-python` 是本模块的**硬依赖**，若导入失败则整个模块无法运行。在 `engine.py` 顶层执行 `import cv2`，失败时立即抛出 `ImportError` 并在错误信息中提示用户执行 `pip install opencv-python`。由于本模块是纯函数库，不存在无 OpenCV 的降级工作模式。

### 3.2 Pillow

**在模块中的作用：**

Pillow 负责图片的读取、解码、格式识别、EXIF 方向修正和最终写入保存。`PIL.Image.open()` 是统一的图片加载入口，`ImageOps.exif_transpose()` 修正手机拍摄时的旋转方向，`.save()` 输出 JPEG 文件。

**选择理由：**

- Python 图像 I/O 的标准方案，支持 JPG、PNG、BMP、TIFF 等常见格式
- 内置完善的 EXIF 解析，一步完成方向修正
- 相比 OpenCV 的 `cv2.imread()`，Pillow 在色彩空间处理（尤其是 JPEG 的 YCbCr 转换）上更不易出现色差
- API 简洁，与 OpenCV 的 numpy 数组互转方便（`np.array(img)` 和 `Image.fromarray()`）

**版本约束：** `Pillow>=10.0.0`

- 10.0.0 起改进了 HEIC 插件接口的兼容性
- 后续版本持续修复安全漏洞，不设上限但建议锁定小版本

**导入失败降级策略：**

Pillow 同样是**硬依赖**，导入失败直接抛出 `ImportError`。不存在降级路径。

### 3.3 numpy

**在模块中的作用：**

numpy 是本模块的底层数据载体。所有像素级操作都以 `np.ndarray` 进行传递：Pillow 读取的图片转为 numpy 数组后送入 OpenCV 处理；mask 是 `uint8` 类型的二维数组；质量评分中的像素统计、直方图计算、掩码逻辑运算均依赖 numpy 的向量化操作。

**选择理由：**

- OpenCV 的 Python 绑定原生返回 numpy 数组，两者无缝衔接
- 向量化像素统计（如 `np.sum(mask > 127)`）比纯 Python 循环快 2-3 个数量级
- 矩阵运算和广播机制极大简化了多通道 mask 合并逻辑
- 是 Python 科学计算生态的基石，稳定性和兼容性经过长期验证

**版本约束：** `numpy>=1.24.0,<2.0.0`

- 1.24.0 起支持更稳定的类型提示
- 2.0 系列改变了若干标量行为，可能引发 OpenCV 兼容性问题，故暂设上限

**导入失败降级策略：**

numpy 是**硬依赖**，导入失败直接抛出 `ImportError`。

### 3.4 pillow-heif

**在模块中的作用：**

为 Pillow 提供 HEIC/HEIF 格式解码能力，使 iPhone 默认格式照片可以直接被本模块读取。通过 `register_heif_opener()` 向 Pillow 注册 HEIF 解码器，之后 `Image.open()` 即可透明地打开 `.heic` 文件。

**选择理由：**

- iPhone 自 iOS 11 起默认以 HEIC 保存照片，家庭场景下这是最常见的原始格式
- `pillow-heif` 是 Pillow 官方推荐的 HEIF 插件，纯 Python 封装底层 libheif
- 相比将 HEIC 预先转换为 JPG 的外部工具方案，`pillow-heif` 在流程中直接集成，用户无感知
- 同类替代品 `pyheif` 维护状态较差且编译依赖复杂

**版本约束：** `pillow-heif>=0.14.0`

- 0.14.0 修复了若干 16 位 HEIF 图片的解码错误

**导入失败降级策略：**

`pillow-heif` 是**软依赖**，采用 Graceful Degradation 策略：

```python
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False
```

- 若导入失败，`HEIC_SUPPORTED` 标记为 `False`
- `load_image()` 函数在检测到 `.heic` 扩展名且 `HEIC_SUPPORTED == False` 时，不抛异常，而是返回 `ProcessResult(success=False, error="HEIC not supported: install pillow-heif")`
- 对 JPG/PNG 的处理完全不受影响
- 在 `warnings` 列表中附加 `"pillow-heif not installed, HEIC support disabled"` 提示

---

## 4. 核心算法/流程

### 4.1 `process_paper()` 主流程伪代码

```
function process_paper(input_path, output_dir):
    warnings = []
    
    # Step 1: 图片加载 + EXIF 方向修正
    try:
        img_pil = load_image(input_path)   # PIL Image, RGB
        img_pil = exif_transpose(img_pil)  # 修正旋转
    except Exception as e:
        return ProcessResult(success=False, error=f"load_failed: {e}")
    
    # Step 2: 长边缩放（防止 OOM）
    img_pil = resize_long_edge(img_pil, MAX_LONG_EDGE)
    
    # PIL -> numpy (RGB -> BGR for OpenCV)
    img = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
    
    # Step 3: 纸张检测
    quad = detect_paper(img)   # 返回四边形顶点或 None
    
    # Step 4: 透视矫正（容错）
    if quad is not None:
        area_ratio = polygon_area(quad) / (img.shape[0] * img.shape[1])
        if area_ratio >= MIN_PAPER_AREA_RATIO:
            img = warp_perspective(img, quad)
        else:
            warnings.append("paper_detection_failed: detected area too small")
    else:
        warnings.append("paper_detection_failed: skipped perspective correction")
    
    # Step 5: 去阴影（CLAHE）
    try:
        img = remove_shadow_clahe(img)
    except Exception as e:
        warnings.append(f"shadow_removal_failed: {e}")
    
    # Step 6: 二值化增强
    try:
        img = enhance_contrast(img)
    except Exception as e:
        warnings.append(f"contrast_enhancement_failed: {e}")
    
    # 保存预处理图
    ensure_dir(output_dir)
    processed_path = os.path.join(output_dir, "processed.jpg")
    cv2.imwrite(processed_path, img, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    
    # Step 7: 手写 mask 生成
    mask = generate_mask_internal(img)
    
    # Step 8: 擦除
    cleaned = apply_mask_internal(img, mask, method='white')
    cleaned_path = os.path.join(output_dir, "cleaned.jpg")
    cv2.imwrite(cleaned_path, cleaned, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    
    # Step 9: 质量评分
    quality_score = score_quality(img, cleaned, mask)
    
    # 判断 success
    success = True
    if quality_score < QUALITY_THRESHOLD:
        warnings.append(f"quality_score {quality_score:.2f} below threshold")
    
    return ProcessResult(
        success=success,
        processed_path=processed_path,
        cleaned_path=cleaned_path,
        quality_score=quality_score,
        warnings=warnings,
        error=None
    )
```

### 4.2 `generate_mask()` HSV 色彩空间策略伪代码

```
function generate_mask_internal(img_bgr):
    # img_bgr: OpenCV BGR 格式 numpy 数组
    
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    H = hsv[:,:,0]
    S = hsv[:,:,1]
    V = hsv[:,:,2]
    
    # --- 蓝色笔迹 mask ---
    blue_mask = (
        (H >= 100) AND (H <= 130) AND
        (S > MIN_SATURATION) AND
        (V > MIN_VALUE)
    )
    
    # --- 红色笔迹 mask ---
    # 红色在 HSV 中跨越 0度，需两段判断
    red_mask = (
        (
            ((H >= 0) AND (H <= 10)) OR
            ((H >= 170) AND (H <= 180))
        ) AND
        (S > MIN_SATURATION) AND
        (V > MIN_VALUE)
    )
    
    # --- 黑色/铅笔 mask ---
    # 策略：低饱和度 + 低亮度 区域，再通过形态学特征区分印刷体
    gray_mask = (
        (S < 80) AND
        (V < 200) AND
        (V > 30)       # 排除纯黑背景/边框
    )
    
    # 对 gray_mask 应用印刷体过滤：
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(gray_mask, 8)
    
    for each component i (skip background 0):
        area = stats[i, cv2.CC_STAT_AREA]
        width = stats[i, cv2.CC_STAT_WIDTH]
        height = stats[i, cv2.CC_STAT_HEIGHT]
        aspect_ratio = max(width, height) / max(min(width, height), 1)
        
        # 过滤规则（保守优先）：
        if area > 5000:
            gray_mask[labels == i] = 0          # 去除：疑似印刷文字块
        elif area < 20:
            gray_mask[labels == i] = 0          # 去除：噪点
        else:
            stroke_width = estimate_stroke_width(component_i)
            if stroke_width < 1.5 AND area > 1000:
                gray_mask[labels == i] = 0      # 去除：过细且大面积，疑似印刷体
    
    # --- 合并 mask ---
    combined_mask = blue_mask OR red_mask OR gray_mask
    combined_mask = combined_mask.astype(np.uint8) * 255
    
    # --- 形态学后处理 ---
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    combined_mask = cv2.morphologyEx(combined_mask, cv2.MORPH_CLOSE, kernel)
    combined_mask = cv2.dilate(combined_mask, kernel, iterations=1)
    
    return combined_mask   # uint8, 白色=255(手写), 黑色=0(保留)
```

### 4.3 `apply_mask()` 擦除逻辑伪代码

```
function apply_mask_internal(img_bgr, mask_gray, method):
    if mask_gray.dtype != np.uint8:
        mask_gray = mask_gray.astype(np.uint8)
    
    if method == 'white':
        # 方式 A：白色填充（默认，适合白底试卷）
        result = img_bgr.copy()
        result[mask_gray > 127] = (255, 255, 255)
        return result
        
    elif method == 'inpaint':
        # 方式 B：图像修复（适合复杂背景、网格底纹）
        inpaint_mask = (mask_gray > 127).astype(np.uint8) * 255
        result = cv2.inpaint(img_bgr, inpaint_mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
        return result
        
    else:
        raise ValueError(f"unknown method: {method}")
```

**两种方法对比：**

| 维度 | `'white'` 白色填充 | `'inpaint'` 图像修复 |
|------|-------------------|---------------------|
| 速度 | 极快（纯数组赋值） | 较慢（逐像素扩散） |
| 白底试卷效果 | 完美，无伪影 | 可能残留修复痕迹 |
| 网格/底纹试卷效果 | 会破坏网格线 | 较好，能延续背景纹理 |
| 实现复杂度 | 极简 | 需调参（半径、算法） |
| 默认策略 | 默认 | 备选 |

### 4.4 `score_quality()` 质量评分伪代码

```
function score_quality(original_bgr, cleaned_bgr, mask_gray):
    # original_bgr: 预处理后图像（擦除前）
    # cleaned_bgr:  擦除后图像
    # mask_gray:    手写 mask
    
    # --- 维度 1：擦除覆盖率（权重 0.3）---
    mask_bool = mask_gray > 127
    if np.sum(mask_bool) == 0:
        erase_coverage = 1.0   # 无手写可擦，满分
    else:
        cleaned_white = np.all(cleaned_bgr >= 240, axis=2)
        erased_pixels = np.sum(mask_bool AND cleaned_white)
        total_mask_pixels = np.sum(mask_bool)
        erase_coverage = erased_pixels / total_mask_pixels
    
    # --- 维度 2：题干保留率（权重 0.5，最关键）---
    keep_bool = NOT mask_bool
    if np.sum(keep_bool) == 0:
        text_preservation = 0.0
    else:
        diff = cv2.absdiff(original_bgr, cleaned_bgr)
        diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        changed_pixels = np.sum((diff_gray > 15) AND keep_bool)
        total_keep_pixels = np.sum(keep_bool)
        change_ratio = changed_pixels / total_keep_pixels
        text_preservation = max(0.0, 1.0 - change_ratio * 10)
    
    # --- 维度 3：视觉干净度（权重 0.2）---
    cleaned_gray = cv2.cvtColor(cleaned_bgr, cv2.COLOR_BGR2GRAY)
    
    # 3a: 白色纯度
    white_ratio = np.sum(cleaned_gray >= 250) / cleaned_gray.size
    
    # 3b: 孤立噪点数量
    inverted = 255 - cleaned_gray
    _, binary = cv2.threshold(inverted, 15, 255, cv2.THRESH_BINARY)
    num_labels, _, stats, _ = cv2.connectedComponentsWithStats(binary, 8)
    noise_count = 0
    for i in 1 to num_labels-1:
        area = stats[i, cv2.CC_STAT_AREA]
        if area < 50:
            noise_count += 1
    noise_score = max(0.0, 1.0 - noise_count / 500)
    
    cleanliness = 0.6 * white_ratio + 0.4 * noise_score
    
    # --- 综合加权 ---
    score = 0.3 * erase_coverage + 0.5 * text_preservation + 0.2 * cleanliness
    score = float(np.clip(score, 0.0, 1.0))
    return score
```

### 4.5 错误处理决策树

```
[开始]
  |
  +- 图片加载失败（格式不支持 / 文件损坏 / 路径错误）
  |     +- -> success=False, error="load_failed: 具体原因"
  |        （流程终止，不生成任何文件）
  |
  +- HEIC 格式但 pillow-heif 未安装
  |     +- -> success=False, error="HEIC not supported: install pillow-heif"
  |        （流程终止）
  |
  +- 图片加载成功
  |     |
  |     +- EXIF 修正失败
  |     |     +- -> warning 记录，继续（极少发生）
  |     |
  |     +- 缩放成功
  |     |     |
  |     |     +- 纸张检测失败 / 四边形面积过小
  |     |     |     +- -> warning 记录，跳过透视矫正，继续后续步骤
  |     |     |
  |     |     +- 透视矫正成功
  |     |           +- -> 继续
  |     |
  |     +- 去阴影失败（CLAHE 异常）
  |     |     +- -> warning 记录，跳过，使用原图继续
  |     |
  |     +- 二值化增强失败
  |     |     +- -> warning 记录，跳过，使用原图继续
  |     |
  |     +- 预处理图保存失败（磁盘满 / 权限不足）
  |     |     +- -> success=False, error="write_failed: 具体原因"
  |     |        （流程终止）
  |     |
  |     +- mask 生成成功（mask 可能为空，即无手写 detected）
  |     |     |
  |     |     +- mask 为空（全黑）
  |     |     |     +- -> warning 记录 "no_handwriting_detected",
  |     |     |        cleaned = processed，继续评分
  |     |     |
  |     |     +- mask 非空 -> 正常擦除
  |     |
  |     +- 擦除失败（mask 格式异常）
  |     |     +- -> success=False, error="erase_failed: 具体原因"
  |     |
  |     +- cleaned 图保存失败
  |     |     +- -> success=False, error="write_failed: 具体原因"
  |     |
  |     +- 质量评分
  |           |
  |           +- score >= 0.6 -> success=True
  |           +- score < 0.6 -> success=True（但带 quality warning）
  |                 # 注意：质量低不视为失败，只视为 warning，
  |                 # 由上层（M4）决定是否接受或重新处理
```

**关键原则：**

- **致命错误**（加载失败、保存失败、HEIC 不支持）：`success=False`，流程终止
- **可恢复错误**（纸张检测失败、去阴影失败、二值化失败）：记录 `warning`，跳过该步骤，继续后续流程
- **质量不佳**（`quality_score < 0.6`）：`success=True`，但附加 warning，将决策权交给调用方
- **空 mask**：视为正常情况（可能试卷本就无手写），不失败

---

## 5. 接口设计

### 5.1 函数签名（与 INTERFACE-CONTRACT.md 4.1 完全一致）

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcessResult:
    """图像处理结果"""
    success: bool
    processed_path: Optional[str] = None  # 预处理后图片路径
    cleaned_path: Optional[str] = None    # 擦除后图片路径
    quality_score: float = 0.0            # 0.0-1.0, >=0.6 视为可打印
    warnings: list[str] = None            # 处理过程中的警告
    error: Optional[str] = None           # 失败时的错误信息


def process_paper(input_path: str, output_dir: str) -> ProcessResult:
    """
    处理单张试卷图片。

    Args:
        input_path: 原始图片的绝对路径
        output_dir: 输出目录的绝对路径（会在其中生成 processed.jpg 和 cleaned.jpg）

    Returns:
        ProcessResult 数据类

    处理流程:
        1. EXIF 方向修正
        2. 缩放到合理尺寸（长边不超过 3000px）
        3. 纸张检测 + 透视矫正
        4. 去阴影（CLAHE）
        5. 二值化增强
        6. 手写 mask 生成
        7. 区域填充（擦除）
        8. 质量评分

    不变量:
        - 不修改 input_path 指向的原图
        - output_dir 不存在时自动创建
        - 失败时 success=False, error 字段有描述
    """


def generate_mask(input_path: str, output_path: str) -> bool:
    """
    仅生成手写 mask（用于调试和人工修正场景）。

    Args:
        input_path: 预处理后的图片路径
        output_path: mask 图片输出路径（白色=手写区域，黑色=保留区域）

    Returns:
        是否成功
    """


def apply_mask(input_path: str, mask_path: str, output_path: str, method: str = 'white') -> bool:
    """
    根据 mask 擦除手写内容。

    Args:
        input_path: 预处理后的图片路径
        mask_path: mask 图片路径
        output_path: 擦除结果输出路径
        method: 'white'(白色填充) | 'inpaint'(图像修复)

    Returns:
        是否成功
    """
```

### 5.2 函数详细说明

#### `process_paper(input_path: str, output_dir: str) -> ProcessResult`

| 参数 | 类型 | 是否必填 | 说明 |
|------|------|----------|------|
| `input_path` | `str` | 是 | 原始图片绝对路径。支持 `.jpg`、`.jpeg`、`.png`、`.heic`（需 pillow-heif） |
| `output_dir` | `str` | 是 | 输出目录绝对路径。函数内部自动创建（含递归） |

| 返回值字段 | 类型 | 说明 |
|-----------|------|------|
| `success` | `bool` | `True` 表示流程完成（即使质量分低）；`False` 表示致命错误 |
| `processed_path` | `Optional[str]` | 预处理图保存的绝对路径，失败时为 `None` |
| `cleaned_path` | `Optional[str]` | 擦除图保存的绝对路径，失败时为 `None` |
| `quality_score` | `float` | 0.0–1.0 的综合质量评分，未执行评分时默认 0.0 |
| `warnings` | `list[str]` | 非致命问题的文本列表，成功时可能非空 |
| `error` | `Optional[str]` | 失败时的可读错误描述，成功时为 `None` |

**异常处理策略：**

- 函数内部捕获所有异常，不向上抛出
- 返回 `ProcessResult(success=False, error=str(e))` 作为统一的错误出口
- 调用方无需 try/except，只需判断 `result.success`

#### `generate_mask(input_path: str, output_path: str) -> bool`

| 参数 | 类型 | 是否必填 | 说明 |
|------|------|----------|------|
| `input_path` | `str` | 是 | 预处理后的图片路径。由于 mask 生成依赖去阴影和增强后的清晰图像，输入应为 `processed.jpg` 而非原始照片 |
| `output_path` | `str` | 是 | mask 输出路径，通常以 `.jpg` 结尾 |

| 返回值 | 说明 |
|--------|------|
| `True` | mask 成功生成并写入 `output_path` |
| `False` | 任何步骤失败（图片读取失败、写入磁盘失败等） |

**异常处理策略：**

- 内部捕获所有异常，返回 `False`
- 不暴露具体错误原因给调用方，调用方在调试场景可查看 stderr 日志
- 输出 mask 格式：单通道灰度图，白色像素值 = 255（手写区域），黑色像素值 = 0（保留区域）

#### `apply_mask(input_path: str, mask_path: str, output_path: str, method: str = 'white') -> bool`

| 参数 | 类型 | 是否必填 | 说明 |
|------|------|----------|------|
| `input_path` | `str` | 是 | 预处理后的图片路径 |
| `mask_path` | `str` | 是 | mask 图片路径（白色 = 待擦除，黑色 = 保留） |
| `output_path` | `str` | 是 | 擦除结果输出路径 |
| `method` | `str` | 否 | 默认值 `'white'`。可选 `'inpaint'` |

| 返回值 | 说明 |
|--------|------|
| `True` | 擦除成功，结果写入 `output_path` |
| `False` | 任何步骤失败 |

**异常处理策略：**

- `method` 不是 `'white'` 或 `'inpaint'` 时，内部抛出 `ValueError`，被外层捕获后返回 `False`
- mask 与图片尺寸不匹配时，自动将 mask resize 到图片尺寸（最近邻插值）
- 内部捕获所有异常，返回 `False`

### 5.3 CLI 接口

模块提供独立命令行入口，用于开发调试和批量处理场景。

```bash
# 处理单张图片
python -m src.m1_image_engine.cli process input.jpg output_dir/

# 仅生成 mask
python -m src.m1_image_engine.cli mask input.jpg mask.jpg

# 批量处理目录
python -m src.m1_image_engine.cli batch input_dir/ output_dir/
```

**子命令详细说明：**

| 子命令 | 参数 | 功能 |
|--------|------|------|
| `process` | `input_path` `output_dir` | 调用 `process_paper()`，在 `output_dir` 生成 `processed.jpg` 和 `cleaned.jpg`。终端打印 `ProcessResult` 的 JSON 表示 |
| `mask` | `input_path` `output_path` | 调用 `generate_mask()`，生成 mask 图。终端打印 `True` 或 `False` |
| `batch` | `input_dir` `output_dir` | 遍历 `input_dir` 下所有图片文件（`.jpg`、`.jpeg`、`.png`、`.heic`），对每个文件调用 `process_paper()`，输出到 `output_dir/{filename_noext}/`。终端打印批量统计（成功数/总数/平均质量分） |

**CLI 错误处理：**

- 命令行参数缺失时，使用 `argparse` 打印帮助信息并退出（返回码 2）
- 单张处理失败时打印错误 JSON，继续下一张（batch 模式）
- batch 模式结束时返回码 0（即使部分失败），由终端输出中的统计数字告知用户整体结果

### 5.4 错误处理约定

本模块采用**返回值驱动**的错误处理风格，不抛异常给调用方：

```python
# 调用方代码范式（M4 后端使用方式）
result = process_paper(input_path, output_dir)
if not result.success:
    # 记录错误，更新数据库状态为 failed
    db.update_paper_status(paper_id, status='failed', error_message=result.error)
else:
    # 保存路径和质量分
    db.update_paper_status(
        paper_id,
        status='processed',
        processed_path=result.processed_path,
        cleaned_path=result.cleaned_path,
        quality_score=result.quality_score
    )
    # 如果有 warnings，记录到日志
    for warning in (result.warnings or []):
        logger.warning(f"paper {paper_id}: {warning}")
```

---

## 6. 数据结构

### 6.1 `ProcessResult` 数据类

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProcessResult:
    """图像处理结果

    这是 M1 模块与外部调用方（主要是 M4 后端）之间的核心通信契约。
    所有字段均有明确的默认值，确保即使部分流程未执行也能安全访问。
    """
    success: bool
    """流程是否成功完成。True 表示生成了有效输出文件（即使质量分低）；
    False 表示发生致命错误，output 字段可能为 None。"""

    processed_path: Optional[str] = None
    """预处理后图片的绝对文件系统路径。
    仅当 success=True 时保证非 None 且文件存在。"""

    cleaned_path: Optional[str] = None
    """手写擦除后图片的绝对文件系统路径。
    仅当 success=True 时保证非 None 且文件存在。"""

    quality_score: float = 0.0
    """综合质量评分，范围 [0.0, 1.0]。
    >= 0.6 视为可打印质量。
    若评分步骤未执行（流程提前失败），默认值为 0.0。"""

    warnings: list[str] = None
    """处理过程中遇到的非致命问题的文本列表。
    例如纸张检测失败、去阴影跳过、质量分偏低等。
    可能为 None，调用方应使用 `result.warnings or []` 访问。"""

    error: Optional[str] = None
    """失败时的可读错误描述。
    仅当 success=False 时有意义，成功时为 None。"""
```

### 6.2 内部流水线数据格式转换

模块内部在不同处理阶段使用两种不同的图像表示，需要明确的转换边界：

| 阶段 | 数据格式 | 色彩空间 | 值域 | 负责模块 |
|------|----------|----------|------|----------|
| 加载 | `PIL.Image` | RGB | uint8 [0, 255] | `utils.py` |
| EXIF 修正 | `PIL.Image` | RGB | uint8 [0, 255] | `preprocess.py` |
| 缩放 | `PIL.Image` | RGB | uint8 [0, 255] | `preprocess.py` |
| -> OpenCV 转换 | `np.ndarray` | BGR | uint8 [0, 255] | `preprocess.py`（`cv2.cvtColor(..., COLOR_RGB2BGR)`） |
| 纸张检测 | `np.ndarray` | BGR | uint8 [0, 255] | `preprocess.py` |
| 透视矫正 | `np.ndarray` | BGR | uint8 [0, 255] | `preprocess.py` |
| 去阴影 | `np.ndarray` | BGR | uint8 [0, 255] | `preprocess.py` |
| 二值化增强 | `np.ndarray` | BGR | uint8 [0, 255] | `preprocess.py` |
| 保存预处理图 | `np.ndarray` -> `PIL.Image` | RGB | uint8 [0, 255] | `preprocess.py`（`COLOR_BGR2RGB` 后 `Image.fromarray()`） |
| mask 生成 | `np.ndarray` | HSV 中间态 / Gray 输出 | uint8 [0, 255] | `mask.py` |
| 擦除 | `np.ndarray` | BGR | uint8 [0, 255] | `eraser.py` |
| 保存擦除图 | `np.ndarray` -> `PIL.Image` | RGB | uint8 [0, 255] | `eraser.py` |

**转换规范：**

- PIL 到 OpenCV：`np.array(pil_img)` 得到 RGB 数组，再 `cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2BGR)` 转为 BGR
- OpenCV 到 PIL：`cv2.cvtColor(bgr_arr, cv2.COLOR_BGR2RGB)` 后 `Image.fromarray(rgb_arr)`
- 任何情况下不直接使用 `cv2.imread()` 或 `cv2.imwrite()` 加载/保存，而是通过 PIL 统一处理 I/O，避免 HEIC 和色彩空间陷阱

### 6.3 Mask 表示约定

模块内部和外部的 mask 均遵循严格的像素语义：

- **白色像素（值 = 255）**：手写区域，需要被擦除
- **黑色像素（值 = 0）**：保留区域，印刷文字、表格、背景等
- **不允许存在中间灰度**：`generate_mask()` 输出前进行二值化，`threshold=127`
- **单通道灰度图**：shape 为 `(H, W)`，`dtype=np.uint8`
- **尺寸对齐**：mask 必须与对应图像的宽度和高度完全一致

此约定在 `generate_mask()` 的输出、`apply_mask()` 的输入以及质量评分的 `mask` 参数中保持一致。

### 6.4 内部配置常量

以下常量定义在 `engine.py` 或专门的 `config.py` 中，作为模块级全局变量，不暴露给调用方：

```python
# 图像尺寸
MAX_LONG_EDGE = 3000          # 缩放长边上限
JPEG_QUALITY = 95             # 输出 JPEG 质量

# CLAHE 去阴影
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = (8, 8)

# 自适应阈值
ADAPTIVE_THRESH_BLOCK = 11
ADAPTIVE_THRESH_C = 2

# HSV 颜色范围
BLUE_HUE_RANGE = (100, 130)
RED_HUE_RANGE_1 = (0, 10)
RED_HUE_RANGE_2 = (170, 180)
MIN_SATURATION = 50
MIN_VALUE = 50

# 形态学
DILATE_KERNEL_SIZE = 3

# 纸张检测
MIN_PAPER_AREA_RATIO = 0.30   # 检测到的四边形面积至少占原图 30%

# 质量评分
QUALITY_THRESHOLD = 0.60      # 可打印门槛
ERASE_COVERAGE_WEIGHT = 0.30
TEXT_PRESERVATION_WEIGHT = 0.50
CLEANLINESS_WEIGHT = 0.20

# mask 印刷体过滤
MIN_HANDWRITING_AREA = 20      # 手写笔画最小面积（px）
MAX_HANDWRITING_AREA = 5000    # 疑似印刷文字块面积上限（px）
PRINT_STROKE_WIDTH_THRESH = 1.5  # 印刷体笔画宽度阈值（px）
NOISE_COUNT_THRESH = 500       # cleanliness 评分中的噪点数量阈值
```

---

## 7. 测试策略

### 7.1 测试分层

| 层级 | 测试文件 | 测试对象 | 方法 |
|------|----------|----------|------|
| 单元测试 | `test_preprocess.py` | `preprocess.py` 中的每个子步骤 | 合成图像 + 断言数组变化 |
| 单元测试 | `test_mask.py` | `mask.py` 的颜色分割和形态学 | 纯色块图像 + 断言 mask 形状 |
| 单元测试 | `test_eraser.py` | `eraser.py` 的两种擦除方法 | 合成图 + mask + 断言像素值 |
| 单元测试 | `test_quality.py` | `quality.py` 的三维评分 | 构造已知质量差异的图像对 + 断言分数范围 |
| 端到端测试 | `test_engine_e2e.py` | `process_paper()` 完整流程 | 真实样本 + 人工检查输出图 + 断言 success/quality_score |
| CLI 测试 | `test_cli.py` | `cli.py` 的三个子命令 | 使用 `subprocess.run` 调用命令行，断言返回码和输出文件 |

### 7.2 测试数据要求

测试样本存放于 `data/samples/`（该目录不进 git，由开发者在本地准备），至少包含以下 5 类真实场景：

| 编号 | 场景 | 要求 | 测试重点 |
|------|------|------|----------|
| S1 | 铅笔书写 | 真实小学试卷，2B 铅笔填涂和书写 | 黑色/灰色 mask 生成、笔画宽度过滤 |
| S2 | 黑色水笔 | 常见 0.5mm 黑色签字笔书写 | 黑色笔迹与印刷文字区分 |
| S3 | 蓝色水笔 | 蓝色中性笔书写的数学试卷 | HSV 蓝色通道分割准确性 |
| S4 | 红笔批改 | 教师红色笔迹批改的语文试卷 | HSV 红色通道分割（跨 0度 处理） |
| S5 | 混合书写 | 同时包含铅笔、黑笔、蓝笔、红笔的试卷 | 多颜色 mask 合并逻辑 |

**扩展场景（建议补充）：**

| 编号 | 场景 | 测试重点 |
|------|------|----------|
| S6 | 倾斜/透视拍摄 | 纸张检测和透视矫正的鲁棒性 |
| S7 | 阴影/光照不均 | CLAHE 去阴影效果 |
| S8 | 带网格/底纹的数学卷 | inpaint 方法 vs white 方法对比 |
| S9 | HEIC 格式（iPhone 拍摄）| pillow-heif 集成、EXIF 方向修正 |
| S10 | 无手写的空白卷 | 空 mask 处理、质量分应接近 1.0 |

### 7.3 关键测试场景与断言

**预处理测试：**

- `test_exif_transpose()`：构造带 EXIF Orientation=6（旋转 90度）的合成图，断言处理后尺寸对调
- `test_resize_long_edge()`：输入 6000x4000 图片，断言输出长边为 3000，短边为 2000（保持比例）
- `test_paper_detection_success()`：在白色背景上放置一个黑色边框的四边形，断言检测到的 quad 顶点数 = 4
- `test_paper_detection_failure_fallback()`：输入无纸张特征的图片（纯噪声），断言返回 warning 且不崩溃
- `test_perspective_area_guard()`：构造小面积四边形（占原图 10%），断言跳过矫正并记录 warning

**Mask 生成测试：**

- `test_blue_pen_detected()`：在白色画布上绘制纯蓝色矩形，断言对应区域 mask = 255
- `test_red_pen_detected()`：绘制纯红色矩形，断言对应区域 mask = 255
- `test_printed_text_preserved()`：在画布上绘制黑色细横线（模拟印刷文字，笔画宽度 1px，大面积连通域），断言 mask = 0
- `test_table_lines_preserved()`：绘制黑色表格线（长宽比极大），断言 mask = 0

**擦除测试：**

- `test_white_fill()`：输入彩色图 + 中心白色 mask，断言中心区域变为 (255, 255, 255)
- `test_inpaint_no_crash()`：输入彩色图 + mask，断言不崩溃且输出图尺寸不变
- `test_invalid_method()`：传入 `method='blur'`，断言返回 `False`

**质量评分测试：**

- `test_perfect_clean_score()`：original = cleaned，mask 全黑，断言 quality_score 约等于 1.0
- `test_poor_erase_score()`：mask 全白但 cleaned 无变化，断言 erase_coverage 约等于 0，总分 < 0.3
- `test_text_damage_score()`：cleaned 在非 mask 区域有大量像素变化，断言 text_preservation 低，总分 < 0.4

**端到端测试：**

- `test_all_samples_processable()`：对全部样本调用 `process_paper()`，断言全部返回 `ProcessResult`（不崩溃）
- `test_success_rate()`：对全部样本统计 `success=True` 的比例，断言 >= 80%
- `test_quality_gate()`：对全部样本统计 `quality_score >= 0.6` 的比例，断言 >= 60%

### 7.4 质量门禁

模块验收必须同时满足以下量化指标：

| 门禁 | 指标 | 阈值 | 验证方式 |
|------|------|------|----------|
| 稳定性 | 样本处理不崩溃率 | 100%（10/10 返回结果）| `test_all_samples_processable` |
| 成功率 | `success=True` 比例 | >= 80% | `test_success_rate` |
| 质量合格率 | `quality_score >= 0.6` 比例 | >= 60% | `test_quality_gate` |
| 单元测试覆盖率 | 行覆盖率 | >= 70% | `pytest --cov=src.m1_image_engine` |
| CLI 可用性 | 三个子命令均可执行 | 100% | `test_cli.py` |
| 零外部依赖 | 不 import M2/M3/M4/M5 | 100% | 静态检查 + import 测试 |

### 7.5 CI/CD 集成

由于 `data/samples/` 不进 git，CI 环境无法直接运行端到端测试。采取以下策略：

- **单元测试层**：全部使用合成图像，不依赖真实样本，在 CI 中 100% 运行
- **端到端测试层**：标记为 `pytest.mark.skipif(not os.path.exists("data/samples"), reason="samples not available")`，仅在本地开发环境运行
- **预提交钩子**：`black` 格式化 + `flake8` 风格检查 + `mypy` 类型检查
- **CI 流水线**：`pytest tests/m1/test_*.py -m "not sample"` 运行纯合成图测试，保证代码合并时无回归
- **发布前检查清单**：开发者在本地对完整样本集运行 `pytest tests/m1/ -v`，确认全部通过后方可标记模块完成

---

## 8. 风险与对策

### 8.1 风险矩阵

| 编号 | 风险描述 | 概率 | 影响 | 严重度 |
|------|----------|------|------|--------|
| R1 | 黑色手写与印刷文字无法有效区分，导致误删题干 | 高 | 极高 | 关键 |
| R2 | 纸张检测在复杂背景 / 深色桌面上失败 | 中 | 中 | 重要 |
| R3 | HEIC 格式兼容性问题（pillow-heif 安装失败或解码异常） | 中 | 中 | 重要 |
| R4 | 透视矫正过度裁剪或变形（检测到的四边形非真实纸张边界） | 低 | 高 | 重要 |
| R5 | 红笔批改区域跨 H=0度 的 HSV 分割遗漏 | 低 | 中 | 一般 |

### 8.2 逐风险分析

#### R1：黑色手写与印刷文字无法有效区分

**详细说明：**

这是本模块**最困难的技术问题**。印刷文字和黑色水笔/铅笔在灰度特征上几乎不可分：两者都是深色、低饱和度。当前策略依赖连通域面积、长宽比和笔画宽度进行启发式过滤，但这些规则在面对“印刷体填空横线 + 手写答案”时极易失效。误删题干的后果是直接破坏试卷内容，比漏擦手写更严重（模块核心原则是“宁可漏擦，不可误删”）。

**缓解策略：**

- 第一版实现采用**极端保守策略**：对于黑色/灰色区域，只有当连通域特征明确符合手写笔画（中等面积、非极端长宽比、笔画宽度 2-5px）时才标记为擦除
- 大面积黑色块（如印刷文字段落、黑色标题）一律保留
- 在质量评分的 `text_preservation` 维度赋予最高权重（0.5），即使漏擦较多手写，只要题干完整，总分仍可能及格
- 收集失败案例，建立本地样本库，用于后续阈值调优

**Fallback 计划：**

- 若第一版的保守策略导致漏擦过多（大量手写残留），质量分普遍低于 0.6，则在第二版中引入轻量级的机器学习分类器（如基于连通域特征的随机森林或 MobileNet 微调的笔画分类器）
- 分类器作为可选增强，保持当前启发式规则作为默认路径，确保无模型时仍可运行

#### R2：纸张检测在复杂背景上失败

**详细说明：**

`cv2.Canny()` + `cv2.findContours()` 的纸张检测假设试卷是画面中最大的四边形轮廓。当试卷放在花纹桌布、深色木质桌面或与其他纸张重叠时，边缘检测可能找到错误的轮廓，或根本找不到四边形。

**缓解策略：**

- 使用面积占比守卫（`MIN_PAPER_AREA_RATIO = 0.3`）：检测到的四边形面积必须至少占原图 30%，否则视为误判
- 对轮廓进行多边形逼近（`cv2.approxPolyDP`），仅接受逼近后为 4 个顶点的轮廓
- 按轮廓面积降序排列，尝试前 3 个最大轮廓，取第一个满足四边形条件的

**Fallback 计划：**

- 若纸张检测失败，**跳过透视矫正**，直接对原图进行后续处理（去阴影、二值化、mask 生成）
- 记录 warning `"paper_detection_failed: skipped perspective correction"`，不阻塞整体流程
- 调用方（M4）可将带 warning 的结果呈现给用户，提示“检测到倾斜，建议重新拍摄”

#### R3：HEIC 格式兼容性问题

**详细说明：**

iPhone 默认以 HEIC 保存照片。`pillow-heif` 依赖底层 libheif C 库，在某些平台（如 Alpine Linux、ARM 架构）上编译或运行可能出现问题。此外，iOS 更新可能引入新的 HEIF 编码特性，导致旧版本 `pillow-heif` 解码失败。

**缓解策略：**

- `pillow-heif` 作为**软依赖**，graceful degradation
- 安装时通过 `requirements.txt` 锁定 `pillow-heif>=0.14.0`
- 加载图片时先检查文件扩展名，`.heic` 文件在 `HEIC_SUPPORTED=False` 时直接返回友好错误，不尝试用错误解码器打开

**Fallback 计划：**

- 在 M4 后端或用户文档中提示：若 HEIC 处理失败，可先在手机设置中将相机格式改为“兼容性最佳”（JPEG）
- 提供独立的 HEIC->JPG 转换工具脚本（基于 `pyheif` 或系统 `heif-convert`），作为模块外的预处理选项

#### R4：透视矫正过度裁剪或变形

**详细说明：**

即使检测到了四边形，该四边形可能并非试卷真实边界（例如检测到了画面中一本书的边缘、桌面的矩形花纹）。此时进行透视矫正会导致试卷内容被拉伸、裁剪或嵌入到错误的外框中。

**缓解策略：**

- 面积占比守卫（四边形面积 >= 原图 30%）过滤掉过小的误判区域
- 长宽比检查：矫正后的输出长宽比应在合理范围（0.5 到 2.0 之间），超出范围视为异常
- 计算四边形各内角，接近直角的四边形（角度在 70度-110度 之间）才被视为有效纸张

**Fallback 计划：**

- 任何守卫条件不满足时，放弃透视矫正，记录 warning，继续使用未矫正的原图
- 在 `ProcessResult.warnings` 中明确告知调用方“跳过了透视矫正”，由上层决定是否提示用户重拍

#### R5：红笔批改区域跨 H=0度 的 HSV 分割遗漏

**详细说明：**

红色在 HSV 色彩空间中 H 通道接近 0度，这意味着纯红色的 H 值分布在 0 附近和 180 附近（因为 Hue 是环形角度）。如果仅检测 H在[0, 10] 而忽略 [170, 180]，会遗漏部分偏品红的红色笔迹。但将两段范围合并后，也可能引入肤色、棕色等干扰。

**缓解策略：**

- 必须同时检测两段范围：`[0, 10]` 和 `[170, 180]`，使用逻辑 OR 合并
- 配合饱和度 `S > 50` 和亮度 `V > 50` 过滤低饱和度的红色噪声（如肤色通常 S < 40）
- 形态学膨胀 2-3px 覆盖红色笔迹边缘的抗锯齿过渡色

**Fallback 计划：**

- 若测试中发现特定红色笔（如荧光红、暗红）遗漏，可动态扩展 HSV 范围表，将常见红笔的色相范围加入配置文件
- 漏擦的红色笔迹可通过质量评分的 `erase_coverage` 维度反映为低分，由调用方提示用户“可能存在未擦除的批改痕迹”

### 8.3 已知硬问题汇总

| 问题 | 当前策略 | 后续优化方向 |
|------|----------|-------------|
| 黑色手写 vs 印刷文字 | 连通域面积 + 笔画宽度启发式，保守过滤 | 引入轻量笔画分类器（随机森林 / CNN） |
| 纸张检测失败 | 跳过矫正，记录 warning，不阻塞 | 引入 Hough 直线检测作为四边形备选检测策略 |
| HEIC 兼容性 | pillow-heif 软依赖，失败时提示安装 | 预构建 wheel 包，减少编译依赖 |
| 网格底纹试卷 | 默认 white 方法会破坏网格，需手动切换 inpaint | 自动检测底纹（频率域分析），智能选择方法 |
| 阴影严重遮挡手写 | CLAHE 只能缓解均匀阴影，对局部强阴影效果有限 | 引入基于照度估计的阴影去除算法 |

---

*文档结束。本计划作为 M1 模块编码实现的唯一技术依据，所有实现代码必须与此文档保持一致。*
