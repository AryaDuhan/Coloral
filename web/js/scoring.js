/**
 * scoring.js — CIEDE2000 color scoring pipeline.
 *
 * Pipeline: HSB → RGB → XYZ (D65) → CIELAB → CIEDE2000 ΔE → S-curve → hue adjustments
 * Matches dialed.gg's scoring system (midpoint 25.25, k 0.18, recovery 0.25, penalty 0.15).
 */

// ── Color Space Conversions ────────────────────────────────────────────────────

/** HSB (H 0-360, S 0-100, B 0-100) → RGB (0-255 each) */
export function hsbToRgb(h, s, b) {
  s /= 100;
  b /= 100;
  const k = (n) => (n + h / 60) % 6;
  const f = (n) => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
  return [Math.round(f(5) * 255), Math.round(f(3) * 255), Math.round(f(1) * 255)];
}

/** HSB → CSS color string */
export function hsbToCss(h, s, b) {
  const [r, g, bl] = hsbToRgb(h, s, b);
  return `rgb(${r}, ${g}, ${bl})`;
}

/** Get a contrasting text color for readability on a given HSB background */
export function getTextColor(h, s, b) {
  const [r, g, bl] = hsbToRgb(h, s, b);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * bl) / 255;
  return luminance > 0.5 ? 'rgba(0,0,0,0.7)' : 'rgba(255,255,255,0.7)';
}

/** Linearize an sRGB channel (0-1 range) */
function linearize(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

/** RGB (0-255) → XYZ (D65 illuminant, scaled 0-100) */
function rgbToXyz(r, g, b) {
  const rl = linearize(r / 255);
  const gl = linearize(g / 255);
  const bl = linearize(b / 255);
  return [
    (rl * 0.4124564 + gl * 0.3575761 + bl * 0.1804375) * 100,
    (rl * 0.2126729 + gl * 0.7151522 + bl * 0.0721750) * 100,
    (rl * 0.0193339 + gl * 0.1191920 + bl * 0.9503041) * 100,
  ];
}

/** XYZ → CIELAB (D65 white point) */
function xyzToLab(x, y, z) {
  const Xn = 95.047, Yn = 100.0, Zn = 108.883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : (903.3 * t + 16) / 116);
  const fx = f(x / Xn), fy = f(y / Yn), fz = f(z / Zn);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

/** HSB → CIELAB (convenience) */
function hsbToLab(h, s, b) {
  return xyzToLab(...rgbToXyz(...hsbToRgb(h, s, b)));
}

// ── CIEDE2000 ──────────────────────────────────────────────────────────────────

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

/**
 * Compute the CIEDE2000 perceptual color difference.
 * Reference: "The CIEDE2000 Color-Difference Formula" (Sharma, Wu, Dalal, 2005)
 */
function ciede2000(lab1, lab2) {
  const [L1, a1, b1] = lab1;
  const [L2, a2, b2] = lab2;

  // 1. Cab, mean Cab, G factor
  const C1 = Math.sqrt(a1 * a1 + b1 * b1);
  const C2 = Math.sqrt(a2 * a2 + b2 * b2);
  const Cmean = (C1 + C2) / 2;
  const Cmean7 = Math.pow(Cmean, 7);
  const G = 0.5 * (1 - Math.sqrt(Cmean7 / (Cmean7 + 6103515625))); // 25^7

  // 2. a', C', h'
  const a1p = a1 * (1 + G);
  const a2p = a2 * (1 + G);
  const C1p = Math.sqrt(a1p * a1p + b1 * b1);
  const C2p = Math.sqrt(a2p * a2p + b2 * b2);

  let h1p = Math.atan2(b1, a1p) * DEG;
  if (h1p < 0) h1p += 360;
  let h2p = Math.atan2(b2, a2p) * DEG;
  if (h2p < 0) h2p += 360;

  // 3. ΔL', ΔC', Δh', ΔH'
  const dLp = L2 - L1;
  const dCp = C2p - C1p;

  let dhp;
  if (C1p * C2p === 0) {
    dhp = 0;
  } else {
    dhp = h2p - h1p;
    if (dhp > 180) dhp -= 360;
    if (dhp < -180) dhp += 360;
  }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin((dhp / 2) * RAD);

  // 4. Means for weighting
  const Lpmean = (L1 + L2) / 2;
  const Cpmean = (C1p + C2p) / 2;

  let hpmean;
  if (C1p * C2p === 0) {
    hpmean = h1p + h2p;
  } else if (Math.abs(h1p - h2p) <= 180) {
    hpmean = (h1p + h2p) / 2;
  } else {
    hpmean = (h1p + h2p + (h1p + h2p < 360 ? 360 : -360)) / 2;
  }

  // 5. T, SL, SC, SH, RT
  const T =
    1 -
    0.17 * Math.cos((hpmean - 30) * RAD) +
    0.24 * Math.cos(2 * hpmean * RAD) +
    0.32 * Math.cos((3 * hpmean + 6) * RAD) -
    0.20 * Math.cos((4 * hpmean - 63) * RAD);

  const Lpmean50sq = Math.pow(Lpmean - 50, 2);
  const SL = 1 + (0.015 * Lpmean50sq) / Math.sqrt(20 + Lpmean50sq);
  const SC = 1 + 0.045 * Cpmean;
  const SH = 1 + 0.015 * Cpmean * T;

  const theta = 30 * Math.exp(-Math.pow((hpmean - 275) / 25, 2));
  const Cpmean7 = Math.pow(Cpmean, 7);
  const RC = 2 * Math.sqrt(Cpmean7 / (Cpmean7 + 6103515625));
  const RT = -Math.sin(2 * theta * RAD) * RC;

  // 6. Final ΔE
  return Math.sqrt(
    Math.pow(dLp / SL, 2) +
    Math.pow(dCp / SC, 2) +
    Math.pow(dHp / SH, 2) +
    RT * (dCp / SC) * (dHp / SH)
  );
}

// ── Scoring ────────────────────────────────────────────────────────────────────

/**
 * S-curve mapping from CIEDE2000 ΔE to a 0-10 base score.
 * Midpoint 25.25 (score crosses 5/10), steepness 1.55.
 * Generous for close matches, punishing for misses.
 */
function deltaEToScore(dE) {
  // Fair midpoint 23.0, custom strictness
  return 10 / (1 + Math.pow(dE / 23.0, 1.9));
}

/** Absolute hue difference in degrees (wraps around 360°) */
function hueDiff(h1, h2) {
  let d = Math.abs(h1 - h2);
  return d > 180 ? 360 - d : d;
}

/**
 * Score a single round with full pipeline:
 *   1. CIEDE2000 base score (S-curve)
 *   2. Hue recovery (rewards remembering the right color family)
 *   3. Hue penalty (punishes wrong hue on vivid colors)
 *
 * @param {{ h: number, s: number, b: number }} target  Target color (HSB)
 * @param {{ h: number, s: number, b: number }} guess   Player's guess (HSB)
 * @returns {number} Score from 0.00 to 10.00
 */
export function scoreRound(target, guess) {
  // Perfect match shortcut
  if (target.h === guess.h && target.s === guess.s && target.b === guess.b) {
    return 10.00;
  }

  // Base score from CIEDE2000
  const targetLab = hsbToLab(target.h, target.s, target.b);
  const guessLab = hsbToLab(guess.h, guess.s, guess.b);
  const dE = ciede2000(targetLab, guessLab);
  let base = deltaEToScore(dE);

  // 2. Hue recovery — reward getting the color family right
  const hDiff = hueDiff(target.h, guess.h);
  const avgSat = (target.s + guess.s) / 2;

  const hueAccuracy = Math.max(0, 1 - Math.pow(hDiff / 25, 1.5));
  const recoverySatWeight = Math.min(1, avgSat / 30);
  const recovery = (10 - base) * hueAccuracy * recoverySatWeight * 0.25;

  // 3. Hue penalty — punish wrong hue on vivid colors
  const huePenFactor = Math.max(0, (hDiff - 25) / 100);
  const penaltySatWeight = Math.min(1, avgSat / 40);
  const penalty = base * huePenFactor * penaltySatWeight * 0.25;

  // Final score
  const score = base + recovery - penalty;
  return Math.max(0, Math.min(10, parseFloat(score.toFixed(2))));
}

export function scoreEmoji(score) {
  if (score >= 9.5) return '🟩'; 
  if (score >= 8.0) return '🟨';
  if (score >= 6.0) return '🟧';
  if (score >= 4.0) return '🟥';
  if (score >= 2.0) return '🟫';
  return '⬛';
}

