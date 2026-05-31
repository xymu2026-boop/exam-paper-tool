# M5 PDF 导出模块技术实现计划

> **模块编号**: M5
> **模块名称**: PDF 导出引擎
> **技术特性**: 纯函数式，零外部依赖
> **版本**: v1.0
> **日期**: 2026-05-31

---

## 1. 模块职责

M5 是一个纯函数式 PDF 生成库。它接收一个错题图片路径列表和一份导出配置，输出一份排版好的 PDF 文件到指定路径。它不访问数据库，不发起网络请求，也不依赖项目中的其他任何模块。M4 后端可以在导出流程中调用它，开发者也可以通过 CLI 独立运行它进行测试或批量处理。

---

## 2. 输入输出

### 2.1 函数接口

**输入**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image_paths` | `list[str]` | 是 | 错题图片的绝对路径列表，按期望顺序排列 |
| `output_path` | `str` | 是 | PDF 输出文件的绝对路径 |
| `config` | `ExportConfig` | 否 | 导出配置，为 `None` 时使用全部默认值 |

**输出**

| 返回值 | 类型 | 说明 |
|--------|------|------|
| 主返回值 | `bool` | `True` 表示 PDF 成功写入磁盘，`False` 表示导出失败 |
| 副作用 | 文件 | 在 `output_path` 位置生成 PDF 文件 |

### 2.2 支持的图片格式

- `jpg` / `jpeg`
- `png`

其他格式的图片在入口校验阶段会被跳过并记录警告日志。

### 2.3 输出 PDF 规格

- 页面尺寸：A4（210mm x 297mm）或 A3（297mm x 420mm）
- 图片按配置规则进行缩放、旋转和排版
- 每页预留边距，图片下方根据布局模式保留答题空间
- 首页可选显示标题文字

### 2.4 CLI 接口

```bash
# 基础导出
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf

# 指定布局模式
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf --layout two_per_page

# 指定标题和布局
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf --layout compact --title "K1 数学错题"
```

**CLI 参数说明**

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `images` | 位置参数 | 必填 | 一个或多个图片路径 |
| `-o`, `--output` | 字符串 | 必填 | 输出 PDF 路径 |
| `--layout` | 字符串 | `one_per_page` | 布局模式：`one_per_page` / `two_per_page` / `compact` |
| `--title` | 字符串 | `''` | PDF 首页标题 |

---

## 3. 技术选型

### 3.1 PDF 生成库：fpdf2

项目选用 `fpdf2>=2.7.0` 作为 PDF 生成引擎。它的核心优势在于：

- **API 简洁直观**：`pdf.image()` 和 `pdf.add_page()` 足以覆盖绝大多数排版场景，不需要像 ReportLab 那样管理复杂的画布状态。
- **体积轻量**：纯 Python 实现，不依赖额外的系统级二进制库（如 GTK 或 Qt），安装和部署都很方便。
- **图片处理能力成熟**：内置对 JPG 和 PNG 的直接嵌入支持，自动处理 DPI 换算，不需要手动把图片转成字节流。
- **活跃维护**：社区活跃，文档完整，中文支持方案明确。

### 3.2 排除的替代方案

| 方案 | 排除原因 |
|------|----------|
| **ReportLab** | API 过于底层，学习成本高。对于“把图片放进 PDF”这个需求，ReportLab 的代码量会多出几倍，且对中文支持需要额外配置 |
| **WeasyPrint / Markdown 方案** | 这些工具的核心场景是“HTML / Markdown 转 PDF”。M5 的工作对象是原始图片文件，不是富文本内容，引入 HTML 中间层属于过度设计 |
| **Pillow 原生 PDF** | Pillow 的 `save(format='PDF')` 功能非常基础，只能单图单页，无法控制页边距、多图排版、分页逻辑和字体渲染 |

### 3.3 中文支持方案

当 `config.title` 包含中文字符时，fpdf2 内置的拉丁字体无法渲染。解决方案是：

1. 在 `src/m5_pdf_export/fonts/` 目录下预置一份开源中文字体文件（如 **Noto Sans SC** 的 Regular 字重）。
2. 导出器在初始化 PDF 对象时，通过 `pdf.add_font('NotoSansSC', '', font_path, uni=True)` 加载该字体。
3. 渲染标题时切换至该字体即可正确显示中文。

字体文件仅在标题渲染时才会被读取。如果 `title` 为空或不包含中文，则不会触发字体加载逻辑，从而避免不必要的 I/O。

### 3.4 图片方向检测

图片方向检测由 `Pillow` 负责。它在读取图片时会解析 EXIF 中的 `Orientation` 标签，并自动应用旋转变换。如果某张图片是横向拍摄的照片（宽大于高），在竖向 A4 页面上会占用过多水平空间。此时 M5 会额外做一次逻辑判断：当图片宽高比明显偏向横向时，在内存中将其顺时针旋转 90 度，使其更适合纵向页面的排版。

---

## 4. 核心算法与流程

### 4.1 主流程 `export_pdf()`

整个导出过程遵循以下 7 个步骤：

1. **输入校验**：检查 `image_paths` 是否为非空列表，检查 `output_path` 的父目录是否存在（不存在则自动创建），过滤掉不存在的图片路径并记录日志。
2. **配置归一化**：如果 `config` 为 `None`，实例化一个 `ExportConfig()` 使用全部默认值。
3. **PDF 初始化**：根据 `config.page_size` 创建 `FPDF` 对象，设置页面尺寸和默认边距。
4. **标题页渲染**：如果 `config.title` 非空，在首页顶部居中渲染标题。标题页不放置任何图片。
5. **逐图排版**：遍历过滤后的图片列表，对每张图片执行加载、方向修正、尺寸计算和页面放置。
6. **分页控制**：在每个布局算法内部维护一个“当前页面剩余可用高度”的游标。当剩余空间不足以容纳下一张图片及其所需间距时，调用 `pdf.add_page()` 开启新页。
7. **保存输出**：调用 `pdf.output(output_path)` 写入磁盘，返回 `True`。

### 4.2 单页单题布局（`one_per_page`）

这是默认布局，每道错题独占一页。

- **可用宽度**：`page_width_mm - 2 * margin_mm`
- **图片缩放**：将图片宽度缩放到可用宽度，高度按原比例等比缩放。
- **水平定位**：`x = margin_mm`，即左对齐贴边距。
- **垂直定位**：`y = margin_mm`，即从页面上边距处开始。
- **高度保护**：如果缩放后的图片高度超过页面高度的 60%，则进一步缩小，使其高度恰好等于 60% 页面高度，宽度按原比例等比缩减。
- **答题留白**：图片底部到页面下边距之间保留 `spacing_mm` 的空白区域，供手写答题使用。

### 4.3 双页双题布局（`two_per_page`）

每页上下排列两道题。

- **半页可用高度**：`(page_height_mm - 2 * margin_mm - spacing_mm) / 2`
- **第一题**：占据上半部分，图片宽度缩放到可用宽度，顶部从 `margin_mm` 开始。
- **第二题**：占据下半部分，顶部从 `margin_mm + 半页高度 + spacing_mm` 开始。
- **高度溢出处理**：如果某张图片按可用宽度缩放后的高度超过了半页可用高度，则这张图片会被“提升”为单页单题模式，独占一整页，而不是被强行压缩进半页导致看不清。

### 4.4 紧凑布局（`compact`）

适合小题量密集打印。

- **可用宽度**：`page_width_mm - 2 * margin_mm`
- **图片间距**：图片之间固定保留 10mm 间隙（与 `spacing_mm` 解耦）。
- **贪心放置**：
  - 维护一个 `cursor_y` 变量，记录当前页面上已占用的最下方位置。
  - 第一张图片从 `margin_mm` 开始放置。
  - 放置后，`cursor_y = 图片底部 y + 10mm`。
  - 下一张图片尝试放在 `cursor_y` 处。
  - 如果 `cursor_y + 图片高度 > page_height_mm - margin_mm`，则新开一页，重置 `cursor_y = margin_mm`。
- **无强制留白**：紧凑模式下不额外预留答题空间，图片之间的 10mm 间隙即为全部留白。

### 4.5 图片处理流水线

每张图片在进入排版前都会经过以下处理：

1. **加载**：使用 `Pillow.Image.open(path)` 读取图片。
2. **EXIF 旋转**：调用 `ImageOps.exif_transpose(img)` 根据 EXIF 方向标签自动修正旋转。
3. **横向检测**：如果图片宽度大于高度且宽高比大于 1.2，在内存中执行 `img.rotate(-90, expand=True)` 使其变为纵向。
4. **尺寸计算**：根据布局算法的可用宽度，按原比例计算在 PDF 中的显示尺寸（毫米单位）。
5. **放置**：调用 `fpdf.image()` 将处理后的图片写入当前页面坐标。

---

## 5. 接口设计

### 5.1 主导出函数

```python
from dataclasses import dataclass

@dataclass
class ExportConfig:
    """导出配置"""
    layout: str = 'one_per_page'  # 'one_per_page' | 'two_per_page' | 'compact'
    page_size: str = 'A4'         # 'A4' | 'A3'
    margin_mm: int = 15           # 页边距
    spacing_mm: int = 20          # 题目间距（留答题空间）
    title: str = ''               # PDF 标题（如 "K1 数学错题 2026-05-31"）
    show_number: bool = True      # 是否显示题号

def export_pdf(image_paths: list[str], output_path: str,
               config: ExportConfig = None) -> bool:
    """
    将错题图片列表导出为 PDF。

    Args:
        image_paths: 错题图片的绝对路径列表（按顺序排列）
        output_path: PDF 输出的绝对路径
        config: 导出配置，None 时使用默认值

    Returns:
        是否成功

    行为:
        - 每张图片按比例缩放到页面宽度
        - layout='one_per_page': 每题一页，下方留空
        - layout='two_per_page': 每页两题
        - layout='compact': 尽量紧凑排列
        - 自动分页
        - 首页可选标题
    """
```

以上签名必须与 `INTERFACE-CONTRACT.md` 第 4.5 节保持一致，任何实现变更都不能修改该签名。

### 5.2 内部模块接口

虽然本计划不涉及具体实现代码，但以下内部函数的职责边界需要在开发时遵守：

| 函数（预期） | 所在文件 | 职责 |
|-------------|----------|------|
| `export_pdf()` | `exporter.py` | 公共入口，负责校验、初始化和协调排版 |
| `_load_and_orient_image(path)` | `utils.py` | 加载图片，应用 EXIF 旋转，检测横向并修正 |
| `_calculate_layout(images, config)` | `layout.py` | 接收图片元数据列表，输出每张图片的页面号和坐标元组 |
| `_render_title_page(pdf, config)` | `exporter.py` | 在首页渲染标题，处理中文字体加载 |
| `_render_image_page(pdf, image_info, layout_result)` | `exporter.py` | 根据布局结果调用 `pdf.image()` 放置单张图片 |
| `main()` | `cli.py` | 解析 `sys.argv`，构造 `ExportConfig`，调用 `export_pdf()` |

### 5.3 错误处理策略

| 异常场景 | 处理行为 | 返回值 |
|----------|----------|--------|
| 单个图片路径不存在 | 跳过该图片，记录 `logging.warning`，继续处理后续图片 | 其他图片正常导出，整体返回 `True`（部分成功） |
| 所有图片路径均无效 | 无可排版内容，不生成 PDF 文件 | 返回 `False` |
| `output_path` 的父目录不存在 | 自动调用 `os.makedirs(..., exist_ok=True)` 创建 | 继续执行 |
| 磁盘空间不足或写入权限不足 | `fpdf.output()` 抛出 `OSError` | 捕获异常，记录 `logging.error`，返回 `False` |
| 图片文件损坏导致 Pillow 无法读取 | 跳过该图片，记录 `logging.warning`，继续处理 | 其他图片正常导出，整体返回 `True` |
| 无效的 `layout` 或 `page_size` 字符串 | 在校验阶段发现，视为配置错误 | 返回 `False` |

---

## 6. 数据结构

### 6.1 配置数据类

```python
@dataclass
class ExportConfig:
    """导出配置"""
    layout: str = 'one_per_page'      # 合法值: 'one_per_page' | 'two_per_page' | 'compact'
    page_size: str = 'A4'             # 合法值: 'A4' | 'A3'
    margin_mm: int = 15               # 取值范围: 5 ~ 50
    spacing_mm: int = 20              # 取值范围: 0 ~ 100
    title: str = ''                   # 最大长度建议 100 字符
    show_number: bool = True          # 是否在每题左上角打印序号
```

### 6.2 页面尺寸常量

```python
PAGE_SIZES = {
    'A4': (210, 297),  # 单位: mm (宽, 高)
    'A3': (297, 420),  # 单位: mm (宽, 高)
}
```

### 6.3 内部图片元数据

在 `export_pdf()` 内部，每张输入图片会被转换为一个轻量元组或命名元组，避免在内存中同时保存所有 Pillow 对象：

```python
# 内部表示（示例，实际可用 NamedTuple 或 dataclass）
ImageInfo = tuple[str, int, int, int]
# 字段含义: (absolute_path, pixel_width, pixel_height, orientation_degrees)
```

- `absolute_path`: 图片在磁盘上的绝对路径
- `pixel_width`: 原始像素宽度
- `pixel_height`: 原始像素高度
- `orientation_degrees`: 需要额外施加的旋转角度（0 或 90）

### 6.4 布局计算结果

`layout.py` 的输出是一个布局指令列表，每个元素描述一张图片在最终 PDF 中的位置和尺寸：

```python
LayoutResult = list[tuple[int, float, float, float, float]]
# 字段含义: (page_number, x_mm, y_mm, display_width_mm, display_height_mm)
```

- `page_number`: 从 1 开始的页码
- `x_mm`: 图片左上角在页面上的水平位置（毫米）
- `y_mm`: 图片左上角在页面上的垂直位置（毫米）
- `display_width_mm`: 图片在 PDF 中的显示宽度（毫米）
- `display_height_mm`: 图片在 PDF 中的显示高度（毫米）

`exporter.py` 的职责是严格按照这个指令列表的顺序调用 `pdf.image()`，不自行再做任何尺寸或位置计算。

---

## 7. 测试策略

### 7.1 测试目录与文件

```
tests/m5/
├── __init__.py
├── conftest.py        # 测试图片生成 fixture
├── test_layout.py     # 排版算法单元测试
├── test_exporter.py   # 主导出流程测试
└── test_cli.py        # CLI 参数解析与执行测试
```

### 7.2 测试图片生成

在 `conftest.py` 中定义一个 `sample_images` fixture，使用 Pillow 动态生成已知尺寸的纯色矩形图片。这样做的好处是：测试不依赖真实照片文件，尺寸完全可控，颜色便于肉眼快速区分。

生成的测试图片覆盖以下场景：

| 尺寸 (px) | 颜色 | 用途 |
|-----------|------|------|
| 800 x 600 | 红色 | 标准纵向小图 |
| 1200 x 900 | 蓝色 | 标准纵向中图 |
| 600 x 800 | 绿色 | 纵向长高图 |
| 1000 x 1000 | 黄色 | 正方形图 |
| 1600 x 1200 | 紫色 | 横向大图，测试自动旋转 |

### 7.3 核心测试用例

**排版模式测试（`test_layout.py`）**

- `test_one_per_page_page_count`: 传入 5 张图，预期生成 5 页（或 6 页，如果有标题页）。读取输出 PDF 的页数进行断言。
- `test_two_per_page_layout`: 传入 4 张图，预期生成 2 页排版页（加可能的标题页）。
- `test_compact_layout`: 传入 10 张矮图，验证页数明显少于 10 页，确认紧凑排列生效。
- `test_no_blank_pages`: 所有布局模式下，最终 PDF 不应出现完全空白的页面。

**边界条件测试（`test_exporter.py`）**

- `test_empty_image_list`: 传入空列表，预期返回 `False`，且不应在磁盘上创建 PDF 文件。
- `test_single_image`: 传入单张图片，三种布局都能正常生成至少一页的 PDF。
- `test_many_images`: 传入 50 张测试图片，验证程序能在合理时间内完成，且 PDF 页数符合预期。
- `test_missing_image_path`: 传入包含 2 个有效路径和 1 个无效路径的列表，预期跳过无效路径，其余图片正常导出，返回 `True`。
- `test_invalid_layout_name`: 构造 `ExportConfig(layout='invalid')`，预期 `export_pdf()` 返回 `False`。

**图片方向测试**

- `test_landscape_image_rotated`: 使用一张宽度远大于高度的测试图片，在 `one_per_page` 布局下，验证其在 PDF 中被旋转为纵向，而不是以极小的比例横向塞入页面。

**中文标题测试**

- `test_chinese_title_rendering`: 设置 `title="K1 数学错题 2026-05-31"`，生成 PDF 后用系统阅读器打开，确认标题显示正常，没有出现“豆腐块”（空白方框）。

**CLI 测试（`test_cli.py`）**

- `test_cli_export_command`: 模拟 `python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o out.pdf`，验证进程退出码为 0 且文件存在。
- `test_cli_layout_flag`: 测试 `--layout two_per_page` 和 `--layout compact` 都能被正确解析并影响输出。
- `test_cli_title_flag`: 测试 `--title "某标题"` 能被正确传递。

### 7.4 验收标准

- 执行 `pytest tests/m5/ -v` 时全部测试通过。
- 生成的 PDF 可以用 macOS 预览、Adobe Acrobat Reader 或 Chrome 内置阅读器正常打开。
- 将 PDF 发送至打印机，打印结果清晰，图片没有超出纸张边界或被截断。
- CLI 可以在完全不加载 M1/M2/M3/M4 任何代码的情况下独立运行。

---

## 8. 风险与对策

### 8.1 中文标题渲染为空白方框

**风险描述**：如果 fpdf2 加载字体文件失败，或者字体文件本身缺少对应字符的字形，中文字符会显示为空白方框（俗称“豆腐块”），严重影响可用性。

**对策**：

1. 在 `src/m5_pdf_export/fonts/` 下固定预置一份经过验证的 Noto Sans SC 字体文件（Regular 字重即可）。
2. 在 `export_pdf()` 的初始化阶段，检查标题是否包含中文字符（可用正则表达式匹配 Unicode 中文字符范围）。只有需要时才加载字体，避免无标题时的冗余 I/O。
3. 在 CI 测试流程中加入 `test_chinese_title_rendering` 测试，该测试生成一份带中文标题的 PDF，并通过 `PyMuPDF` 或 `pdfplumber` 提取文本内容，断言其中包含预期的中文字符。这样可以在每次提交时自动验证字体渲染的正确性。

### 8.2 高分辨率图片导致缩放过度、细节丢失

**风险描述**：现代手机拍摄的试卷照片分辨率可能高达 3000x4000 甚至更高。如果直接按页面宽度等比缩放，图片在 PDF 中的物理尺寸会很大，但显示尺寸却被压缩到 A4 宽度，导致文件体积膨胀而视觉质量并未提升。反之，如果图片缩放逻辑有误，也可能导致图片被过度压缩，文字模糊。

**对策**：

1. 在加载图片后，根据目标显示尺寸（毫米）和页面默认 DPI（72 DPI，约 2.83 px/mm）计算目标像素尺寸。
2. 如果原图分辨率远超目标像素尺寸，先用 Pillow 的 `Image.resize()` 将其缩小到目标尺寸附近，再传给 fpdf2。这样可以显著减小 PDF 文件体积。
3. 如果原图分辨率低于目标尺寸（例如截图或小图），则保持原图像素，不做放大，避免人为引入模糊。
4. 在测试集中加入一张超高分辨率测试图，验证生成的 PDF 文件大小在合理范围内（不应超过几十 MB）。

### 8.3 损坏的图片文件导致整个导出流程崩溃

**风险描述**：如果输入的图片列表中某一张文件已损坏（例如传输中断导致的不完整 JPG），Pillow 在 `Image.open()` 时可能抛出 `OSError` 或 `UnidentifiedImageError`，从而中断整个导出过程。

**对策**：

1. 对每一张图片的加载操作都包裹在 `try ... except (OSError, UnidentifiedImageError)` 块中。
2. 单张图片加载失败时，记录 `logging.warning` 说明跳过的文件路径和原因，然后 `continue` 处理下一张。
3. 导出结束后，如果至少有一张图片成功排版，主函数返回 `True`。只有当全部图片都失败时，才返回 `False`。
4. 在测试集中加入一个故意损坏的文件（例如一个内容为随机字节的 `.jpg` 文件），验证跳过逻辑生效。

### 8.4 大量大图片导致内存占用过高

**风险描述**：如果用户一次性导出上百张高分辨率错题图片，且实现代码采用“先全部加载到内存，再统一写入 PDF”的策略，可能导致内存峰值过高，在内存受限的设备上触发 `MemoryError`。

**对策**：

1. 采用**流式处理**策略：遍历图片列表时，一次只加载并处理一张图片。
2. 每张图片处理完毕后，立即调用 `pdf.image()` 写入 PDF 内部缓冲区，然后主动调用 `img.close()` 释放 Pillow 对象，并在循环末尾执行 `del img` 帮助垃圾回收。
3. 避免在内存中同时保留所有图片的 Pillow 对象或所有图片的字节流。
4. 在测试中不直接验证内存占用（因为难以稳定断言），但代码审查时必须确认不存在预加载所有图片的写法。

### 8.5 输出目录不存在导致写入失败

**风险描述**：M4 后端调用 M5 时，可能传入一个尚不存在的输出路径（例如 `data/exports/1.pdf`，而 `data/exports/` 目录还未创建）。如果 M5 不做处理，`pdf.output()` 会直接抛出 `FileNotFoundError`。

**对策**：

1. 在 `export_pdf()` 的校验阶段，使用 `os.makedirs(os.path.dirname(output_path), exist_ok=True)` 自动创建父目录。
2. 这是一个无副作用的安全操作，即使目录已存在也不会报错。
3. 在测试中传入一个深层嵌套的 `tmp_path / "a/b/c/output.pdf"`，验证导出成功且目录被自动创建。

### 8.6 极端宽高比图片破坏排版

**风险描述**：实际错题图片的宽高比差异很大。例如一道横向贯穿整页的数学题截图可能非常宽，而一道竖向的填空题可能非常窄且高。极端比例可能导致 `one_per_page` 模式下图片被过度缩小，或者 `compact` 模式下某一张高图独占一页造成浪费。

**对策**：

1. 在测试 fixture 中额外生成极端比例的图片：超宽图（2000x200）、超高图（200x2000）、以及混合方向的图片序列。
2. 对 `layout.py` 的单元测试覆盖这些极端情况，断言它们不会触发除零错误，也不会生成空白页。
3. 在 `two_per_page` 模式下，已经设计了“提升为单页”的兜底逻辑。对于其他模式，保证图片始终会被缩放至页面可用区域内，绝不溢出边界。
