# TextIn 试卷手写擦除 API 简化实验方案

> 生成时间：2026-06-01 | 简化版
> 目的：快速验证 TextIn 两个接口在手写擦除场景下的真实效果

---

## 一、实验目标

用 3-5 张家庭试卷图片，回答三个问题：

1. TextIn 直接擦除手写效果怎么样？
2. 先切边增强、再擦除，是否比直接擦除更好？
3. 是否值得交给 OpenCode 做正式接入？

---

## 二、实验边界

- ✅ 只测 TextIn（不测有道/百度/腾讯）
- ✅ 使用家庭自有试卷即可，不额外设计复杂脱敏流程
- ✅ 人工肉眼评价即可，不搞复杂评分表
- ❌ 不做正式产品接入（目前仅实验）

---

## 三、两个关键接口

### 3.1 文档切边增强矫正（crop_enhance_image）

| 维度 | 详情 |
|------|------|
| 接口 | `POST https://api.textin.com/ai/service/v1/crop_enhance_image` |
| 鉴权 | Header: `x-ti-app-id` + `x-ti-secret-code` |
| 请求体 | 二进制图片流（≤50MB, 20-10000px） |
| 返回 | JSON，`result.image_list[0].image` 为 base64 处理图 |

**关键参数**：

| 参数 | 作用 | 实验线 B 取值 |
|------|------|-------------|
| `crop_image=1` | 自动切边 | 1 |
| `correct_direction=1` | 方向校正 | 1 |
| `dewarp_image=1` | 弯曲矫正 | 1 |
| `enhance_mode` | 增强模式 | -1（禁用）和 5（去阴影增强）各测一次 |
| `deblur_image` | 清晰度提升 | 0 |
| `jpeg_quality` | 输出质量 | 95 |

### 3.2 自动擦除手写文字（handwritten_erase）

| 维度 | 详情 |
|------|------|
| 接口 | `POST https://api.textin.com/ai/service/v1/handwritten_erase` |
| 鉴权 | Header: `x-ti-app-id` + `x-ti-secret-code` |
| 请求体 | 二进制图片流（≤50MB, 20-10000px） |
| 返回 | JSON，`result.image` 为 base64 擦除后图片 |

**关键参数**：

| 参数 | 作用 | 实验线 A | 实验线 B |
|------|------|---------|---------|
| `crop` | 自动切边 | 1 | 0（前面已切） |
| `doc_direction` | 方向转正 | 4（自动） | 0（前面已转） |
| `dewarp` | 弯曲矫正 | 1 | 0（前面已矫） |
| `binarization` | 增强锐化 | A1=0, A2=1 | 0 |
| `image_type` | 彩色输出 | 1 | 1 |

---

## 四、两条实验线

### 实验线 A：直接擦除

```
原图 → handwritten_erase → cleaned
```

| 参数组 | crop | doc_direction | dewarp | binarization | 输出文件 |
|--------|------|-------------|--------|-------------|---------|
| A1 (无增强) | 1 | 4 | 1 | 0 | `direct_b0.jpg` |
| A2 (有增强) | 1 | 4 | 1 | 1 | `direct_b1.jpg` |

**目的**：判断 TextIn 擦除接口单独是否够用，以及 binarization 开关的影响。

### 实验线 B：先增强再擦除

```
原图 → crop_enhance_image → enhanced → handwritten_erase → cleaned
```

| 参数组 | enhance_mode | 输出文件 |
|--------|-------------|---------|
| B1 (禁用增强) | -1 | `chain_enhance_m1.jpg` |
| B2 (去阴影增强) | 5 | `chain_enhance_5.jpg` |

crop_enhance_image 固定参数：crop=1, dewarp=1, correct_direction=1, jpeg_quality=95
handwritten_erase 固定参数：crop=0, doc_direction=0, dewarp=0, binarization=0, image_type=1

**目的**：判断先做专业切边+矫正后再擦除，效果是否更好。

---

## 五、实验样本

准备 3-5 张真实家庭试卷/作业图片，覆盖：

1. 红笔批改
2. 铅笔答案
3. 黑笔答案
4. 几何图形或表格
5. 轻微倾斜或阴影

---

## 六、输出目录

```
data/api_eval/textin/
├── input/
│   ├── sample_001.jpg
│   ├── sample_002.jpg
│   └── sample_003.jpg
├── output/
│   └── sample_001/
│       ├── original.jpg
│       ├── direct_b0.jpg
│       ├── direct_b1.jpg
│       ├── chain_enhance_m1.jpg
│       ├── chain_enhance_5.jpg
│       ├── response_direct_b0.json
│       ├── response_direct_b1.json
│       ├── response_chain_enhance_m1.json
│       └── response_chain_enhance_5.json
└── comparison/
    ├── index.html        # 所有样本对比总览
    └── evaluation.md     # 人工评价结论
```

---

## 七、评价标准

每张图用文字记录即可，不搞复杂评分表：

1. 手写答案是否明显擦除？
2. 红笔批改是否明显擦除？
3. 印刷题干是否保留清楚？
4. 几何图/表格是否被破坏？
5. 背景是否自然？
6. A 线和 B 线哪个更好？
7. 是否值得继续接入正式 debug 页面？

---

## 八、密钥配置

```bash
# .env.example
TEXTIN_APP_ID=
TEXTIN_SECRET_CODE=
```

- `.env` 加入 `.gitignore`
- key 不写进代码
- 日志不打完整 key

---

## 九、最小开发任务（4 步）

### Task 1：TextIn Client 封装（0.5h）
- 读取 `.env` 中的 key
- 封装 `handwritten_erase(image_path, output_path, params)` 
- 封装 `crop_enhance_image(image_path, output_path, params)`
- 返回统一 dict：`{ok, output_path, duration_ms, error}`

### Task 2：实验线 A（0.5h）
- 输入图片 → 调 A1/A2 两组参数 → 输出 `direct_b0.jpg` / `direct_b1.jpg` + response json

### Task 3：实验线 B（0.5h）
- 输入图片 → 先调 crop_enhance_image → 再调 handwritten_erase → 输出 `chain_enhance_m1.jpg` / `chain_enhance_5.jpg` + response json

### Task 4：生成对比页面（0.5h）
- 每张图生成一个 compare.html（原图 / direct_b0 / direct_b1 / chain_enhance_m1 / chain_enhance_5 并排）
- 汇总 `comparison/index.html`
- 显示耗时和错误信息

---

## 十、下一步

1. 青山注册 TextIn → 获取 app-id + secret-code → 配置 .env
2. 准备 3-5 张测试图放入 `data/api_eval/textin/input/`
3. 交给 OpenCode 执行 4 个 Task
4. 打开 `comparison/index.html` 肉眼对比
5. 填写 `comparison/evaluation.md`，给出结论

---

*简化版方案。不追求企业级，不求万字，先跑通再看。*
