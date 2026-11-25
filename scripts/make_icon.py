"""重绘插件图标 icons/fntvdoubansync.png（1024 画布超采样渲染后缩至 128x128）"""

import math
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

SIZE = 1024
OUT_SIZE = 128

BG_TOP = (12, 24, 48, 255)
BG_BOT = (22, 42, 78, 255)
RIM_COLOR = (255, 255, 255, 26)
CARD_SHADOW = (6, 12, 26, 130)
FN_BLUE = (47, 118, 246, 255)
FN_BLUE_LIGHT = (96, 165, 250, 255)
PLAY_WHITE = (248, 251, 255, 255)
DOUBAN_GREEN = (0, 181, 68, 255)
DOUBAN_GREEN_RING = (16, 185, 129, 255)
HALO_NAVY = (15, 30, 58, 255)


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _arc_point(cx: float, cy: float, r: float, deg: float) -> tuple[float, float]:
    rad = math.radians(deg)
    return cx + r * math.cos(rad), cy + r * math.sin(rad)


def _draw_sync_arrows(draw: ImageDraw.ImageDraw, cx: float, cy: float, r: float, stroke: int):
    bbox = (cx - r, cy - r, cx + r, cy + r)
    # 上半圆弧 + 右下箭头
    draw.arc(bbox, start=205, end=345, fill=PLAY_WHITE, width=stroke)
    tip1 = _arc_point(cx, cy, r, 355)
    b1a = _arc_point(cx, cy, r - stroke * 1.15, 330)
    b1b = _arc_point(cx, cy, r + stroke * 1.15, 330)
    draw.polygon([tip1, b1a, b1b], fill=PLAY_WHITE)

    # 下半圆弧 + 左上箭头
    draw.arc(bbox, start=25, end=165, fill=PLAY_WHITE, width=stroke)
    tip2 = _arc_point(cx, cy, r, 175)
    b2a = _arc_point(cx, cy, r - stroke * 1.15, 150)
    b2b = _arc_point(cx, cy, r + stroke * 1.15, 150)
    draw.polygon([tip2, b2a, b2b], fill=PLAY_WHITE)


def main():
    # 1. 垂直渐变圆角底板
    bg = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    grad = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grad)
    for y in range(SIZE):
        t = y / (SIZE - 1)
        col = tuple(int(BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * t) for i in range(4))
        gd.line([(0, y), (SIZE, y)], fill=col)

    mask = _rounded_mask(SIZE, 224)
    bg.paste(grad, (0, 0), mask)

    overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle((6, 6, SIZE - 7, SIZE - 7), radius=218, outline=RIM_COLOR, width=6)
    od.rounded_rectangle((174, 200, 758, 728), radius=108, fill=CARD_SHADOW)
    bg = Image.alpha_composite(bg, overlay)

    d = ImageDraw.Draw(bg)

    # 2. 飞牛影视主视觉卡片（蓝色媒体屏 + 顶部高光条 + 居中播放三角）
    card_box = (160, 176, 744, 704)
    d.rounded_rectangle(card_box, radius=108, fill=FN_BLUE)
    # 顶部浅蓝装饰条
    d.rounded_rectangle((224, 224, 680, 272), radius=24, fill=FN_BLUE_LIGHT)
    # 播放按钮三角（圆润居中）
    play_tri = [(376, 336), (376, 568), (576, 452)]
    d.polygon(play_tri, fill=PLAY_WHITE)

    # 3. 豆瓣同步绿标（右下角带深蓝隔离环的双箭头徽章）
    cx, cy = 708, 708
    halo_r = 186
    badge_r = 152
    d.ellipse((cx - halo_r, cy - halo_r, cx + halo_r, cy + halo_r), fill=HALO_NAVY)
    d.ellipse((cx - badge_r, cy - badge_r, cx + badge_r, cy + badge_r), fill=DOUBAN_GREEN)
    d.ellipse(
        (cx - badge_r + 6, cy - badge_r + 6, cx + badge_r - 6, cy + badge_r - 6),
        outline=DOUBAN_GREEN_RING,
        width=6,
    )
    _draw_sync_arrows(d, cx, cy, r=74, stroke=26)

    icon = bg.resize((OUT_SIZE, OUT_SIZE), Image.Resampling.LANCZOS)
    out = ROOT / "icons" / "fntvdoubansync.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    icon.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
