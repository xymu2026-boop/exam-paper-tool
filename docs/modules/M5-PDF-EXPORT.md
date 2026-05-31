# M5: PDF 导出 — 开发任务卡

| 模块编号 | 状态 | 可并行 | 依赖 |
|---------|------|--------|------|
| M5      | 待开发 | ✅     | 无   |

---

## 模块定位

将错题图片列表导出为可打印的 A4 PDF。纯 Python，不依赖数据库，不依赖网络，不依赖其他模块。

模块定位为**纯函数式工具**：输入图片路径列表 + 配置，输出 PDF 文件。可被 M4 后端调用，也可通过 CLI 独立运行。

---

## 前置阅读

- `docs/INTERFACE-CONTRACT.md` 第四节 4.5
- `家庭版试卷宝需求总文档_v1.0.md` 主线6

---

## 目录结构

```
src/m5_pdf_export/
├── __init__.py        # 导出 export_pdf, ExportConfig
├── exporter.py        # 主导出逻辑
├── layout.py          # 排版算法
├── cli.py             # CLI 入口
└── utils.py           # 辅助函数
```

测试目录：

```
tests/m5/
├── __init__.py
├── conftest.py        # 生成测试图片的 fixture
├── test_layout.py     # 排版单元测试
├── test_exporter.py   # 主流程测试
└── test_cli.py        # CLI 测试
```

---

## 核心接口

### ExportConfig

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
```

### export_pdf

```python
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

---

## 实现要求

### 排版算法 (layout.py)

#### one_per_page 模式

- 每道错题占一整页
- 图片居中，按比例缩放到页面宽度（减去边距）
- 图片下方留 `spacing_mm` 的空白答题区域
- 如果图片太高（超过页面高度的 60%），缩小到 60%

#### two_per_page 模式

- 每页放两道题
- 上下各占页面一半
- 每题图片 + 下方留白
- 如果某题图片太高，单独占一页

#### compact 模式

- 尽量紧凑排列
- 图片之间只留 10mm 间距
- 自动分页（当前页放不下时换页）
- 适合打印大量小题

### 标题和编号

- 首页顶部显示 `config.title`（如果非空）
- `show_number=True` 时，每题左上角显示序号（1, 2, 3...）
- 字体：使用 fpdf2 内置字体（不需要中文字体文件）
- 如果 `title` 包含中文，用 fpdf2 的 UniTTF 支持（需要一个中文字体文件，放在 `src/m5_pdf_export/fonts/` 下）

### 图片处理

- 支持 jpg, png 格式输入
- 自动检测图片方向（横向图片旋转 90 度适配竖向页面）
- 图片路径不存在时跳过并在日志中记录

---

## 测试要求

- `tests/m5/` 目录
- 用固定尺寸的测试图片（可以用 Pillow 生成纯色矩形）
- 测试三种 layout 模式
- 验证输出 PDF 存在且大小合理
- 测试命令：

```bash
pytest tests/m5/ -v
```

测试图片生成示例（放在 `conftest.py` 中）：

```python
import pytest
from PIL import Image

@pytest.fixture
def sample_images(tmp_path):
    """生成 5 张不同尺寸的纯色测试图片"""
    paths = []
    for i, (w, h, color) in enumerate([
        (800, 600, 'red'),
        (1200, 900, 'blue'),
        (600, 800, 'green'),
        (1000, 1000, 'yellow'),
        (1600, 1200, 'purple'),  # 横向图片，测试旋转
    ]):
        p = tmp_path / f'img_{i}.png'
        Image.new('RGB', (w, h), color).save(p)
        paths.append(str(p))
    return paths
```

---

## 验收标准

- 输入 5 张图片，三种 layout 都能生成 PDF
- PDF 可以用系统默认 PDF 阅读器打开
- 打印效果清晰可读
- CLI 可独立运行
- 不依赖任何其他模块

CLI 验收命令：

```bash
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf --layout two_per_page
python -m src.m5_pdf_export.cli export img1.jpg img2.jpg -o output.pdf --layout compact --title "K1 数学错题"
```

---

## 技术要点

- fpdf2 的 `image()` 方法自动处理缩放
- A4 尺寸：210mm x 297mm
- 注意 DPI 和像素的换算（默认 72 DPI，1mm ≈ 2.83 pt）
- fpdf2 中文支持需要 `add_font()` + TTF 文件

页面尺寸常量：

```python
PAGE_SIZES = {
    'A4': (210, 297),  # mm
    'A3': (297, 420),  # mm
}
```

---

## 参考资料

- fpdf2 文档：<https://py-pdf.github.io/fpdf2/>
- fpdf2 图片处理：<https://py-pdf.github.io/fpdf2/Images.html>
