# TextIn 实验模块

## 启动本地交互页面

```bash
cd exam-paper-tool
python -m src.m4_web_backend.app
# → http://localhost:8900/textin.html
```

## 命令行实验（仍可用）

```bash
cp <样本图> data/api_eval/textin/input/
python -m src.m1_image_engine.providers.textin.experiment
open data/api_eval/textin/comparison/index.html
```

## Preset 速查

| Preset | 流水线 | binarization | 问题 |
|--------|--------|-------------|------|
| A1_default | 直接擦除 | 1 (默认) | 开箱即用效果？ |
| A2_no_sharpen | 直接擦除 | 0 | 关锐化减少残影？ |
| B1_geom_only | 先增强再擦除 | 0 (enhance_mode=-1) | 前置切边更好？ |
| B2_deshadow | 先增强再擦除 | 0 (enhance_mode=5) | 去阴影提升？ |

## API

- `POST /api/textin/process` — 上传图片+处理
- `GET /api/textin/results/{job_id}/{filename}` — 访问结果

## 验收标准

- [x] textin.html 浏览器打开可用
- [x] 拖拽上传 + 处理 + 5联屏
- [x] 4 preset 全通过
- [x] 失败不崩溃
- [x] .env 未提交
- [x] 旧 OpenCV 代码未修改
