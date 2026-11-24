"""按 brand-mark.svg 构图重绘插件图标 icons/fntvdoubansync.png（512 画布渲染后缩至 128）"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
NAVY = (8, 22, 43)
BLUE = (52, 120, 229)
GREEN = (0, 181, 106)

S = 8  # 64 视图 → 512 画布


def main():
    img = Image.new("RGBA", (64 * S, 64 * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 深蓝圆角底
    d.rounded_rectangle((0, 0, 64 * S - 1, 64 * S - 1), radius=15 * S, fill=NAVY)

    # 蓝色横幅（顶部载具造型）
    d.rounded_rectangle((12 * S, 88, 53.4 * S, 216), radius=56, fill=BLUE)

    # 蓝色「F」字标
    d.rectangle((200, 216, 347, 440), fill=BLUE)  # 竖笔
    d.polygon([(278, 216), (392, 216), (348, 282), (278, 282)], fill=BLUE)  # 上横
    d.polygon([(278, 316), (334, 316), (291, 380), (278, 380)], fill=BLUE)  # 中横

    # 绿色循环箭头（同步意象）
    bbox = (98, 268, 298, 468)  # 圆心 (198,368) 半径 100
    d.arc(bbox, start=150, end=420, fill=GREEN, width=58)
    d.polygon([(230, 415), (300, 426), (256, 481)], fill=GREEN)  # 箭头头部

    icon = img.resize((128, 128), Image.LANCZOS)
    out = ROOT / "icons" / "fntvdoubansync.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    icon.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
