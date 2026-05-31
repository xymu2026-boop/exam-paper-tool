# 迁移自旧项目 exam-paper-tool，原始路径: 06_实验与样本/03_擦除实验/脚本草稿/erase_handwriting_path_a.py
# ⚠️ 旧版草稿，待重构

#!/usr/bin/env python3
"""
擦除手写还原空白题目 — 路径 A 脚本草稿（Pillow + 颜色阈值）

【状态】未运行。本脚本是 Phase 1C 的草稿，待用户授权 pip install Pillow 后可直接运行。

【用法】
    python3 erase_handwriting_path_a.py [--input INPUT_DIR] [--output OUTPUT_DIR]

【依赖】
    Pillow >= 10.0  (pip install Pillow)

【参数说明】
    INPUT_DIR  默认 ../擦除实验/input_5/
    OUTPUT_DIR 默认 ../擦除实验/output_cleaned/

【处理流程】
    对每张图：
    1. 读 RGB
    2. 像素级判断每个点的颜色
    3. 黑色（印刷字）：保留
    4. 蓝色 / 蓝黑色（手写笔）：替换为白
    5. 红色（红笔批改）：替换为白
    6. 灰色（阴影、纸张折痕）：保留（避免误伤印刷字）
    7. 输出到 OUTPUT_DIR，文件名加 _cleaned 后缀
    8. 写一份 process_log.csv，记录每张图的像素统计

【调参建议】
    - 黑色阈值：所有通道 < BLACK_THRESHOLD（默认 80）
    - 蓝色判定：B - max(R,G) > BLUE_DELTA（默认 30）
    - 红色判定：R - max(G,B) > RED_DELTA（默认 40）
    - 第一次跑完先观察 040（最干净），看印刷字是否完整保留
    - 如果误伤印刷字，调大 BLACK_THRESHOLD 或调大 RED_DELTA
    - 如果手写残留，调小 BLUE_DELTA

【注意事项】
    - 输入目录原图不会被修改，所有输出都另存到 OUTPUT_DIR
    - OUTPUT_DIR 不存在会自动创建
    - 同名输出文件会被覆盖（脚本运行多次时）
    - 处理失败会跳过该图，写日志，不会中断整批

【已知局限】
    - 颜色阈值法对扫描偏色敏感，不同扫描仪/拍照设备可能要重新调参
    - 手写笔颜色接近印刷字时无法分离（如签字笔的纯黑）
    - 红笔覆盖印刷字的部分会被一起擦掉，留下空白
    - 这是入门级方案，效果不满意应升级到路径 B（OpenCV）
"""
import argparse, csv, sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("错误：未安装 Pillow")
    print("请运行：pip install Pillow")
    sys.exit(1)


def parse_args():
    p = argparse.ArgumentParser()
    here = Path(__file__).resolve().parent
    default_in = here.parent / "擦除实验/input_5"
    default_out = here.parent / "擦除实验/output_cleaned"
    p.add_argument("--input", type=Path, default=default_in)
    p.add_argument("--output", type=Path, default=default_out)
    p.add_argument("--black-threshold", type=int, default=80)
    p.add_argument("--blue-delta", type=int, default=30)
    p.add_argument("--red-delta", type=int, default=40)
    return p.parse_args()


def is_black(r, g, b, t):
    return r < t and g < t and b < t


def is_blue(r, g, b, d):
    return b - max(r, g) > d


def is_red(r, g, b, d):
    return r - max(g, b) > d


def clean_image(src_path, dst_path, black_t, blue_d, red_d):
    """处理单张图，返回 (像素总数, 印刷, 手写蓝, 红笔, 其他保留) 统计"""
    img = Image.open(src_path).convert("RGB")
    pixels = img.load()
    w, h = img.size

    black_count = 0
    blue_count = 0
    red_count = 0
    kept_count = 0

    for y in range(h):
        for x in range(w):
            r, g, b = pixels[x, y]
            if is_black(r, g, b, black_t):
                black_count += 1
                # 印刷字保持原样
            elif is_red(r, g, b, red_d):
                red_count += 1
                pixels[x, y] = (255, 255, 255)
            elif is_blue(r, g, b, blue_d):
                blue_count += 1
                pixels[x, y] = (255, 255, 255)
            else:
                kept_count += 1
                # 灰色 / 浅色：保持原样（避免误伤印刷字的边缘）

    img.save(dst_path, quality=95)
    return w * h, black_count, blue_count, red_count, kept_count


def main():
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    images = sorted(args.input.glob("*.jpg")) + sorted(args.input.glob("*.png"))
    if not images:
        print(f"输入目录无图片: {args.input}")
        return

    log_rows = []
    for src in images:
        dst = args.output / (src.stem + "_cleaned" + src.suffix)
        try:
            total, blk, blu, rd, kpt = clean_image(
                src, dst, args.black_threshold, args.blue_delta, args.red_delta
            )
            print(f"[OK] {src.name} → {dst.name}")
            print(f"     总像素 {total}, 印刷 {blk} ({blk/total*100:.1f}%), "
                  f"蓝色擦 {blu} ({blu/total*100:.1f}%), "
                  f"红色擦 {rd} ({rd/total*100:.1f}%), "
                  f"其他保留 {kpt}")
            log_rows.append({
                "源文件": src.name,
                "输出文件": dst.name,
                "总像素": total,
                "印刷像素": blk,
                "印刷占比": f"{blk/total*100:.2f}%",
                "蓝色擦除像素": blu,
                "红色擦除像素": rd,
                "灰色保留像素": kpt,
                "状态": "成功",
                "黑阈值": args.black_threshold,
                "蓝差": args.blue_delta,
                "红差": args.red_delta,
            })
        except Exception as e:
            print(f"[FAIL] {src.name}: {e}")
            log_rows.append({
                "源文件": src.name,
                "输出文件": "",
                "总像素": 0, "印刷像素": 0, "印刷占比": "",
                "蓝色擦除像素": 0, "红色擦除像素": 0, "灰色保留像素": 0,
                "状态": f"失败-{e}",
                "黑阈值": args.black_threshold,
                "蓝差": args.blue_delta,
                "红差": args.red_delta,
            })

    log_path = args.output / "process_log.csv"
    with log_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(log_rows[0].keys()))
        w.writeheader()
        w.writerows(log_rows)
    print(f"\n日志: {log_path}")


if __name__ == "__main__":
    main()
