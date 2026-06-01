# TextIn 实验模块

TextIn 单供应商试卷擦除 API 实验。回答 "TextIn 值不值得继续投入"。

## 快速开始

```bash
cp .env.example .env   # 填入 TEXTIN_APP_ID / TEXTIN_SECRET_CODE
mkdir -p data/api_eval/textin/input
cp <你的样本图> data/api_eval/textin/input/sample_001.jpg
python -m src.m1_image_engine.providers.textin.experiment
open data/api_eval/textin/comparison/index.html
```

## Preset 速查

| Preset | 流水线 | 关键参数 | 想回答的问题 |
|--------|--------|---------|------------|
| A1_default | 直接擦除 | binarization=1 (默认) | 开箱即用效果如何 |
| A2_no_sharpen | 直接擦除 | binarization=0 | 关锐化能否减少残影 |
| B1_geom_only | 先增强再擦除 | enhance_mode=-1 | 前置切边是否优于 A 线 |
| B2_deshadow | 先增强再擦除 | enhance_mode=5 | 去阴影是否进一步提升 |

## 输出

```
data/api_eval/textin/output/sample_001/
├── original.jpg
├── A1_default.jpg / A2_no_sharpen.jpg
├── B1_enhanced.jpg / B1_geom_only.jpg
├── B2_enhanced.jpg / B2_deshadow.jpg
├── responses/ (6 份 JSON)
├── meta.json
└── compare.html
```

## 验收标准

- [ ] 4 个 preset 全部生成对应输出
- [ ] response.json 完整保存
- [ ] B 线中间产物 _enhanced.jpg 存在
- [ ] meta.json stage_failed 字段正确
- [ ] comparison/index.html 可浏览器打开
- [ ] 失败 preset 显示错误信息而非空白

## 第一轮要回答的 5 个核心问题

1. TextIn 单接口擦除手写效果是否可用？
2. binarization 默认 1 是不是好默认？
3. B 线是不是比 A 线更好？
4. enhance_mode=5 相比 -1 有没有显著改善？
5. 下一步怎么走？
