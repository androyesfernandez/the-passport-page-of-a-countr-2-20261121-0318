#!/usr/bin/env python3
"""The passport page of a country that isn't there.

Renders one open passport spread of the Republic of Vessalia -- a small
island republic of lighthouses and ferry ports -- as a single PNG written
to /output/entry.png. Pure PIL, no network, fully deterministic: the same
program always produces the same bytes.

Left page: visas and border stamps telling one consistent trip
(Port Aurelia -> Kordavia -> home, then San Telmo -> home), plus a
Kordavian visa sticker with its fee paid. Right page: the data page --
drawn portrait (plus a faded ghost image), bilingual data fields, an
observation that reveals the country, and a two-line machine-readable
zone with genuine ICAO 9303 check digits.
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

S = 2  # supersample factor; the canvas is drawn at 2x and reduced
W, H = 1024, 768

OUT = "/output/entry.png"

# ---------------------------------------------------------------- fonts
_FONT_DIRS = [
    "/usr/share/fonts/truetype/liberation",
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts",
]


def _font_file(names):
    for name in names:
        for d in _FONT_DIRS:
            p = os.path.join(d, name)
            if os.path.exists(p):
                return p
    return None


def F(kind, size):
    """kind: serif, serifb, sans, sansb, mono, italic. size in final px."""
    table = {
        "serif": ["LiberationSerif-Regular.ttf", "DejaVuSerif.ttf"],
        "serifb": ["LiberationSerif-Bold.ttf", "DejaVuSerif-Bold.ttf"],
        "sans": ["LiberationSans-Regular.ttf", "DejaVuSans.ttf"],
        "sansb": ["LiberationSans-Bold.ttf", "DejaVuSans-Bold.ttf"],
        "mono": ["LiberationMono-Regular.ttf", "DejaVuSansMono.ttf"],
        "italic": ["LiberationSerif-Italic.ttf", "DejaVuSerif-Italic.ttf"],
    }
    path = _font_file(table[kind])
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(path, int(size * S))


# ---------------------------------------------------------------- colours
PAPER = (248, 243, 224)
PAPER_EDGE = (238, 230, 203)
DESK = (172, 164, 148)
DESK_DARK = (148, 139, 120)
NAVY = (29, 53, 87)
GOLD = (168, 132, 44)
INK = (32, 35, 40)
LABEL = (96, 86, 70)
TEAL = (110, 164, 158)
ROSE = (206, 156, 146)
BLUE_INK = (36, 86, 166)
RED_INK = (166, 43, 37)
VIOLET_INK = (107, 63, 160)
GREEN_INK = (30, 110, 62)


def X(v):
    return int(round(v * S))


# ---------------------------------------------------------------- text helpers
def text(d, xy, s, font, fill=INK, anchor="la", tracking=0):
    """Draw text; tracking is extra final-px advance between characters."""
    x, y = xy
    if tracking:
        widths = []
        for ch in s:
            widths.append(d.textlength(ch, font=font))
        total = sum(widths) + tracking * S * (len(s) - 1)
        if anchor[0] == "m":
            x = x - total / (2 * S)
        elif anchor[0] == "r":
            x = x - total / S
        cx = x
        for ch, w in zip(s, widths):
            d.text((X(cx), X(y)), ch, font=font, fill=fill, anchor="la")
            cx += w / S + tracking
        return total / S
    d.text((X(x), X(y)), s, font=font, fill=fill, anchor=anchor)
    return d.textlength(s, font=font) / S


def textw(d, s, font, tracking=0):
    w = d.textlength(s, font=font) / S
    if tracking:
        w += tracking * (len(s) - 1)
    return w


# ---------------------------------------------------------------- MRZ
def _mrz_value(ch):
    if ch.isdigit():
        return int(ch)
    if ch == "<":
        return 0
    return ord(ch) - 55  # A=10 .. Z=35


def mrz_check(field):
    weights = (7, 3, 1)
    total = 0
    for i, ch in enumerate(field):
        total += _mrz_value(ch) * weights[i % 3]
    return str(total % 10)


def build_mrz():
    line1 = "P<VSLMARIN<<ELODIE<CLAIRE"
    line1 = line1 + "<" * (44 - len(line1))
    doc = "C7482913<"
    dob, expiry, personal = "910523", "330109", "9105234471<<<<"
    line2 = (
        doc + mrz_check(doc)
        + "VSL"
        + dob + mrz_check(dob)
        + "F"
        + expiry + mrz_check(expiry)
        + personal + mrz_check(personal)
    )
    composite = line2[0:10] + line2[13:20] + line2[21:43]
    line2 = line2 + mrz_check(composite)
    assert len(line1) == 44 and len(line2) == 44
    return line1, line2


# ---------------------------------------------------------------- guilloche
def guilloche(d, x0, x1, y0, y1):
    """Interlaced sine ribbons in pale inks, clipped to the page rect."""
    step = 4
    ribbons = [
        (TEAL, 26, 0.021, 0.0, 13, 0.043, 1.7),
        (ROSE, 22, 0.017, 2.1, 11, 0.052, 0.4),
        (TEAL, 30, 0.013, 4.0, 9, 0.037, 3.3),
    ]
    mid = (y0 + y1) / 2.0
    for colour, a1, f1, p1, a2, f2, p2 in ribbons:
        for off in (-46, -23, 0, 23, 46):
            pts = []
            x = x0
            while x <= x1:
                t = (x - x0) * S
                yy = mid + off + a1 * math.sin(f1 * t / S + p1) \
                    + a2 * math.sin(f2 * t / S + p2)
                if y0 + 4 <= yy <= y1 - 4:
                    pts.append((X(x), X(yy)))
                x += step
            if len(pts) > 1:
                d.line(pts, fill=colour + (70,) if len(colour) == 3 else colour,
                       width=max(1, X(0.7)))


# ---------------------------------------------------------------- emblem
def draw_emblem(d, cx, top, size, ink=NAVY, accent=GOLD, teal=(46, 110, 104),
               alpha=255):
    """Shield of Vessalia: three stars over a lighthouse standing in waves."""
    w = size
    h = size * 1.18
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = top, top + h
    shield = [
        (x0, y0), (x1, y0), (x1, y0 + h * 0.52),
        (cx + w * 0.30, y0 + h * 0.82), (cx, y1),
        (cx - w * 0.30, y0 + h * 0.82), (x0, y0 + h * 0.52),
    ]
    d.polygon([(X(a), X(b)) for a, b in shield], outline=ink, width=X(2.2))
    inner = [(cx + (a - cx) * 0.88, y0 + (b - y0) * 0.90 + h * 0.03)
             for a, b in shield]
    d.polygon([(X(a), X(b)) for a, b in inner], outline=accent, width=X(1.0))
    # three stars
    for dx in (-0.26, 0.0, 0.26):
        sx, sy, r = cx + dx * w, y0 + h * 0.16, size * 0.075
        star = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            star.append((X(sx + rr * math.cos(ang)), X(sy + rr * math.sin(ang))))
        d.polygon(star, fill=accent)
    # lighthouse tower
    tw = w * 0.15
    base_y = y0 + h * 0.78
    top_y = y0 + h * 0.34
    tower = [(cx - tw, base_y), (cx - tw * 0.62, top_y),
             (cx + tw * 0.62, top_y), (cx + tw, base_y)]
    d.polygon([(X(a), X(b)) for a, b in tower], outline=ink, width=X(1.8))
    for frac in (0.52, 0.66):
        yy = base_y - (base_y - top_y) * frac
        half = tw * (1 - 0.38 * frac)
        d.line([(X(cx - half), X(yy)), (X(cx + half), X(yy))],
               fill=ink, width=X(1.6))
    # lamp room + light
    d.rectangle([X(cx - tw * 0.55), X(top_y - size * 0.075),
                 X(cx + tw * 0.55), X(top_y)], outline=ink, width=X(1.6))
    d.ellipse([X(cx - size * 0.035), X(top_y - size * 0.062),
               X(cx + size * 0.035), X(top_y - size * 0.008)], fill=accent)
    for ang in (-0.5, -0.25, 0.0, 0.25, 0.5):
        ex = cx + math.cos(ang) * w * 0.30
        ey = (top_y - size * 0.035) + math.sin(ang) * w * 0.30
        d.line([(X(cx), X(top_y - size * 0.035)), (X(ex), X(ey))],
               fill=accent, width=X(1.0))
    # waves
    for i, frac in enumerate((0.84, 0.90, 0.96)):
        yy = y0 + h * frac
        d.arc([X(cx - w * 0.30), X(yy - size * 0.05),
               X(cx - w * 0.02), X(yy + size * 0.05)], 0, 180, fill=teal,
              width=X(1.6))
        d.arc([X(cx + w * 0.02), X(yy - size * 0.05),
               X(cx + w * 0.30), X(yy + size * 0.05)], 0, 180, fill=teal,
              width=X(1.6))


# ---------------------------------------------------------------- portrait
def draw_portrait_tile():
    """A stylised drawn portrait of the holder, as a photo tile."""
    pw, ph = X(150), X(190)
    tile = Image.new("RGB", (pw, ph), (203, 214, 216))
    d = ImageDraw.Draw(tile, "RGBA")
    # photo-paper backdrop: soft vertical gradient + fine lines
    for yy in range(ph):
        t = yy / ph
        c = tuple(int(203 + 30 * t) for _ in range(1))
        d.line([(0, yy), (pw, yy)],
               fill=(int(198 + 34 * t), int(210 + 32 * t), int(214 + 30 * t)))
    for yy in range(0, ph, X(5)):
        d.line([(0, yy), (pw, yy)], fill=(255, 255, 255, 26))
    # faint emblem watermark behind the head
    wm = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    draw_emblem(wd, 75, 34, 96, ink=(90, 110, 130), accent=(120, 130, 120),
                teal=(90, 120, 118))
    wm.putalpha(wm.split()[3].point(lambda a: int(a * 0.16)))
    tile.paste(Image.alpha_composite(tile.convert("RGBA"), wm).convert("RGB"),
               (0, 0))
    d = ImageDraw.Draw(tile, "RGBA")
    cx = pw / 2
    skin = (219, 166, 128)
    skin_shade = (203, 146, 108)
    hair = (74, 50, 38)
    # shoulders / sweater
    d.polygon([(X(18), ph), (X(30), X(148)), (X(52), X(128)), (X(98), X(128)),
               (X(120), X(148)), (X(132), ph)], fill=(38, 52, 74))
    d.polygon([(X(58), X(128)), (X(75), X(146)), (X(92), X(128)),
               (X(92), X(122)), (X(58), X(122))], fill=(238, 236, 228))
    # neck
    d.rectangle([X(64), X(104), X(86), X(132)], fill=skin_shade)
    # hair back panel (bob)
    d.ellipse([X(34), X(18), X(116), X(128)], fill=hair)
    d.rectangle([X(34), X(70), X(48), X(126)], fill=hair)
    d.rectangle([X(102), X(70), X(116), X(126)], fill=hair)
    # face
    d.ellipse([X(45), X(26), X(105), X(118)], fill=skin)
    d.ellipse([X(50), X(84), X(70), X(110)], fill=(226, 176, 138))
    d.ellipse([X(80), X(84), X(100), X(110)], fill=(226, 176, 138))
    # hair fringe
    d.pieslice([X(40), X(14), X(110), X(84)], 180, 360, fill=hair)
    d.pieslice([X(40), X(20), X(110), X(80)], 175, 250, fill=hair)
    # brows and eyes (grey eyes)
    d.arc([X(56), X(62), X(70), X(70)], 190, 340, fill=(70, 48, 34),
          width=X(1.6))
    d.arc([X(80), X(62), X(94), X(70)], 200, 350, fill=(70, 48, 34),
          width=X(1.6))
    for ex in (63, 87):
        d.ellipse([X(ex - 5), X(71.6), X(ex + 5), X(78.4)],
                  fill=(244, 244, 240))
        d.ellipse([X(ex - 2.9), X(71), X(ex + 2.9), X(78.8)],
                  fill=(112, 122, 124))
        d.ellipse([X(ex - 1.4), X(72.8), X(ex + 1.4), X(77.2)],
                  fill=(30, 30, 32))
        d.arc([X(ex - 5.4), X(70), X(ex + 5.4), X(77.6)], 180, 360,
              fill=(90, 70, 55), width=X(1.1))
    # nose and mouth
    d.line([(X(75), X(80)), (X(72.6), X(90)), (X(76.4), X(90.6))],
           fill=(188, 128, 92), width=X(1.3))
    d.arc([X(66), X(94), X(84), X(104)], 15, 165, fill=(168, 84, 74),
          width=X(1.8))
    # fine vertical security lines over the photo
    for xx in range(0, pw, X(3)):
        d.line([(xx, 0), (xx, ph)], fill=(255, 255, 255, 14))
    return tile


# ---------------------------------------------------------------- stamps
def stamp_tile(w, h, colour, lines, shape="rect", sub=None):
    """One border-stamp as an RGBA tile. lines: list of (text, size, bold)."""
    tile = Image.new("RGBA", (X(w), X(h)), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    if shape == "rect":
        d.rounded_rectangle([X(3), X(3), X(w - 3), X(h - 3)], radius=X(6),
                            outline=colour, width=X(2.6))
        d.rounded_rectangle([X(7.5), X(7.5), X(w - 7.5), X(h - 7.5)],
                            radius=X(4), outline=colour, width=X(1.0))
    else:  # oval / round
        d.ellipse([X(3), X(3), X(w - 3), X(h - 3)], outline=colour,
                  width=X(2.6))
        d.ellipse([X(8), X(8), X(w - 8), X(h - 8)], outline=colour,
                  width=X(1.0))
    total = sum(sz * 1.28 for _, sz, _ in lines)
    yy = (h - total) / 2 + 1
    for txt, sz, bold in lines:
        f = F("sansb" if bold else "sans", sz)
        text(d, (w / 2, yy), txt, f, fill=colour, anchor="ma", tracking=0.4)
        yy += sz * 1.28
    if sub:
        text(d, (w / 2, h - 15), sub, F("sans", 7.5), fill=colour,
             anchor="ma", tracking=0.6)
    # soften the ink
    alpha = tile.split()[3].point(lambda a: int(a * 0.88))
    tile.putalpha(alpha)
    return tile


def paste_stamp(canvas, tile, x, y, angle):
    r = tile.rotate(angle, expand=True, resample=Image.BICUBIC)
    canvas.paste(r, (X(x), X(y)), r)


# ---------------------------------------------------------------- pages
def draw_page_base(img, x0, x1, y0, y1):
    d = ImageDraw.Draw(img, "RGBA")
    d.rounded_rectangle([X(x0), X(y0), X(x1), X(y1)], radius=X(5),
                        fill=PAPER, outline=PAPER_EDGE, width=X(1.5))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    guilloche(ld, x0 + 10, x1 - 10, y0 + 8, y1 - 8)
    mask = Image.new("L", img.size, 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([X(x0), X(y0), X(x1), X(y1)], radius=X(5), fill=255)
    img.paste(Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB"),
              (0, 0), mask)
    return ImageDraw.Draw(img, "RGBA")


def field(d, x, y, label, value, w=None, vsize=13.5):
    text(d, (x, y), label, F("sans", 8.6), fill=LABEL, anchor="la",
         tracking=0.9)
    text(d, (x, y + 11), value, F("sansb", vsize), fill=INK, anchor="la",
         tracking=0.2)


def signature(d, x, y, w):
    pts = []
    import random
    rnd = random.Random(7)
    xx = x
    while xx < x + w * 0.52:
        pts.append((X(xx), X(y + 8 + 7 * math.sin(xx * 0.55)
                            + rnd.uniform(-1.5, 1.5))))
        xx += 3
    d.line(pts, fill=(24, 40, 90), width=X(1.6))
    d.line([(X(x), X(y + 20)), (X(x + w), X(y + 20))], fill=LABEL,
           width=X(0.8))


def build():
    img = Image.new("RGB", (X(W), X(H)), DESK)
    d = ImageDraw.Draw(img, "RGBA")
    # desk shading: darker toward the corners
    for i in range(28):
        d.rounded_rectangle([X(-30 + i * 2), X(-30 + i * 2),
                             X(W + 30 - i * 2), X(H + 30 - i * 2)],
                            radius=X(20), outline=(0, 0, 0, 3))
    # book shadow + cover edge
    d.rounded_rectangle([X(16), X(26), X(1008), X(744)], radius=X(8),
                        fill=(24, 30, 44))
    d.rounded_rectangle([X(20), X(28), X(1004), X(740)], radius=X(8),
                        fill=(38, 46, 66))

    LX0, LX1, RX0, RX1, PY0, PY1 = 28, 500, 524, 996, 36, 732
    d = draw_page_base(img, LX0, LX1, PY0, PY1)
    d = draw_page_base(img, RX0, RX1, PY0, PY1)
    # spine shadow
    for i in range(16):
        a = int(46 * (1 - i / 16))
        d.line([(X(512 - i), X(PY0 + 4)), (X(512 - i), X(PY1 - 4))],
               fill=(90, 78, 58, a))
        d.line([(X(512 + i), X(PY0 + 4)), (X(512 + i), X(PY1 - 4))],
               fill=(90, 78, 58, a))

    # ============================================================ LEFT PAGE
    cx_l = (LX0 + LX1) / 2
    text(d, (cx_l, 54), "VISAS", F("serifb", 21), fill=NAVY, anchor="ma",
         tracking=3)
    text(d, (cx_l, 82), "VISAS ET TIMBRES · VISAS AND STAMPS",
         F("sans", 9), fill=LABEL, anchor="ma", tracking=1.2)
    d.line([(X(LX0 + 26), X(104)), (X(LX1 - 26), X(104))], fill=GOLD,
           width=X(1.2))
    text(d, (LX1 - 34, 50), "12", F("serif", 13), fill=LABEL, anchor="ma")
    # faint watermark emblem behind the stamps
    wm = Image.new("RGBA", img.size, (0, 0, 0, 0))
    wd = ImageDraw.Draw(wm)
    draw_emblem(wd, cx_l, 300, 150, ink=(120, 128, 140),
                accent=(150, 138, 100), teal=(120, 150, 146))
    wm.putalpha(wm.split()[3].point(lambda a: int(a * 0.10)))
    img.paste(Image.alpha_composite(img.convert("RGBA"), wm).convert("RGB"),
              (0, 0))
    d = ImageDraw.Draw(img, "RGBA")

    # --- Kordavia visa sticker
    vx0, vy0, vx1, vy1 = 54, 118, 336, 238
    d.rounded_rectangle([X(vx0), X(vy0), X(vx1), X(vy1)], radius=X(4),
                        fill=(238, 244, 224), outline=GREEN_INK, width=X(2))
    d.rounded_rectangle([X(vx0 + 5), X(vy0 + 5), X(vx1 - 5), X(vy1 - 5)],
                        radius=X(3), outline=GREEN_INK, width=X(0.8))
    text(d, (vx0 + 16, vy0 + 12), "REPUBLIC OF KORDAVIA", F("sansb", 13),
         fill=(24, 74, 44), tracking=0.5)
    text(d, (vx0 + 16, vy0 + 34), "VISA  № 004417", F("sansb", 12.5),
         fill=INK, tracking=0.5)
    rows = [
        ("TYPE", "SINGLE ENTRY"),
        ("VALID", "10 MAR 2023 — 10 APR 2023"),
        ("HOLDER", "MARIN ELODIE CLAIRE"),
        ("FEE", "PAID · 40 KR · VOSTOK HARBOUR OFFICE"),
    ]
    yy = vy0 + 54
    for k, v in rows:
        text(d, (vx0 + 16, yy), k, F("sans", 8.4), fill=LABEL, tracking=0.8)
        text(d, (vx0 + 62, yy - 2), v, F("sansb", 10.6), fill=INK,
             tracking=0.2)
        yy += 15

    # --- border stamps (one consistent travel history)
    paste_stamp(img, stamp_tile(218, 88, BLUE_INK, [
        ("VESSALIA · PORT AURELIA", 11.5, True),
        ("FERRY TERMINAL — DEPARTURE", 9.5, False),
        ("14 MAR 2023", 14, True)]), 266, 90, 5)
    d = ImageDraw.Draw(img, "RGBA")
    paste_stamp(img, stamp_tile(218, 88, RED_INK, [
        ("KORDAVIA · VOSTOK HARBOUR", 11.5, True),
        ("ENTRY · ADMITTED", 9.5, False),
        ("15 MAR 2023", 14, True)]), 52, 262, -3)
    paste_stamp(img, stamp_tile(218, 88, RED_INK, [
        ("KORDAVIA · VOSTOK HARBOUR", 11.5, True),
        ("EXIT", 9.5, False),
        ("02 APR 2023", 14, True)]), 268, 268, 2)
    paste_stamp(img, stamp_tile(196, 122, VIOLET_INK, [
        ("SAN TELMO", 13, True),
        ("AEROPUERTO INT. — ENTRADA", 9, False),
        ("19 JUN 2024", 13.5, True)], shape="oval"), 58, 384, -5)
    paste_stamp(img, stamp_tile(196, 122, VIOLET_INK, [
        ("SAN TELMO", 13, True),
        ("AEROPUERTO INT. — SALIDA", 9, False),
        ("27 JUN 2024", 13.5, True)], shape="oval"), 282, 392, 3)
    paste_stamp(img, stamp_tile(132, 132, BLUE_INK, [
        ("PORT AURELIA", 11, True),
        ("ENTRY", 10, False),
        ("28 JUN 2024", 11.5, True)], shape="oval"), 192, 520, -2)
    d = ImageDraw.Draw(img, "RGBA")
    text(d, (cx_l, 678),
         "This page is reserved for visas and border stamps.",
         F("italic", 10.5), fill=LABEL, anchor="ma")
    text(d, (cx_l, 694),
         "Cette page est réservée aux visas et aux timbres des postes frontières.",
         F("italic", 10.5), fill=LABEL, anchor="ma")

    # ============================================================ RIGHT PAGE
    cx_r = (RX0 + RX1) / 2
    text(d, (cx_r, 50), "REPUBLIC OF VESSALIA", F("serifb", 27), fill=NAVY,
         anchor="ma", tracking=2.2)
    text(d, (cx_r, 84), "RÉPUBLIQUE DE VESSALIE", F("serif", 12.5),
         fill=LABEL, anchor="ma", tracking=2.6)
    draw_emblem(d, cx_r, 104, 62)
    text(d, (cx_r, 190), "PASSPORT", F("serifb", 16), fill=NAVY,
         anchor="ma", tracking=4)
    text(d, (cx_r, 211), "PASSEPORT", F("serif", 9.5), fill=LABEL,
         anchor="ma", tracking=3)
    d.line([(X(RX0 + 24), X(230)), (X(RX1 - 24), X(230))], fill=GOLD,
           width=X(1.4))

    # type / code / number row
    field(d, RX0 + 26, 240, "TYPE / TYPE", "P", vsize=13)
    field(d, RX0 + 120, 240, "COUNTRY CODE / CODE", "VSL", vsize=13)
    field(d, RX0 + 268, 240, "PASSPORT No / No DE PASSEPORT", "C7482913",
          vsize=13)

    # portrait + ghost image
    tile = draw_portrait_tile()
    img.paste(tile, (X(RX0 + 26), X(282)))
    d = ImageDraw.Draw(img, "RGBA")
    d.rectangle([X(RX0 + 26), X(282), X(RX0 + 176), X(472)], outline=NAVY,
                width=X(1.6))
    ghost = tile.resize((X(92), X(116)), Image.LANCZOS).convert("RGBA")
    ghost.putalpha(ghost.split()[3].point(lambda a: int(a * 0.26)))
    img.paste(ghost, (X(RX1 - 140), X(316)), ghost)
    d = ImageDraw.Draw(img, "RGBA")

    # data fields
    fx = RX0 + 196
    fy = 282
    field(d, fx, fy, "SURNAME / NOM", "MARIN")
    field(d, fx, fy + 38, "GIVEN NAMES / PRÉNOMS", "ELODIE CLAIRE")
    field(d, fx, fy + 76, "NATIONALITY / NATIONALITÉ", "VESSALIAN")
    field(d, fx, fy + 114, "DATE OF BIRTH / DATE DE NAISSANCE",
          "23 MAY 1991")
    field(d, fx, fy + 152, "PLACE OF BIRTH / LIEU DE NAISSANCE",
          "PORT AURELIA")
    field(d, RX0 + 26, 478, "SEX / SEXE", "F", vsize=13)
    field(d, RX0 + 90, 478, "HEIGHT / TAILLE", "168 CM", vsize=13)
    field(d, RX0 + 196, 478, "EYES / YEUX", "GREY", vsize=13)
    field(d, RX0 + 300, 478, "PROFESSION / PROFESSION", "KEEPER OF LIGHTS",
          vsize=13)
    field(d, RX0 + 26, 512, "DATE OF ISSUE / DATE DE DÉLIVRANCE",
          "09 JAN 2023", vsize=13)
    field(d, RX0 + 250, 512, "DATE OF EXPIRY / DATE D'EXPIRATION",
          "09 JAN 2033", vsize=13)
    field(d, RX0 + 26, 548, "AUTHORITY / AUTORITÉ",
          "MINISTRY OF THE INTERIOR — PORT AURELIA", vsize=12)
    signature(d, RX0 + 250, 574, 190)
    text(d, (RX0 + 250, 600), "HOLDER'S SIGNATURE", F("sans", 7.8),
         fill=LABEL, tracking=0.7)
    text(d, (RX0 + 250, 611), "SIGNATURE DU TITULAIRE", F("sans", 7.8),
         fill=LABEL, tracking=0.7)

    # the telling detail: an observation that reveals the country
    text(d, (RX0 + 26, 622), "OBSERVATIONS", F("sans", 8.6), fill=LABEL,
         tracking=0.9)
    text(d, (RX0 + 26, 634),
         "The bearer, a keeper of lights, is exempt from harbour dues in all ports",
         F("italic", 10.5), fill=INK)
    text(d, (RX0 + 26, 648),
         "of the Republic. (Maritime Code, art. 14)",
         F("italic", 10.5), fill=INK)

    # machine-readable zone
    line1, line2 = build_mrz()
    d.rectangle([X(RX0 + 14), X(664), X(RX1 - 14), X(724)], fill=(252, 250, 240))
    mrz_font = F("mono", 16)
    text(d, (RX0 + 30, 672), line1, mrz_font, fill=(20, 20, 20), tracking=0)
    text(d, (RX0 + 30, 696), line2, mrz_font, fill=(20, 20, 20), tracking=0)

    # deterministic paper grain
    grain = Image.new("L", (256, 192), 0)
    px = grain.load()
    seed = 1234567
    for yy in range(192):
        for xx in range(256):
            seed = (seed * 1103515245 + 12345) % (1 << 31)
            px[xx, yy] = 118 + (seed >> 16) % 20
    grain = grain.resize((X(W), X(H)), Image.BICUBIC)
    noise = Image.merge("RGB", (grain, grain, grain))
    img = Image.blend(img, noise, 0.03)

    img = img.resize((W, H), Image.LANCZOS)
    return img


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img = build()
    img.save(OUT, "PNG", optimize=True)
    print("wrote", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
