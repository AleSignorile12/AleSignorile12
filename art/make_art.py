#!/usr/bin/env python3
"""Pixel art for my GitHub profile.

No libraries: everything is drawn on a small grid of palette colours and written
out as GIFs by hand (LZW and all).

    python3 art/make_art.py

writes art/desk.gif, art/byeclicky.gif, art/dynisland.gif and art/tracker.gif.
"""
import math
import random
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------- palette --
PALETTE = [
    "#0B0E1A",  # INK    night, outlines
    "#141B2E",  # WALL
    "#1E2A45",  # WALL2
    "#2B3B5E",  # FRAME
    "#3E5C8A",  # SKY
    "#7FA6D9",  # GLOW
    "#E8F1FF",  # WHITE
    "#3F96FF",  # BLUE   ByeClicky's cursor
    "#9AA3B5",  # ALU    aluminium
    "#5D6678",  # ALU2
    "#000000",  # BLACK  notch, bezels
    "#F2B45A",  # AMBER
    "#8A4B2A",  # WOOD
    "#B5703F",  # WOOD2
    "#FF4F6D",  # PINK
    "#3FD07A",  # GREEN
]
(INK, WALL, WALL2, FRAME, SKY, GLOW, WHITE, BLUE,
 ALU, ALU2, BLACK, AMBER, WOOD, WOOD2, PINK, GREEN) = range(16)

BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]]

# 3x5 pixel font
FONT = {
    "A": ".#.|#.#|###|#.#|#.#", "B": "##.|#.#|##.|#.#|##.", "C": ".##|#..|#..|#..|.##",
    "D": "##.|#.#|#.#|#.#|##.", "E": "###|#..|##.|#..|###", "F": "###|#..|##.|#..|#..",
    "G": ".##|#..|#.#|#.#|.##", "H": "#.#|#.#|###|#.#|#.#", "I": "###|.#.|.#.|.#.|###",
    "J": "..#|..#|..#|#.#|.#.", "K": "#.#|#.#|##.|#.#|#.#", "L": "#..|#..|#..|#..|###",
    "M": "#.#|###|###|#.#|#.#", "N": "##.|#.#|#.#|#.#|#.#", "O": ".#.|#.#|#.#|#.#|.#.",
    "P": "##.|#.#|##.|#..|#..", "Q": ".#.|#.#|#.#|##.|.##", "R": "##.|#.#|##.|#.#|#.#",
    "S": ".##|#..|.#.|..#|##.", "T": "###|.#.|.#.|.#.|.#.", "U": "#.#|#.#|#.#|#.#|###",
    "V": "#.#|#.#|#.#|#.#|.#.", "W": "#.#|#.#|###|###|#.#", "X": "#.#|#.#|.#.|#.#|#.#",
    "Y": "#.#|#.#|.#.|.#.|.#.", "Z": "###|..#|.#.|#..|###",
    "0": "###|#.#|#.#|#.#|###", "1": ".#.|##.|.#.|.#.|###", "2": "##.|..#|.#.|#..|###",
    "3": "##.|..#|.#.|..#|##.", "4": "#.#|#.#|###|..#|..#", "5": "###|#..|##.|..#|##.",
    "6": ".##|#..|###|#.#|###", "7": "###|..#|.#.|.#.|.#.", "8": "###|#.#|###|#.#|###",
    "9": "###|#.#|###|..#|##.", ":": "...|.#.|...|.#.|...", "?": "##.|..#|.#.|...|.#.",
    ".": "...|...|...|...|.#.", "!": ".#.|.#.|.#.|...|.#.", "'": ".#.|.#.|...|...|...",
    "-": "...|...|###|...|...", "E2": ".##|##.|#..|##.|.##", " ": "...|...|...|...|...",
}
FONT["€"] = FONT.pop("E2")


# ------------------------------------------------------------------ helpers --
def clamp(v, a=0.0, b=1.0):
    return a if v < a else b if v > b else v


def ph(t, a, b):
    """Progress of t through [a, b], clamped to 0..1."""
    return clamp((t - a) / (b - a))


def ease_io(p):
    return 4 * p * p * p if p < 0.5 else 1 - (-2 * p + 2) ** 3 / 2


def ease_out(p):
    return 1 - (1 - p) ** 3


def springy(p):
    """Overshoots a little and settles, like the Dynamic Island."""
    return 1.0 if p >= 1 else 1 - math.exp(-6 * p) * math.cos(10 * p)


def lerp(a, b, p):
    return a + (b - a) * p


class Canvas:
    def __init__(self, w, h, fill=0):
        self.w, self.h = w, h
        self.px = bytearray([fill]) * (w * h)

    def set(self, x, y, c):
        x, y = int(x), int(y)
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = c

    def get(self, x, y):
        return self.px[y * self.w + x]

    def rect(self, x, y, w, h, c):
        x, y, w, h = int(x), int(y), int(w), int(h)
        x0, x1 = max(0, x), min(self.w, x + w)
        if x1 <= x0:
            return
        run = bytes([c]) * (x1 - x0)
        for yy in range(max(0, y), min(self.h, y + h)):
            self.px[yy * self.w + x0: yy * self.w + x1] = run

    def box(self, x, y, w, h, c):
        self.rect(x, y, w, 1, c)
        self.rect(x, y + h - 1, w, 1, c)
        self.rect(x, y, 1, h, c)
        self.rect(x + w - 1, y, 1, h, c)

    def rrect(self, x, y, w, h, c, r=1):
        """Rectangle with r pixels shaved off each corner."""
        for yy in range(h):
            d = min(yy, h - 1 - yy)
            inset = max(0, r - d) if d < r else 0
            self.rect(x + inset, y + yy, w - 2 * inset, 1, c)

    def disc(self, cx, cy, r, c):
        for yy in range(int(cy - r - 1), int(cy + r + 2)):
            for xx in range(int(cx - r - 1), int(cx + r + 2)):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= (r + 0.35) ** 2:
                    self.set(xx, yy, c)

    def ring(self, cx, cy, r, c, upto=1.0):
        steps = max(12, int(r * 8))
        for i in range(int(steps * upto)):
            a = 2 * math.pi * i / steps
            self.set(round(cx + r * math.sin(a)), round(cy - r * math.cos(a)), c)

    def line(self, x0, y0, x1, y1, c):
        x0, y0, x1, y1 = int(round(x0)), int(round(y0)), int(round(x1)), int(round(y1))
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while True:
            self.set(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def dither(self, x, y, w, h, c, level):
        t = level * 16
        for yy in range(max(0, y), min(self.h, y + h)):
            for xx in range(max(0, x), min(self.w, x + w)):
                if BAYER[yy & 3][xx & 3] < t:
                    self.px[yy * self.w + xx] = c

    def sprite(self, x, y, rows, cmap):
        for j, row in enumerate(rows):
            for i, ch in enumerate(row):
                if ch != ".":
                    self.set(x + i, y + j, cmap[ch] if isinstance(cmap, dict) else cmap)

    def text(self, x, y, s, c, scale=1):
        cx = x
        for ch in s:
            rows = FONT.get(ch, FONT[" "]).split("|")
            for j, row in enumerate(rows):
                for i, bit in enumerate(row):
                    if bit == "#":
                        self.rect(cx + i * scale, y + j * scale, scale, scale, c)
            cx += 4 * scale
        return cx - x - scale

    def blit(self, src, dx, dy, clip):
        cx0, cy0, cx1, cy1 = clip
        for y in range(src.h):
            ty = y + dy
            if not (cy0 <= ty < cy1):
                continue
            for x in range(src.w):
                tx = x + dx
                if cx0 <= tx < cx1:
                    self.px[ty * self.w + tx] = src.px[y * src.w + x]


def text_w(s, scale=1):
    return (len(s) * 4 - 1) * scale


def gradient(v, x, y, stops):
    """Colour for value v along [(v0, c0), (v1, c1), ...], dithered between stops."""
    if v <= stops[0][0]:
        return stops[0][1]
    for (v0, c0), (v1, c1) in zip(stops, stops[1:]):
        if v < v1:
            return c1 if BAYER[y & 3][x & 3] < (v - v0) / (v1 - v0) * 16 else c0
    return stops[-1][1]


# ---------------------------------------------------------------- GIF writer --
def lzw(data, mcs):
    clear, eoi = 1 << mcs, (1 << mcs) + 1
    out = bytearray()
    buf = nbits = 0
    size, nxt, table = mcs + 1, eoi + 1, {}
    buf |= clear << nbits
    nbits += size
    prefix = data[0]
    for k in data[1:]:
        key = (prefix << 8) | k
        v = table.get(key)
        if v is not None:
            prefix = v
            continue
        buf |= prefix << nbits
        nbits += size
        while nbits >= 8:
            out.append(buf & 255)
            buf >>= 8
            nbits -= 8
        if nxt < 4096:
            table[key] = nxt
            nxt += 1
            if nxt > (1 << size) and size < 12:
                size += 1
        else:
            buf |= clear << nbits
            nbits += size
            table, size, nxt = {}, mcs + 1, eoi + 1
        prefix = k
    for code in (prefix, eoi):
        buf |= code << nbits
        nbits += size
        while nbits >= 8:
            out.append(buf & 255)
            buf >>= 8
            nbits -= 8
        if code == prefix and nxt < 4096:
            nxt += 1
            if nxt > (1 << size) and size < 12:
                size += 1
    if nbits:
        out.append(buf & 255)
    return out


def write_gif(path, frames, scale, delay_cs):
    seq = []
    for f in frames:
        if seq and seq[-1][0].px == f.px:
            seq[-1][1] += delay_cs
        else:
            seq.append([f, delay_cs])
    w, h = frames[0].w, frames[0].h
    bits = 4
    out = bytearray(b"GIF89a")
    out += struct.pack("<HHBBB", w * scale, h * scale, 0x80 | 0x70 | (bits - 1), 0, 0)
    for hx in PALETTE:
        out += bytes.fromhex(hx[1:])
    out += b"\x21\xff\x0bNETSCAPE2.0\x03\x01\x00\x00\x00"
    prev = None
    for f, delay in seq:
        if prev is None:
            x0, y0, x1, y1 = 0, 0, w, h
        else:
            rows = [y for y in range(h) if f.px[y * w:(y + 1) * w] != prev.px[y * w:(y + 1) * w]]
            y0, y1 = rows[0], rows[-1] + 1
            cols = [x for x in range(w) if any(f.px[y * w + x] != prev.px[y * w + x] for y in range(y0, y1))]
            x0, x1 = cols[0], cols[-1] + 1
        out += struct.pack("<BBBBHBB", 0x21, 0xF9, 4, 1 << 2, delay, 0, 0)
        out += struct.pack("<BHHHHB", 0x2C, x0 * scale, y0 * scale, (x1 - x0) * scale, (y1 - y0) * scale, 0)
        data = bytearray()
        for y in range(y0, y1):
            row = bytes(b for b in f.px[y * w + x0:y * w + x1] for _ in range(scale))
            data += row * scale
        out.append(bits)
        enc = lzw(data, bits)
        for i in range(0, len(enc), 255):
            chunk = enc[i:i + 255]
            out.append(len(chunk))
            out += chunk
        out.append(0)
        prev = f
    out.append(0x3B)
    Path(path).write_bytes(out)
    return len(seq), len(out)


# ---------------------------------------------------------- shared pieces --
CURSOR5 = ["....#", "..###", "#####", "..###", "....#"]
CURSOR7 = ["......#", "....###", "..#####", "#######", "..#####", "....###", "......#"]
CHECK5 = ["....#", "...#.", "#.#..", ".#...", "....."]
DOC = ["####...", "#..##..", "#...##.", "#.....#", "#.###.#", "#.....#", "#.###.#", "#.....#", "#######"]
CAKE = ["..f..", "..c..", "ppppp", "bpbpb", "bbbbb"]
SHARE = ["..#..", ".###.", "#.#.#", "#...#", "#####"]
GRID = ["##.##", "##.##", ".....", "##.##", "##.##"]
TAG = ["###..", "####.", "#####", "####.", "###.."]
CTRL = ["..#..", ".#.#.", "#...#", ".....", "....."]
OPT = ["##.##", "..#..", "..#..", "...#.", "...##"]
FOLDER = ["###......", "#########", "#########", "#########", "#########", "#########"]
PERSON = [".###.", ".###.", "..#..", "#####", "#.#.#"]
SPEAKER = ["..#", ".##", "###", ".##", "..#"]


def cursor(c, tx, ty, big=False):
    rows = CURSOR7 if big else CURSOR5
    oy = len(rows) // 2
    if big:  # soft glow around the cursor, like the app's icon
        pts = {(i, j) for j, r in enumerate(rows) for i, ch in enumerate(r) if ch == "#"}
        for (i, j) in pts:
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                if (i + di, j + dj) not in pts:
                    c.set(tx + i + di, ty - oy + j + dj, GLOW)
    c.sprite(tx, ty - oy, rows, BLUE)


def click_ring(c, tx, ty, p, r_max=4):
    if 0 < p < 1:
        c.ring(tx, ty, 1 + (r_max - 1) * ease_out(p), GLOW)


def island(c, cx, top, w, h):
    w, h = max(2, int(round(w))), max(1, int(round(h)))
    x0 = cx - w // 2
    for yy in range(h):
        from_bottom = h - 1 - yy
        inset = 0
        if from_bottom == 0:
            inset = 2 if h >= 9 else 1
        elif from_bottom == 1 and h >= 9:
            inset = 1
        c.rect(x0 + inset, top + yy, w - 2 * inset, 1, BLACK)
    return x0, x0 + w - 1


def confetti(c, t, t0, ox, oy, n=16, seed=7, spread=14, lift=(18, 38), clip=None):
    if not (t0 <= t < t0 + 1.2):
        return
    rnd = random.Random(seed)
    dt = t - t0
    for k in range(n):
        vx, vy = rnd.uniform(-spread, spread), -rnd.uniform(*lift)
        x, y = ox + vx * dt, oy + vy * dt + 0.5 * 42 * dt * dt
        if clip and not (clip[0] <= x < clip[2] and clip[1] <= y < clip[3]):
            continue
        c.set(x, y, (PINK, AMBER, BLUE, GREEN)[k % 4])


# ------------------------------------------------------------------ banner --
def desk(i, n):
    T = 5.12
    t = i / n * T
    c = Canvas(160, 96, WALL)

    # window: night sky, moon, stars, hills with a few lights
    gx0, gy0, gx1, gy1 = 8, 8, 48, 44
    sky = [(0, INK), (12, INK), (20, WALL), (28, WALL2), (36, FRAME)]
    for y in range(gy0, gy1):
        for x in range(gx0, gx1):
            c.set(x, y, gradient(y - gy0, x, y, sky))
    for y in range(gy0, gy1):
        for x in range(gx0, gx1):
            d = math.hypot(x - 39, y - 15)
            if 4.6 < d < 6.6 and BAYER[y & 3][x & 3] < 4:
                c.set(x, y, SKY)
    c.disc(39, 15, 4, WHITE)
    c.disc(41, 13, 4, INK)
    for k, (sx, sy) in enumerate([(11, 10), (16, 17), (22, 12), (31, 9), (25, 21), (13, 26),
                                  (45, 26), (33, 20), (19, 31), (36, 29), (30, 33), (44, 32)]):
        b = (i + k * 5) % 16
        col = WHITE if 4 <= b <= 10 else GLOW if b in (2, 3, 11, 12) else None
        if col is not None:
            c.set(sx, sy, col)
            if k in (2, 6) and col == WHITE:
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    c.set(sx + dx, sy + dy, GLOW)
    p = ph(t, 3.6, 4.05)
    if 0 < p < 1:
        hx, hy = lerp(10, 36, p), lerp(9, 21, p)
        for j, col in enumerate((WHITE, GLOW, GLOW, SKY, SKY, FRAME)):
            x, y = hx - j * 2, hy - j
            if gx0 <= x < gx1 and gy0 <= y < gy1:
                c.set(x, y, col)
                c.set(x - 1, y, col)
    for x in range(gx0, gx1):
        top = 38 + round(2 * math.sin(x * 0.25) + 1.5 * math.sin(x * 0.11 + 1))
        c.rect(x, top, 1, gy1 - top, INK)
    for k, (lx, ly) in enumerate([(12, 41), (19, 40), (33, 42), (42, 41)]):
        if (i // 8 + k) % 3:
            c.set(lx, ly, AMBER)
    c.box(6, 6, 44, 40, FRAME)
    c.box(7, 7, 42, 38, FRAME)
    c.rect(27, 8, 2, 36, FRAME)
    c.rect(8, 25, 40, 2, FRAME)
    c.rect(4, 46, 48, 2, ALU2)

    # clock: the second hand does one lap per loop
    c.disc(142, 18, 9, ALU2)
    c.disc(142, 18, 8, WHITE)
    for dx, dy in ((0, -7), (7, 0), (0, 7), (-7, 0)):
        c.set(142 + dx, 18 + dy, INK)
    c.line(142, 18, 142 - 3, 18 - 3, INK)
    c.line(142, 18, 142 + 4, 18 - 4, INK)
    a = 2 * math.pi * t / T
    c.line(142, 18, 142 + 6 * math.sin(a), 18 - 6 * math.cos(a), PINK)
    c.set(142, 18, INK)

    # desk
    c.rect(0, 68, 160, 28, WOOD)
    c.rect(0, 68, 160, 1, WOOD2)
    rnd = random.Random(3)
    for gy in (74, 80, 87, 92):
        x = rnd.randint(0, 20)
        while x < 160:
            ln = rnd.randint(6, 18)
            c.rect(x, gy, ln, 1, WOOD2)
            x += ln + rnd.randint(10, 30)
    c.rect(47, 68, 74, 1, INK)

    # plant
    sway = round(math.sin(2 * math.pi * t / 2.56))
    plant = ["..#...#...", "..#..##...", ".##..##.#.", ".##..#..#.", ".##.##.##.",
             ".#..##.##.", "##.###.#..", ".#.###.#..", ".#######.."]
    for j, row in enumerate(plant):
        for k, ch in enumerate(row):
            if ch == "#":
                c.set(9 + k + (sway if j < 3 else 0), 52 + j, GREEN)
    c.rect(9, 61, 10, 1, ALU)
    c.rect(10, 62, 8, 6, ALU2)

    # mug and steam
    c.rect(28, 59, 8, 9, AMBER)
    c.rect(35, 59, 1, 9, WOOD2)
    for (x, y) in [(36, 61), (37, 61), (38, 62), (38, 63), (38, 64), (37, 65), (36, 65)]:
        c.set(x, y, AMBER)
    for k in range(2):
        phase = (t / 1.28 + k / 2) % 1
        head = 57 - phase * 12
        for j in range(5):
            yy = round(head - j)
            if yy < 46:
                continue
            xx = 30 + k * 3 + round(1.4 * math.sin(yy * 0.55 + k * 2))
            c.set(xx, yy, GLOW if j < 3 else SKY)

    # MacBook
    c.rect(50, 16, 68, 48, ALU2)
    c.rect(51, 17, 66, 47, BLACK)
    for y in range(22, 62):
        for x in range(53, 115):
            v = (y - 22) + 3 * math.sin(x * 0.15 + 0.5)
            c.set(x, y, gradient(v, x, y, [(0, SKY), (8, FRAME), (22, FRAME), (30, WALL2)]))
    c.rect(53, 19, 62, 3, WALL)
    c.rect(55, 20, 3, 1, WHITE)
    c.rect(108, 20, 5, 1, WHITE)
    c.rect(46, 64, 76, 2, ALU)
    c.rect(46, 66, 76, 1, ALU2)
    c.rect(78, 64, 12, 1, ALU2)
    # a window with a button
    c.rect(63, 28, 42, 28, INK)
    c.rect(62, 27, 42, 28, WHITE)
    c.rect(62, 27, 42, 3, ALU)
    for x, col in ((64, PINK), (66, AMBER), (68, GREEN)):
        c.set(x, 28, col)
    for (x, y, w) in ((65, 33, 24), (65, 36, 18), (65, 39, 28), (65, 42, 14)):
        c.rect(x, y, w, 1, ALU)
    hover = 1.4 <= t < 3.6
    pressed = 1.4 <= t < 1.55
    c.rect(89, 48, 12, 4, FRAME if pressed else BLUE if hover else ALU)
    c.rect(92, 49, 6, 1, WHITE)
    c.rect(92, 50, 4, 1, WHITE)

    # ByeClicky: flies to the button, clicks, talks, flies home
    rest, target = (60, 57), (102, 49)
    if t < 0.4 or t >= 4.7:
        tx, ty = rest
    elif t < 1.4:
        q = ph(t, 0.4, 1.4)
        tx = lerp(rest[0], target[0], ease_io(q))
        ty = lerp(rest[1], target[1], ease_out(q)) - 7 * math.sin(math.pi * q)
    elif t < 3.6:
        tx, ty = target
    else:
        q = ph(t, 3.6, 4.7)
        tx = lerp(target[0], rest[0], ease_io(q))
        ty = lerp(target[1], rest[1], ease_io(q)) + 3 * math.sin(math.pi * q)
    tx, ty = round(tx), round(ty)
    click_ring(c, tx, ty, ph(t, 1.4, 1.8))
    cursor(c, tx, ty)
    if 1.8 <= t < 3.5:
        c.rrect(96, 39, 15, 7, BLUE)
        c.set(104, 46, BLUE)
        dots = 1 + int((t - 1.8) / 0.22) % 3
        for d in range(dots):
            c.set(100 + d * 3, 42, WHITE)

    # Dynisland in the notch: music, then a timer
    w, h, mode = 8, 3, None
    if 0.8 <= t < 2.65:
        e = springy(ph(t, 0.8, 1.15)) if t < 2.4 else 1 - ease_io(ph(t, 2.4, 2.65))
        w, h = lerp(8, 26, e), lerp(3, 7, e)
        mode = "music" if 1.0 <= t < 2.42 else None
    elif 3.0 <= t < 4.7:
        e = springy(ph(t, 3.0, 3.35)) if t < 4.45 else 1 - ease_io(ph(t, 4.45, 4.7))
        w, h = lerp(8, 26, e), lerp(3, 7, e)
        mode = "timer" if 3.2 <= t < 4.47 else None
    x0, x1 = island(c, 84, 19, w, h)
    if mode == "music":
        c.rect(x0 + 2, 20, 5, 5, PINK)
        c.set(x0 + 3, 21, AMBER)
        for k in range(3):
            bh = 1 + round(2 + 2 * math.sin(t * 9 + k * 1.7))
            c.rect(x1 - 6 + k * 2, 25 - bh, 1, bh, BLUE)
    elif mode == "timer":
        c.ring(x0 + 4, 22, 1.5, AMBER)
        left = max(1, 5 - int((t - 3.2) / 0.25))
        c.text(x0 + 8, 20, f"0:0{left}", WHITE)

    # Tracker on the phone: kids get ticked off, then a birthday
    c.rect(127, 64, 13, 4, ALU2)
    c.rect(125, 34, 15, 31, ALU2)
    c.rect(126, 35, 13, 29, BLACK)
    c.rect(127, 36, 11, 27, WHITE)
    c.rect(131, 37, 3, 1, BLACK)
    c.rect(127, 39, 11, 3, BLUE)
    c.rect(129, 40, 4, 1, WHITE)
    checked = sum(t >= s for s in (0.5, 1.0, 1.5, 2.0)) - sum(t >= s for s in (4.6, 4.7, 4.8, 4.9))
    for k, ry in enumerate((44, 49, 54, 59)):
        if k < checked:
            c.rect(128, ry, 3, 3, GREEN)
        else:
            c.box(128, ry, 3, 3, ALU)
        c.rect(132, ry + 1, 5 - (k % 2), 1, ALU)
    confetti(c, t, 2.3, 132, 36)
    return c


# --------------------------------------------------------------- ByeClicky --
def byeclicky(i, n):
    T = 6.4
    t = i / n * T
    c = Canvas(128, 72)
    for y in range(72):
        for x in range(128):
            v = y + 4 * math.sin(x * 0.07)
            c.set(x, y, gradient(v, x, y, [(4, SKY), (18, FRAME), (40, WALL2), (66, WALL)]))
    c.rect(0, 0, 128, 7, WALL)
    c.text(4, 1, "FINDER  FILE  EDIT", WHITE)
    c.sprite(103, 1, ["..#", ".##", "###", ".##", "..#"], BLUE)
    c.text(112, 1, "9:41", WHITE)

    # Finder window
    c.rect(13, 13, 88, 47, INK)
    c.rect(12, 12, 88, 47, WHITE)
    c.rect(12, 12, 88, 9, ALU)
    for x, col in ((15, PINK), (19, AMBER), (23, GREEN)):
        c.rect(x, 15, 2, 2, col)
    c.text(29, 14, "DOWNLOADS", INK)
    hover = 3.5 <= t < 5.4
    for bx, icon in ((66, GRID), (76, SHARE), (86, TAG)):
        lit = hover and icon is SHARE
        c.rrect(bx, 13, 9, 7, WHITE if lit else ALU)
        c.sprite(bx + 2, 14, icon, BLUE if lit else ALU2)
    for k in range(8):
        fx, fy = 18 + (k % 4) * 20, 26 + (k // 4) * 16
        c.sprite(fx, fy, FOLDER, BLUE)
        c.rect(fx, fy + 1, 3, 1, GLOW)
        c.rect(fx - 1, fy + 8, 11, 1, ALU)

    # hold Control + Option and ask
    held = 0.4 <= t < 2.4
    for kx, sym in ((3, CTRL), (15, OPT)):
        dy = 1 if held else 0
        if not held:
            c.rrect(kx, 62, 11, 9, ALU2)
        c.rrect(kx, 61 + dy, 11, 8, ALU)
        c.sprite(kx + 3, 62 + dy, sym, BLUE if held else INK)
    if 0.55 <= t < 2.4:
        for k in range(5):
            bh = 1 + round(3 + 3 * math.sin(t * 11 + k * 1.3) * math.sin(t * 3 + k))
            bh = max(1, min(7, bh))
            c.rect(29 + k * 2, 66 - bh // 2, 1, bh, BLUE)
    question = "WHERE'S SHARE?"
    if 0.7 <= t < 5.4:
        shown = question[:int(clamp((t - 0.7) / 1.4) * len(question) + 0.999)]
        c.rrect(41, 61, 61, 10, ALU2)
        c.rect(42, 62, 59, 8, WHITE)
        c.text(44, 63, shown, INK)

    # ByeClicky flies to Share, clicks it and answers
    rest, target = (106, 47), (85, 16)
    if t < 2.6 or t >= 6.2:
        tx, ty = rest
    elif t < 3.5:
        q = ph(t, 2.6, 3.5)
        tx = lerp(rest[0], target[0], ease_io(q))
        ty = lerp(rest[1], target[1], ease_out(q)) - 4 * math.sin(math.pi * q)
    elif t < 5.4:
        tx, ty = target
    else:
        q = ph(t, 5.4, 6.2)
        tx = lerp(target[0], rest[0], ease_io(q))
        ty = lerp(target[1], rest[1], ease_io(q))
    tx, ty = round(tx), round(ty)
    click_ring(c, tx, ty, ph(t, 3.5, 3.9), 6)
    cursor(c, tx, ty, big=True)
    if 3.8 <= t < 5.4:
        c.rrect(56, 24, 50, 9, BLUE)
        c.rect(87, 23, 3, 1, BLUE)
        c.set(88, 22, BLUE)
        msg = "RIGHT HERE!"
        c.text(59, 26, msg[:int(clamp((t - 3.8) / 0.5) * len(msg) + 0.999)], WHITE)
    return c


# --------------------------------------------------------------- Dynisland --
def dynisland(i, n):
    T = 6.4
    t = i / n * T
    c = Canvas(128, 40)
    for y in range(40):
        for x in range(128):
            v = y + 3 * math.sin(x * 0.09 + 1)
            c.set(x, y, gradient(v, x, y, [(8, SKY), (20, FRAME), (34, WALL2)]))
    c.rect(0, 0, 128, 3, BLACK)
    c.rect(0, 3, 128, 7, WALL)
    c.text(4, 4, "FINDER", WHITE)
    c.text(112, 4, "9:41", WHITE)

    def size(a, b, w1, h1, out_at, end):
        if t < out_at:
            e = springy(ph(t, a, b))
        else:
            e = 1 - ease_io(ph(t, out_at, end))
        return lerp(24, w1, e), lerp(7, h1, e)

    w, h, mode = 24, 7, None
    file_y = None
    if 0.5 <= t < 2.5:
        w, h = size(0.5, 0.85, 84, 17, 2.2, 2.5)
        mode = "music" if 0.7 <= t < 2.22 else None
    elif 2.6 <= t < 4.25:
        if t < 3.1:
            file_y = lerp(42, 10, ease_io(ph(t, 2.6, 3.1)))
            e = springy(ph(t, 2.85, 3.1)) if t >= 2.85 else 0
        else:
            e = 1 if t < 4.0 else 1 - ease_io(ph(t, 4.0, 4.25))
        w, h = lerp(24, 64, e), lerp(7, 15, e)
        mode = "drop" if 2.95 <= t < 3.1 else "file" if 3.1 <= t < 4.02 else None
    elif 4.4 <= t < 6.25:
        w, h = size(4.4, 4.7, 50, 11, 6.0, 6.25)
        mode = "timer" if 4.6 <= t < 6.02 else None
    x0, x1 = island(c, 64, 3, w, h)
    if mode is None and w < 26:
        c.set(64, 5, WALL2)
    if mode == "music":
        c.rect(x0 + 4, 5, 11, 11, PINK)
        c.disc(x0 + 7, 8, 1.5, AMBER)
        for x in range(11):
            top = 12 + round(math.sin(x * 0.7))
            c.rect(x0 + 4 + x, top, 1, 16 - top, INK)
        c.text(x0 + 18, 6, "MOONLIGHT", WHITE)
        c.text(x0 + 18, 12, "DJ PIXEL", ALU2)
        for k in range(4):
            bh = max(2, min(9, round(5 + 4 * math.sin(t * 8 + k * 1.9))))
            c.rect(x1 - 13 + k * 3, 16 - bh, 2, bh, BLUE)
    elif mode == "drop":
        for x in range(x0 + 3, x1 - 2, 2):
            c.set(x, 5, GLOW)
            c.set(x, 3 + int(h) - 3, GLOW)
    elif mode == "file":
        c.sprite(x0 + 5, 5, DOC, {"#": WHITE})
        c.rect(x0 + 7, 9, 3, 1, BLUE)
        c.rect(x0 + 7, 11, 3, 1, BLUE)
        c.text(x0 + 16, 8, "1 FILE", WHITE)
    elif mode == "timer":
        left = 3 - int((t - 4.7) / 0.3) if t >= 4.7 else 3
        done = left <= 0
        col = GREEN if done else AMBER
        frac = 1 if done else clamp((left - (t - 4.7) % 0.3 / 0.3) / 3) if t >= 4.7 else 1
        c.ring(x0 + 7, 8, 3, ALU2)
        c.ring(x0 + 7, 8, 3, col, upto=frac)
        c.text(x0 + 16, 6, "DONE!" if done else f"00:0{left}", GREEN if done else WHITE)
    if file_y is not None:
        c.sprite(60, round(file_y), DOC, {"#": WHITE})
        c.rect(62, round(file_y) + 4, 3, 1, BLUE)
        c.rect(62, round(file_y) + 6, 3, 1, BLUE)
        cursor(c, 66, round(file_y) + 8)
    return c


# ----------------------------------------------------------------- Tracker --
KIDS = [("LUCA", BLUE), ("SOFIA", PINK), ("MATEO", AMBER), ("AMIRA", GREEN), ("IVAN", GLOW)]
SW, SH = 50, 92


def status_bar(s):
    s.rect(0, 0, SW, 7, WHITE)
    s.text(3, 1, "9:41", INK)
    s.rrect(19, 1, 12, 4, BLACK)


def tab_bar(s, active):
    s.rect(0, 83, SW, 1, ALU)
    icons = [["#####", "#...#", "#.#.#", "#####", ".#..."], PERSON,
             [".##", "##.", "#..", "##.", ".##"], ["....#", "...#.", "#.#..", ".#...", "....."]]
    for k, icon in enumerate(icons):
        s.sprite(5 + k * 12, 86, icon, BLUE if k == active else ALU2)


def kids_screen(t):
    s = Canvas(SW, SH, WHITE)
    status_bar(s)
    s.text(3, 9, "KIDS", INK, scale=2)
    paid = sum(t >= x for x in (0.6, 1.0, 1.4, 1.8)) if t < 6.85 else 0
    birthday = 2.2 <= t < 6.85
    for k, (name, col) in enumerate(KIDS):
        y = 22 + k * 12
        s.disc(6, y + 4, 3, col)
        s.text(13, y + 2, name, INK)
        if k == 1 and birthday:
            s.sprite(13 + text_w(name) + 2, y + 1, CAKE, {"f": AMBER, "c": BLUE, "p": PINK, "b": WOOD2})
        if k < paid:
            s.sprite(42, y + 2, CHECK5, GREEN)
        else:
            s.text(36, y + 2, "30€", ALU2)
        s.rect(13, y + 10, SW - 15, 1, ALU)
    tab_bar(s, 1)
    return s


def translator_screen(t):
    s = Canvas(SW, SH, WHITE)
    status_bar(s)
    s.text(3, 10, "TRANSLATE", INK)
    s.rrect(3, 18, 44, 24, ALU)
    s.rrect(4, 19, 42, 22, WHITE)
    s.text(7, 22, "EN", BLUE)
    hello = "HELLO!"
    s.text(7, 31, hello[:int(clamp((t - 4.1) / 0.6) * len(hello) + 0.999)] if t >= 4.1 else "", INK)
    s.sprite(22, 44, [".#.#.", "##.#.", ".#.#.", ".#.##", ".#.#."], BLUE)
    s.rrect(3, 51, 44, 28, ALU)
    s.rrect(4, 52, 42, 26, WHITE)
    s.text(7, 55, "HR", BLUE)
    bok = "BOK!"
    if t >= 4.9:
        s.text(7, 64, bok[:int(clamp((t - 4.9) / 0.4) * len(bok) + 0.999)], INK, scale=2)
    if t >= 5.4:
        s.sprite(37, 55, SPEAKER, ALU2)
        if 5.5 <= t < 6.6:
            waves = 1 + int((t - 5.5) / 0.18) % 3
            for wv in range(waves):
                s.set(41 + wv * 2, 56, BLUE)
                s.set(41 + wv * 2, 57, BLUE)
                s.set(41 + wv * 2, 58, BLUE)
    tab_bar(s, 0)
    return s


def tracker(i, n):
    T = 7.2
    t = i / n * T
    c = Canvas(120, 100)
    for y in range(100):
        for x in range(120):
            c.set(x, y, gradient(y + 6 * math.sin(x * 0.05), x, y, [(10, FRAME), (60, WALL2), (100, WALL)]))
    c.rrect(32, 1, 56, 98, ALU2, r=4)
    c.rrect(33, 2, 54, 96, BLACK, r=4)
    clip = (35, 4, 35 + SW, 4 + SH)
    if t < 3.6:
        c.blit(kids_screen(t), 35, 4, clip)
    elif t < 3.95:
        off = round(SW * ease_io(ph(t, 3.6, 3.95)))
        c.blit(kids_screen(t), 35 - off, 4, clip)
        c.blit(translator_screen(t), 35 + SW - off, 4, clip)
    elif t < 6.85:
        c.blit(translator_screen(t), 35, 4, clip)
    else:
        off = round(SW * ease_io(ph(t, 6.85, 7.2)))
        c.blit(translator_screen(t), 35 + off, 4, clip)
        c.blit(kids_screen(t), 35 - SW + off, 4, clip)
    for (x, y) in [(35, 4), (36, 4), (35, 5), (84, 4), (83, 4), (84, 5),
                   (35, 95), (36, 95), (35, 94), (84, 95), (83, 95), (84, 94)]:
        c.set(x, y, BLACK)
    if t < 3.6:
        confetti(c, t, 2.2, 66, 38, n=22, seed=11, spread=18, lift=(14, 30), clip=clip)
    return c


# -------------------------------------------------------------------- main --
def render(name, fn, n, scale, delay_cs=8):
    frames = [fn(i, n) for i in range(n)]
    unique, size = write_gif(HERE / f"{name}.gif", frames, scale, delay_cs)
    print(f"{name}.gif  {frames[0].w * scale}x{frames[0].h * scale}  {unique} frames  {size // 1024} KB")


if __name__ == "__main__":
    render("desk", desk, 64, 5)
    render("byeclicky", byeclicky, 80, 5)
    render("dynisland", dynisland, 80, 5)
    render("tracker", tracker, 90, 4)
