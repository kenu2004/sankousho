"""告知用の画像を docs/ に作る。サイトと同じ紙・活版の質感。

  python scripts/make_headers.py

  docs/note-header.png  note の見出し画像（1280×670）
  docs/x-header.png     X のヘッダー画像（1500×500）

Windows の游明朝と Georgia Italic を使う（Pillow が必要）。
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
FONTS = Path("C:/Windows/Fonts")

S = 2  # 2倍で描いて縮小し、線をなめらかにする
BG = (245, 241, 232)
INK = (43, 43, 38)
ACCENT = (199, 62, 58)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / name), size * S)


def mix(color: tuple, alpha: float) -> tuple:
    """紙の上に墨を alpha の濃さで乗せた色。"""
    return tuple(round(BG[i] + (color[i] - BG[i]) * alpha) for i in range(3))


def hikisen(d: ImageDraw.ImageDraw, x0: int, x1: int, y: int, alpha: float, width: int = 1) -> None:
    """ところどころ途切れる手引きの罫線（サイトの .hikisen と同じ刻み）。"""
    pattern = [(0, 17), (23, 51), (58, 70)]
    x = x0
    while x < x1:
        for a, b in pattern:
            if x + a >= x1:
                break
            d.line([((x + a) * S, y * S), (min(x + b, x1) * S, y * S)], fill=mix(INK, alpha), width=width * S)
        x += 79


def wave(d: ImageDraw.ImageDraw, x0: int, x1: int, y: int) -> None:
    """手で引いたような朱の波線。振幅と周期を少しずつ揺らす。"""
    rnd = random.Random(7)
    pts = []
    for i in range(0, x1 - x0 + 1, 2):
        t = i / 54 * 2 * math.pi
        amp = 4.2 + 0.8 * math.sin(i / 97)
        pts.append(((x0 + i) * S, (y + amp * math.sin(t) + rnd.uniform(-.25, .25)) * S))
    d.line(pts, fill=ACCENT, width=5 * S, joint="curve")
    for p in (pts[0], pts[-1]):  # 線の端を丸める
        r = 2.5 * S
        d.ellipse([p[0] - r, p[1] - r, p[0] + r, p[1] + r], fill=ACCENT)


def seal(chars: str, size: int) -> Image.Image:
    """朱肉のハンコ。少しゆがんだ四角に、白抜きの枠と2文字。"""
    n = size * S
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    k = n / 120
    d.polygon([(9 * k, 11 * k), (111 * k, 7 * k), (115 * k, 111 * k), (11 * k, 115 * k)], fill=ACCENT + (240,))
    d.rectangle([17 * k, 17 * k, 103 * k, 103 * k], outline=BG + (205,), width=max(1, round(2 * k)))
    f = ImageFont.truetype(str(FONTS / "yumindb.ttf"), round(34 * k))
    for ch, cy in ((chars[0], 39 * k), (chars[1], 80 * k)):
        d.text((60 * k, cy), ch, font=f, fill=BG, anchor="mm")
    return img.rotate(7, resample=Image.BICUBIC, expand=True)


def kicker(d: ImageDraw.ImageDraw, x: int, y: int, text: str, size: int = 19) -> None:
    """朱の点と、字間を広げた斜体の英字。"""
    d.ellipse([x * S, (y + 6) * S, (x + 7) * S, (y + 13) * S], fill=ACCENT)
    fk = font("georgiai.ttf", size)
    cx = (x + 20) * S
    for ch in text:
        d.text((cx, y * S), ch, font=fk, fill=mix(INK, .62))
        cx += d.textlength(ch, font=fk) + 2.6 * S


def headline(d: ImageDraw.ImageDraw, x: int, y: int, size: int, wave_gap: int) -> None:
    """「参考書、多すぎ問題。」。「多すぎ問題」の下に朱の波線。"""
    fh = font("yumindb.ttf", size)
    head_a, head_b = "参考書、", "多すぎ問題。"
    d.text((x * S, y * S), head_a, font=fh, fill=INK)
    xb = x * S + d.textlength(head_a, font=fh)
    d.text((xb, y * S), head_b, font=fh, fill=INK)
    wb = d.textlength(head_b[:-1], font=fh)  # 句点の手前まで波線
    wave(d, round(xb / S) - 4, round((xb + wb) / S) + 6, y + wave_gap)


def label_box(d: ImageDraw.ImageDraw, x: int, y: int, label: str, size: int = 24) -> None:
    """枠線だけのボタン風ラベル。"""
    fl = font("yumin.ttf", size)
    lw = d.textlength(label, font=fl)
    h = round(size * 2.3)
    d.rectangle([x * S, y * S, x * S + lw + 60 * S, (y + h) * S], outline=INK, width=S)
    d.text((x * S + 30 * S, (y + h / 2) * S), label, font=fl, fill=INK, anchor="lm")


def vertical_rule(d: ImageDraw.ImageDraw, x: int, y0: int, y1: int) -> None:
    d.line([(x * S, y0 * S), (x * S, y1 * S)], fill=mix(INK, .25), width=S)
    d.ellipse([(x - 3) * S, (y0 - 2) * S, (x + 3) * S, (y0 + 4) * S], fill=ACCENT)


def finish(img: Image.Image, w: int, h: int, name: str) -> None:
    img = img.resize((w, h), Image.LANCZOS)
    # 平均の明るさは変えずに ±6 だけ揺らして、紙の色はくすませず手ざわりだけ足す
    noise = Image.effect_noise((w, h), 48).filter(ImageFilter.GaussianBlur(.35))
    noise = noise.point(lambda v: v * 12 // 255).convert("RGB")
    img = ImageChops.add(img, noise, scale=1, offset=-6)
    DOCS.mkdir(exist_ok=True)
    img.save(DOCS / name, optimize=True)
    print(f"docs/{name} を作りました（{w}×{h}）")


def note_header() -> None:
    w, h = 1280, 670
    img = Image.new("RGB", (w * S, h * S), BG)
    d = ImageDraw.Draw(img)
    hikisen(d, 80, 1200, 64, .5, 2)
    hikisen(d, 80, 1200, 69, .2)
    hikisen(d, 80, 1200, 606, .18)
    vertical_rule(d, 150, 150, 540)
    x = 186
    kicker(d, x, 156, "IT PASSPORT  —  2026")
    d.text((x * S, 200 * S), "参考書が多すぎて、選べない人へ", font=font("yumin.ttf", 27), fill=mix(INK, .64))
    headline(d, x, 272, 100, 138)
    d.text((x * S, 452 * S), "YES/NOの10問で、自分に合う1冊がわかる。", font=font("yumindb.ttf", 38), fill=INK)
    label_box(d, x, 528, "ITパスポート参考書診断　登録不要・約1分　→")
    st = seal("診断", 132)
    img.paste(st, (1036 * S, 118 * S), st)
    finish(img, w, h, "note-header.png")


def x_header() -> None:
    """X のヘッダー。左下はアイコンが重なり、スマホでは上下が切れるので、文字は中央〜右の帯に置く。"""
    w, h = 1500, 500
    img = Image.new("RGB", (w * S, h * S), BG)
    d = ImageDraw.Draw(img)
    hikisen(d, 60, 1440, 40, .5, 2)
    hikisen(d, 60, 1440, 45, .2)
    hikisen(d, 60, 1440, 458, .18)
    vertical_rule(d, 452, 104, 400)
    x = 486
    kicker(d, x, 104, "INDIE DEV  —  IT PASSPORT")
    headline(d, x, 146, 78, 108)
    d.text((x * S, 286 * S), "YES/NOの10問で、自分に合う1冊がわかる診断を作りました。",
           font=font("yumindb.ttf", 27), fill=INK)
    label_box(d, x, 342, "ITパスポート参考書診断　登録不要・約1分　→", 21)
    st = seal("診断", 112)
    img.paste(st, (1290 * S, 78 * S), st)
    finish(img, w, h, "x-header.png")


if __name__ == "__main__":
    note_header()
    x_header()
