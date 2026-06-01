# TextIn 与有道试卷擦除 API 实验方案

> 生成时间：2026-06-01 | 作者：Deepseek 小马
> 目的：用非敏感试卷测试两个商业 API 的效果、速度和成本，判断是否值得封装

---

## 一、实验目标

1. **快速获得可用效果**：跳过本地 OpenCV/LaMa 调参阶段，直接用商业 API 看天花板
2. **与本地方案做 baseline 对比**：后续本地 mask+inpainting 方案可以拿 API 结果做对照
3. **评估成本**：算清"处理一张试卷到底多少钱"
4. **判断是否值得封装**：如果效果远超本地、成本可接受，考虑封装进 debug 页面作为可选 backend

---

## 二、实验边界（不做的）

- ❌ 不接百度和腾讯
- ❌ 不上传含孩子姓名、学校、班级、老师签名等敏感信息的图片
- ❌ 不把 API 设为默认正式流程（目前仅实验）
- ❌ 不做账号系统、错题库、PDF 导出等下游功能
- ❌ 不替代本地处理路线（API 只是对照）

---

## 三、TextIn API 调研

### 3.1 基本信息

| 维度 | 详情 |
|------|------|
| 官方文档 | https://www.textin.com/document/text_auto_removal |
| 接口地址 | `POST https://api.textin.com/ai/service/v1/handwritten_erase` |
| 鉴权 | Header: `x-ti-app-id` + `x-ti-secret-code` |
| 请求体 | 二进制图片流（`Content-Type: application/octet-stream`）或 URL（`text/plain`） |
| 返回格式 | JSON，`result.image` 是 base64 编码的擦除后图片 |
| 图片限制 | ≤50MB，宽高 20-10000px，支持 jpg/png/bmp/pdf/tiff/webp/gif |

### 3.2 支持能力（URL 参数）

| 参数 | 作用 | 默认 |
|------|------|------|
| `crop=1` | 自动切边 | 0（关闭） |
| `dewarp=1` | 弯曲矫正 | 1（开启） |
| `doc_direction=4` | 自动方向转正 | 0（不旋转） |
| `binarization=1` | 增强锐化 | 1（开启） |
| `image_type=1` | 彩色输出（0=黑白） | 1 |
| `mask_position` | 指定擦除区域坐标 | 整图 |

### 3.3 价格

- 套餐 ￥9.9 起
- 新客有免费体验额度
- 按调用次数计费（具体阶梯价需登录后查看）

### 3.4 错误码

| 错误码 | 含义 |
|--------|------|
| 40101 | app-id/secret-code 为空 |
| 40102 | 鉴权失败 |
| 40003 | 余额不足 |
| 40302 | 文件超 50MB |
| 40304 | 图片尺寸不符 |
| 40306 | QPS 超限 |

### 3.5 Python 调用伪代码

```python
import requests

def textin_erase(image_path, output_path, app_id, secret_code):
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    headers = {
        'x-ti-app-id': app_id,
        'x-ti-secret-code': secret_code,
    }
    params = {
        'crop': 1,
        'doc_direction': 4,
        'dewarp': 1,
        'binarization': 1,
        'image_type': 1,
    }
    
    resp = requests.post(
        'https://api.textin.com/ai/service/v1/handwritten_erase',
        params=params,
        headers=headers,
        data=image_data,
        timeout=30
    )
    result = resp.json()
    if result['code'] == 200:
        import base64
        img_bytes = base64.b64decode(result['result']['image'])
        with open(output_path, 'wb') as f:
            f.write(img_bytes)
        return {'ok': True, 'output_path': output_path}
    else:
        return {'ok': False, 'error': result['message'], 'code': result['code']}
```

### 3.6 接入难点

- 需要在 TextIn 平台注册 → 工作台 → 开发者信息中获取 x-ti-app-id 和 x-ti-secret-code
- 免费额度有限，评测完可能需充值
- 返回的 image 是 base64，大图可能较长

### 3.7 对我们项目的价值

- 效果估计最好（深度学习模型 + 弯曲矫正 + 自动切边）
- 参数丰富（可控制切边/方向/弯曲/彩色），适合做实验对照

---

## 四、有道 API 调研

### 4.1 基本信息

| 维度 | 详情 |
|------|------|
| 官方文档 | https://ai.youdao.com/DOCSIRMA/html/learn/api/sjsxtcc/index.html |
| 接口地址 | `POST https://openapi.youdao.com/ocr_writing_erase` |
| 鉴权 | `appKey` + `sign`（sha256 签名） |
| 请求格式 | `application/x-www-form-urlencoded`（**不是 JSON**） |
| 返回格式 | JSON |
| 图片限制 | Base64 ≤ 5MB（最短边>10px，最长边<2048px） |

### 4.2 签名算法（关键！）

```
signType = v3
input = imgBase64前10字符 + imgBase64长度 + imgBase64后10字符（当img>20字符时）
      或 imgBase64字符串（当img≤20字符时）
sign = sha256(appKey + input + salt + curtime + appSecret)
```

### 4.3 请求参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `appKey` | ✅ | 应用 ID |
| `q` | ✅ | 图片 base64（≤5MB） |
| `salt` | ✅ | 随机数（UUID 或时间戳） |
| `curtime` | ✅ | Unix 时间戳（秒） |
| `sign` | ✅ | sha256 签名 |
| `signType` | ✅ | 固定 `v3` |
| `angle` | 否 | 0=不识别方向，1=360度识别（默认0） |

### 4.4 价格

| 月调用量 | 单价 |
|---------|------|
| 0-1万次 | 0.1 元/次 |
| 1-5万次 | 递减 |
| 200万次以上 | 0.0025 元/次 |
| 资源包 | 1万次 = 60 元 |

新用户注册赠 50 元体验金。

### 4.5 Python 调用伪代码

```python
import requests
import hashlib
import time
import base64
import uuid

def youdao_erase(image_path, output_path, app_key, app_secret):
    with open(image_path, 'rb') as f:
        img_bytes = f.read()
    img_base64 = base64.b64encode(img_bytes).decode('utf-8')
    
    # 计算 input
    if len(img_base64) > 20:
        inp = img_base64[:10] + str(len(img_base64)) + img_base64[-10:]
    else:
        inp = img_base64
    
    salt = str(uuid.uuid4())
    curtime = str(int(time.time()))
    sign_str = app_key + inp + salt + curtime + app_secret
    sign = hashlib.sha256(sign_str.encode('utf-8')).hexdigest()
    
    data = {
        'appKey': app_key,
        'q': img_base64,
        'salt': salt,
        'curtime': curtime,
        'sign': sign,
        'signType': 'v3',
        'angle': '1',
    }
    
    resp = requests.post(
        'https://openapi.youdao.com/ocr_writing_erase',
        data=data,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        timeout=30
    )
    result = resp.json()
    if result.get('errorCode') == '0':
        # 返回的 result 中包含擦除后的图片 URL 或 base64
        # 具体字段以实际返回为准
        return {'ok': True, 'raw': result}
    else:
        return {'ok': False, 'error': result.get('errorMessage', 'unknown')}
```

### 4.6 接入难点

- 签名算法容易写错（input 计算规则特殊）
- 图片 base64 ≤5MB（比 TextIn 的 50MB 严格）
- 最长边 <2048px（大图需要先缩放）
- 有道的"输入"文本的计算是：取base64字符串前10个字符 + 总长度 + 后10个字符

### 4.7 对我们项目的价值

- 价格极低（0.1元/次起）
- 专门面向试卷场景
- 新用户 50 元体验金够跑 500 次

---

## 五、两个 Provider 对比表

| 维度 | TextIn | 有道智云 |
|------|--------|---------|
| **接口名称** | 自动擦除手写文字 | 试卷手写体擦除 |
| **专门面向试卷** | 否（通用文档） | ✅ 是 |
| **自动切边** | ✅ crop=1 | ❌ |
| **方向转正** | ✅ doc_direction=4 | ✅ angle=1 |
| **弯曲矫正** | ✅ dewarp=1 | ❌ |
| **彩色输出** | ✅ image_type=1 | ✅ |
| **指定擦除区域** | ✅ mask_position | ❌ |
| **鉴权复杂度** | ⭐ 简单（两个 header） | ⭐⭐ 中（sha256签名） |
| **单次价格** | 套餐 ￥9.9 起 | 0.1 元/次（1万次以内） |
| **免费额度** | 新客体验 | 50 元体验金（≈500次） |
| **图片限制** | ≤50MB, 20-10000px | Base64 ≤5MB, 最长<2048px |
| **Python 接入难度** | ⭐ 低 | ⭐⭐ 中 |
| **隐私风险** | 云端处理 | 云端处理 |
| **推荐优先级** | 🔥 优先试（参数丰富） | ✅ 同步试（更便宜） |

---

## 六、实验数据准备

### 6.1 样本要求

- 5-10 张**非敏感**试卷/作业图片
- **不含**：孩子姓名、学校、班级、电话、二维码、老师签名
- 覆盖场景：红笔批改、铅笔答案、黑笔答案、几何图形、表格、光线不均、倾斜拍照

### 6.2 目录结构

```
data/api_eval/
├── input/
│   ├── sample_001.jpg
│   ├── sample_001_meta.json    # {"has_red":true,"has_pencil":false,...}
│   ├── sample_002.jpg
│   └── ...
├── textin/
│   └── sample_001/
│       ├── cleaned.jpg
│       ├── response.json
│       └── request_meta.json   # {duration_ms, cost_yuan, params}
├── youdao/
│   └── sample_001/
│       ├── cleaned.jpg
│       ├── response.json
│       └── request_meta.json
└── comparison/
    ├── sample_001_compare.html
    └── evaluation.csv
```

---

## 七、代码结构建议（先不实现）

```
src/m1_image_engine/providers/
├── __init__.py
├── base.py                # EraseProvider 基类
├── textin_provider.py     # TextIn 实现
├── youdao_provider.py     # 有道实现
└── provider_eval.py       # 批量评测脚本
```

统一返回结构：
```json
{
  "provider": "textin",
  "ok": true,
  "input_path": "...",
  "output_path": "...",
  "duration_ms": 1234,
  "cost_estimate_yuan": 0.03,
  "warnings": [],
  "errors": [],
  "raw_response_path": "response.json"
}
```

---

## 八、密钥与安全

- API Key / Secret 用 `.env` 管理，**不写进代码**
- `.env` 加入 `.gitignore`
- 日志不打完整 key
- 上传前人工确认图片无敏感信息
- 所有云端调用由用户主动触发，不做后台自动

```bash
# .env.example
TEXTIN_APP_ID=
TEXTIN_SECRET_CODE=
YOUDAO_APP_KEY=
YOUDAO_APP_SECRET=
```

---

## 九、评估指标（人工评分）

| 指标 | 分值 | 说明 |
|------|------|------|
| 红笔擦除 | 0-5 | 红笔批改是否干净 |
| 铅笔擦除 | 0-5 | 铅笔字是否擦除 |
| 黑笔擦除 | 0-5 | 黑笔答案是否擦除 |
| 题干保留 | 0-5 | 印刷文字是否完整 |
| 图形保留 | 0-5 | 几何图形是否损坏 |
| 背景自然 | 0-5 | 是否出现白斑/脏块 |
| 总体推荐 | 0-5 | 是否值得继续用 |

输出到 `data/api_eval/comparison/evaluation.csv`。

---

## 十、最小开发任务拆分

### Task 1：环境配置（0.5h）
- 新增 `.env.example`
- 新增 `src/m1_image_engine/providers/` 目录骨架
- 验收：无 key 时 print 友好提示

### Task 2：TextIn 最小调用（1h）
- `textin_provider.py` → 输入图片路径 → 输出 cleaned.jpg + response.json
- 验收：跑通 1 张图

### Task 3：有道最小调用（1h）
- `youdao_provider.py` → 实现签名 → 输出 cleaned.jpg + response.json
- 验收：跑通 1 张图

### Task 4：统一 Provider 接口（0.5h）
- `base.py` 定义基类，两个 provider 实现
- 验收：`python provider_eval.py --provider textin --input sample.jpg` 能跑

### Task 5：生成对比 HTML（0.5h）
- 原图 / TextIn / 有道 三栏并排
- 显示耗时、费用
- 验收：浏览器打开可见

### Task 6：输出实验报告（0.5h）
- 汇总 5-10 张图的结果
- 输出推荐结论

---

## 十一、风险与注意事项

| 风险 | 应对 |
|------|------|
| 隐私泄露 | 只用脱敏图片，不上传孩子真实试卷 |
| 费用超支 | 先查免费额度，跑 5 张就停 |
| API 限流 | 间隔 1 秒调用 |
| 图片超限 | 有道需先缩放到 2048px |
| 签名错误 | 严格按文档写 input 计算逻辑 |
| 网络超时 | 设置 30s timeout + 重试 1 次 |

---

## 十二、初步结论

1. **优先试 TextIn**：参数丰富（切边+矫正+弯曲+指定区域），适合做实验对照，接入简单
2. **同步试有道**：更便宜、更专精试卷场景，签名的额外复杂度值得
3. **本地路线继续保留**：无论 API 效果多好，隐私要求决定了长期必须有本地方案
4. **建议进入 OpenCode 实验开发**：6 个 Task 总共约 4 小时，性价比极高
5. **需要青山准备**：TextIn 和有道的注册账号 + API key，5-10 张脱敏测试图

---

*实验方案完成。不追求万字，够用即止。*
