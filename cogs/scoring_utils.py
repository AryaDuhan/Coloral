import math

def hsb_to_rgb(h, s, b):
    s /= 100.0
    b /= 100.0
    def k(n):
        return (n + h / 60.0) % 6
    def f(n):
        return b * (1 - s * max(0, min(k(n), 4 - k(n), 1)))
    return (round(f(5) * 255), round(f(3) * 255), round(f(1) * 255))

def linearize(c):
    return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)

def rgb_to_xyz(r, g, b):
    rl = linearize(r / 255.0)
    gl = linearize(g / 255.0)
    bl = linearize(b / 255.0)
    return (
        (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) * 100,
        (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) * 100,
        (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) * 100,
    )

def xyz_to_lab(x, y, z):
    Xn, Yn, Zn = 95.047, 100.0, 108.883
    def f(t):
        return math.pow(t, 1/3) if t > 0.008856 else (903.3 * t + 16) / 116
    fx = f(x / Xn)
    fy = f(y / Yn)
    fz = f(z / Zn)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))

def hsb_to_lab(h, s, b):
    r, g, bl = hsb_to_rgb(h, s, b)
    x, y, z = rgb_to_xyz(r, g, bl)
    return xyz_to_lab(x, y, z)

RAD = math.pi / 180
DEG = 180 / math.pi

def ciede2000(lab1, lab2):
    L1, a1, b1 = lab1
    L2, a2, b2 = lab2

    C1 = math.sqrt(a1 * a1 + b1 * b1)
    C2 = math.sqrt(a2 * a2 + b2 * b2)
    Cmean = (C1 + C2) / 2
    Cmean7 = math.pow(Cmean, 7)
    G = 0.5 * (1 - math.sqrt(Cmean7 / (Cmean7 + 6103515625)))

    a1p = a1 * (1 + G)
    a2p = a2 * (1 + G)
    C1p = math.sqrt(a1p * a1p + b1 * b1)
    C2p = math.sqrt(a2p * a2p + b2 * b2)

    h1p = math.atan2(b1, a1p) * DEG
    if h1p < 0: h1p += 360
    h2p = math.atan2(b2, a2p) * DEG
    if h2p < 0: h2p += 360

    dLp = L2 - L1
    dCp = C2p - C1p

    if C1p * C2p == 0:
        dhp = 0
    else:
        dhp = h2p - h1p
        if dhp > 180: dhp -= 360
        if dhp < -180: dhp += 360
    
    dHp = 2 * math.sqrt(C1p * C2p) * math.sin((dhp / 2) * RAD)

    Lpmean = (L1 + L2) / 2
    Cpmean = (C1p + C2p) / 2

    if C1p * C2p == 0:
        hpmean = h1p + h2p
    elif abs(h1p - h2p) <= 180:
        hpmean = (h1p + h2p) / 2
    else:
        hpmean = (h1p + h2p + (360 if h1p + h2p < 360 else -360)) / 2

    T = (1 -
         0.17 * math.cos((hpmean - 30) * RAD) +
         0.24 * math.cos(2 * hpmean * RAD) +
         0.32 * math.cos((3 * hpmean + 6) * RAD) -
         0.20 * math.cos((4 * hpmean - 63) * RAD))

    Lpmean50sq = math.pow(Lpmean - 50, 2)
    SL = 1 + (0.015 * Lpmean50sq) / math.sqrt(20 + Lpmean50sq)
    SC = 1 + 0.045 * Cpmean
    SH = 1 + 0.015 * Cpmean * T

    theta = 30 * math.exp(-math.pow((hpmean - 275) / 25, 2))
    Cpmean7 = math.pow(Cpmean, 7)
    RC = 2 * math.sqrt(Cpmean7 / (Cpmean7 + 6103515625))
    RT = -math.sin(2 * theta * RAD) * RC

    return math.sqrt(
        math.pow(dLp / SL, 2) +
        math.pow(dCp / SC, 2) +
        math.pow(dHp / SH, 2) +
        RT * (dCp / SC) * (dHp / SH)
    )

def delta_e_to_score(dE):
    return 10.0 / (1 + math.pow(dE / 23.0, 1.9))

def hue_diff(h1, h2):
    d = abs(h1 - h2)
    return 360 - d if d > 180 else d

def score_round(target, guess):
    if target["h"] == guess["h"] and target["s"] == guess["s"] and target["b"] == guess["b"]:
        return 10.00

    target_lab = hsb_to_lab(target["h"], target["s"], target["b"])
    guess_lab = hsb_to_lab(guess["h"], guess["s"], guess["b"])
    dE = ciede2000(target_lab, guess_lab)
    base = delta_e_to_score(dE)

    h_diff = hue_diff(target["h"], guess["h"])
    avg_sat = (target["s"] + guess["s"]) / 2

    hue_accuracy = max(0, 1 - math.pow(h_diff / 25.0, 1.5))
    recovery_sat_weight = min(1, avg_sat / 30.0)
    recovery = (10 - base) * hue_accuracy * recovery_sat_weight * 0.25

    hue_pen_factor = max(0, (h_diff - 25.0) / 120.0)
    penalty_sat_weight = min(1, avg_sat / 40.0)
    penalty = base * hue_pen_factor * penalty_sat_weight * 0.20

    score = base + recovery - penalty
    return max(0.0, min(10.0, round(score, 2)))
