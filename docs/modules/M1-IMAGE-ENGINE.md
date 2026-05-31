# M1: 图像处理引擎 — 开发任务卡

| 模块编号 | 状态 | 可并行 | 依赖 |
|----------|------|--------|------|
| M1 | 待开发 | ✅ | 无 |

---

## 模块定位

纯 Python 图像处理库，输入一张手机拍摄的试卷照片，输出预处理图和擦除图。

- **不访问数据库**
- **不依赖网络**
- **不依赖其他模块**
- 纯函数式，无状态
- 无 UI 依赖

可独立开发、独立测试、独立运行。其他模块（M4 后端）通过函数调用使用本模块。

---

## 前置阅读

开发前必须先阅读以下文档：

- `docs/INTERFACE-CONTRACT.md` 第四节 4.1（M1 接口定义，权威接口契约）
- `家庭版试卷宝需求总文档_v1.0.md` 主线2（图像处理）和主线3（擦除手写）

---

## 目录结构

```
src/m1_image_engine/
├── __init__.py        # 导出 process_paper, generate_mask, apply_mask, ProcessResult
├── engine.py          # 主入口，编排预处理→mask→擦除→评分
├── preprocess.py      # 预处理管线（EXIF/裁切/透视/去阴影/增强）
├── mask.py            # 手写 mask 生成
├── eraser.py          # 擦除逻辑（白色填充/inpaint）
├── quality.py         # 质量评分
├── cli.py             # CLI 入口
└── utils.py           # 工具函数（HEIC 加载、图片读写、路径处理等）
```

`__init__.py` 必须导出：

```python
from .engine import process_paper, ProcessResult
from .mask import generate_mask
from .eraser import apply_mask

__all__ = ['process_paper', 'generate_mask', 'apply_mask', 'ProcessResult']
```

---

## 核心接口（从 INTERFACE-CONTRACT.md 4.1 复制）

**位置**: `src/m1_image_engine/`
**入口**: `src/m1_image_engine/engine.py`
**依赖**: `opencv-python`, `Pillow`, `numpy`, `pillow-heif`
**特性**: 纯函数式，无状态，不访问数据库

```python
# === 主接口 ===

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

**CLI 入口**（用于独立测试）:

```bash
# 处理单张图片
python -m src.m1_image_engine.cli process input.jpg output_dir/

# 仅生成 mask
python -m src.m1_image_engine.cli mask input.jpg mask.jpg

# 批量处理目录
python -m src.m1_image_engine.cli batch input_dir/ output_dir/
```

---

## 实现要求

### 1. 预处理管线（`preprocess.py`）

按顺序执行以下步骤：

1. **EXIF 方向修正**: `PIL.ImageOps.exif_transpose()` 修正手机拍摄的旋转方向
2. **尺寸缩放**: 长边不超过 3000px（避免 OOM 与加速后续步骤）
3. **纸张检测**: `cv2.Canny()` + `cv2.findContours()` 找最大四边形轮廓
4. **透视矫正**: `cv2.getPerspectiveTransform()` + `cv2.warpPerspective()`
5. **去阴影**: 转 LAB 色彩空间，对 L 通道应用 `CLAHE`（自适应直方图均衡化）
6. **二值化增强**: `cv2.adaptiveThreshold(ADAPTIVE_THRESH_GAUSSIAN_C)` 提升对比度

**容错要求**：

- 如果纸张检测失败（找不到合理的四边形），**跳过透视矫正**，在 `warnings` 中记录 `"paper_detection_failed: skipped perspective correction"`
- 如果某一步出现异常但不致命，记录 warning 并继续

参考管线伪代码：

```python
def preprocess(input_path: str) -> tuple[np.ndarray, list[str]]:
    warnings = []
    img = load_image(input_path)              # 含 HEIC 处理
    img = exif_transpose(img)
    img = resize_long_edge(img, max_size=3000)
    quad = detect_paper(img)
    if quad is not None:
        img = warp_perspective(img, quad)
    else:
        warnings.append("paper_detection_failed: skipped perspective correction")
    img = remove_shadow_clahe(img)
    img = enhance_contrast(img)
    return img, warnings
```

---

### 2. 手写 Mask 生成（`mask.py`）

**核心策略**：在 HSV 色彩空间分离不同颜色的笔迹。

| 笔迹颜色 | HSV 范围 |
|----------|----------|
| 蓝色笔迹 | H∈[100,130], S>50, V>50 |
| 红色笔迹 | H∈[0,10] ∪ [170,180], S>50, V>50（红色横跨 H=0） |
| 黑色/铅笔 | 通过形态学特征区分印刷体和手写：笔画宽度、连通域面积、长宽比 |

**形态学后处理**：

- `cv2.morphologyEx(MORPH_CLOSE)` 闭合笔画内部小孔
- `cv2.dilate()` 膨胀 2-3px 覆盖边缘抗锯齿区域

**关键约束（必须遵守）**：

- ❌ **不能误删印刷文字**——宁可漏擦也不能误删题干
- ✅ 横线、表格线、坐标轴、印刷边框必须**完整保留**
- ✅ 对于无法确定的区域（彩色但形似印刷体），**不擦除**
- 第一版策略保守优先，可通过测试样本逐步调优阈值

返回的 mask 约定：**白色(255) = 待擦除手写区域，黑色(0) = 保留区域**。

---

### 3. 擦除（`eraser.py`）

支持两种擦除方法：

| method | 实现 | 适用场景 |
|--------|------|----------|
| `'white'` | 直接用白色 `(255,255,255)` 填充 mask 区域 | 白底试卷（默认） |
| `'inpaint'` | `cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)` | 复杂背景、网格底纹 |

**默认使用 `'white'`**——对白色背景试卷效果最好，速度快，无伪影。

```python
def apply_mask(input_path, mask_path, output_path, method='white') -> bool:
    img = cv2.imread(input_path)
    mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)
    if method == 'white':
        img[mask > 127] = (255, 255, 255)
    elif method == 'inpaint':
        img = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)
    else:
        raise ValueError(f"unknown method: {method}")
    cv2.imwrite(output_path, img)
    return True
```

---

### 4. 质量评分（`quality.py`）

综合评分 0.0–1.0，**>= 0.6 视为可打印**。

| 维度 | 含义 | 权重建议 |
|------|------|----------|
| 擦除覆盖率 | mask 区域被处理的比例 | 0.3 |
| 题干保留率 | 印刷文字区域未被影响的比例（关键，权重最高） | 0.5 |
| 视觉干净度 | 擦除后残留痕迹的程度（白色像素占比、孤立点数量） | 0.2 |

参考实现思路：

```python
def score_quality(original: np.ndarray, cleaned: np.ndarray, mask: np.ndarray) -> float:
    erase_coverage = compute_erase_coverage(cleaned, mask)
    text_preservation = compute_text_preservation(original, cleaned, mask)
    cleanliness = compute_cleanliness(cleaned)
    score = 0.3 * erase_coverage + 0.5 * text_preservation + 0.2 * cleanliness
    return float(np.clip(score, 0.0, 1.0))
```

---

## 测试要求

- 测试目录：`tests/m1/`
- 使用 `data/samples/` 下的真实图片测试（样本不进 git，本地准备）
- 至少覆盖以下场景：
  - 铅笔书写
  - 黑色水笔
  - 蓝色水笔
  - 红笔批改
  - 混合书写（多色共存）
  - 倾斜/透视拍摄
  - 阴影/光照不均
- 输出处理前后对比图到 `tests/m1/output/`，便于人工检查
- 测试命令：

```bash
pytest tests/m1/ -v
```

测试文件建议结构：

```
tests/m1/
├── test_preprocess.py     # 预处理单元测试（小图、合成图）
├── test_mask.py           # mask 生成测试
├── test_eraser.py         # 擦除测试
├── test_quality.py        # 质量评分测试
├── test_engine_e2e.py     # 端到端样本测试
└── output/                # 对比图输出（gitignore）
```

---

## 验收标准

满足以下全部条件方视为模块完成：

- ✅ `process_paper()` 对 10 张样本图片**全部返回结果**（不崩溃，不抛未捕获异常）
- ✅ 至少 **80%** 样本 `success=True`
- ✅ 至少 **60%** 样本 `quality_score >= 0.6`
- ✅ CLI 可独立运行（`process` / `mask` / `batch` 三个子命令）
- ✅ 不依赖任何其他模块（M2/M3/M4/M5）
- ✅ `pytest tests/m1/ -v` 全部通过
- ✅ 对外接口签名与 `INTERFACE-CONTRACT.md` 4.1 节完全一致

---

## 技术风险与对策

| 风险 | 对策 |
|------|------|
| HEIC 格式（iPhone 默认） | 使用 `pillow-heif`，`import` 失败时 graceful fallback（warning + 仅支持 jpg/png） |
| 大图 OOM | 第一步缩放长边到 3000px |
| 黑色手写 vs 印刷体区分 | **最难的点**。第一版宁可保守（少擦），通过笔画宽度 + 连通域特征区分；后续可引入轻量分类器 |
| 纸张检测失败 | 跳过透视矫正，warning 记录，不阻塞流程 |
| 透视矫正过度变形 | 检测四边形面积占比，过小（<原图30%）则视为误判，跳过 |

HEIC 加载示例：

```python
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_SUPPORTED = True
except ImportError:
    HEIC_SUPPORTED = False
```

---

## 参考资料

- OpenCV 官方文档: https://docs.opencv.org/4.x/
- `adbu42/WPI_inpainting`: 白色填充思路参考
- `smirnovkirilll/document_preprocessor`: 文档预处理管线参考
- `INTERFACE-CONTRACT.md` 第四节 4.1: 权威接口定义

---

## 完成后的交付物

1. `src/m1_image_engine/` 完整代码
2. `tests/m1/` 测试代码与对比图
3. `requirements.txt` 中追加：`opencv-python`, `Pillow`, `numpy`, `pillow-heif`
4. 简短的运行说明（可写入模块 README 或本文件末尾）
