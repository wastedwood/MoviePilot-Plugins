"""将原项目 wastedwood/DouBanSync 的 brand-mark.svg 栅格化为插件图标 PNG"""

import io
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

BRAND_MARK_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" width="512" height="512" role="img" aria-labelledby="title">
  <title id="title">DouBanSync</title>
  <rect width="64" height="64" rx="15" fill="#08162b"/>
  <path fill="#3478e5" d="M12 11c1.8 4.9 5.1 7.2 10.2 7.2h19.6c5.1 0 8.4-2.3 10.2-7.2l2.1 3.8c1.4 2.6 1.1 5.2-.7 7.5-2.2 2.8-5.2 4.2-9 4.2H19.6c-3.8 0-6.8-1.4-9-4.2-1.8-2.3-2.1-4.9-.7-7.5L12 11Z"/>
  <path fill="#3478e5" d="M29 27h20l-5.5 8.2h-8.8v4.3h7.1l-5.4 7.9h-1.7V55H25V27h4Z"/>
  <path d="M24.8 33.5A12.5 12.5 0 1 0 31.4 55" fill="none" stroke="#00b56a" stroke-width="7.5" stroke-linecap="round"/>
  <path fill="#00b56a" d="m27.8 51.2 9.6 1.4-5.8 7.7-3.8-9.1Z"/>
</svg>"""

OUT_SIZE = 256


def render_svg_png(svg: str, out_size: int = OUT_SIZE) -> Image.Image:
    html = (
        "<!doctype html><html><body style='margin:0;padding:0;background:transparent;overflow:hidden;'>"
        f"{svg}</body></html>"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 512, "height": 512}, device_scale_factor=2)
            page.set_content(html)
            raw = page.locator("svg").screenshot(omit_background=True)
        finally:
            browser.close()
    img = Image.open(io.BytesIO(raw)).convert("RGBA")
    return img.resize((out_size, out_size), Image.Resampling.LANCZOS)


def main():
    icon = render_svg_png(BRAND_MARK_SVG, OUT_SIZE)
    icons_dir = ROOT / "icons"
    icons_dir.mkdir(parents=True, exist_ok=True)
    for name in ("fntvdoubansync-logo.png", "fntvdoubansync.png"):
        out = icons_dir / name
        icon.save(out)
        print(f"saved: {out} ({icon.size[0]}x{icon.size[1]})")


if __name__ == "__main__":
    main()
