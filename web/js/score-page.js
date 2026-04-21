/**
 * score-page.js — Interactive scoring demo for the /score page.
 *
 * Imports the actual scoring pipeline from scoring.js and provides:
 *  - Live score computation as user drags sliders
 *  - Real-time Delta E, Hue Recovery, and Hue Penalty metrics
 *  - S-curve chart with animated tracking dot
 *  - Random target generation
 */

// ── Import Scoring Functions ──────────────────────────────────────────────────
// We inline the critical scoring functions to avoid module path issues.
// These mirror scoring.js exactly.

function hsbToRgb(h, s, b) {
  s /= 100;
  b /= 100;
  const k = (n) => (n + h / 60) % 6;
  const f = (n) => b * (1 - s * Math.max(0, Math.min(k(n), 4 - k(n), 1)));
  return [Math.round(f(5) * 255), Math.round(f(3) * 255), Math.round(f(1) * 255)];
}

function hsbToCss(h, s, b) {
  const [r, g, bl] = hsbToRgb(h, s, b);
  return `rgb(${r}, ${g}, ${bl})`;
}

function linearize(c) {
  return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

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

function xyzToLab(x, y, z) {
  const Xn = 95.047, Yn = 100.0, Zn = 108.883;
  const f = (t) => (t > 0.008856 ? Math.cbrt(t) : (903.3 * t + 16) / 116);
  const fx = f(x / Xn), fy = f(y / Yn), fz = f(z / Zn);
  return [116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)];
}

function hsbToLab(h, s, b) {
  return xyzToLab(...rgbToXyz(...hsbToRgb(h, s, b)));
}

const RAD = Math.PI / 180;
const DEG = 180 / Math.PI;

function ciede2000(lab1, lab2) {
  const [L1, a1, b1] = lab1;
  const [L2, a2, b2] = lab2;
  const C1 = Math.sqrt(a1 * a1 + b1 * b1);
  const C2 = Math.sqrt(a2 * a2 + b2 * b2);
  const Cmean = (C1 + C2) / 2;
  const Cmean7 = Math.pow(Cmean, 7);
  const G = 0.5 * (1 - Math.sqrt(Cmean7 / (Cmean7 + 6103515625)));
  const a1p = a1 * (1 + G);
  const a2p = a2 * (1 + G);
  const C1p = Math.sqrt(a1p * a1p + b1 * b1);
  const C2p = Math.sqrt(a2p * a2p + b2 * b2);
  let h1p = Math.atan2(b1, a1p) * DEG;
  if (h1p < 0) h1p += 360;
  let h2p = Math.atan2(b2, a2p) * DEG;
  if (h2p < 0) h2p += 360;
  const dLp = L2 - L1;
  const dCp = C2p - C1p;
  let dhp;
  if (C1p * C2p === 0) { dhp = 0; }
  else { dhp = h2p - h1p; if (dhp > 180) dhp -= 360; if (dhp < -180) dhp += 360; }
  const dHp = 2 * Math.sqrt(C1p * C2p) * Math.sin((dhp / 2) * RAD);
  const Lpmean = (L1 + L2) / 2;
  const Cpmean = (C1p + C2p) / 2;
  let hpmean;
  if (C1p * C2p === 0) { hpmean = h1p + h2p; }
  else if (Math.abs(h1p - h2p) <= 180) { hpmean = (h1p + h2p) / 2; }
  else { hpmean = (h1p + h2p + (h1p + h2p < 360 ? 360 : -360)) / 2; }
  const T = 1 - 0.17 * Math.cos((hpmean - 30) * RAD) + 0.24 * Math.cos(2 * hpmean * RAD) + 0.32 * Math.cos((3 * hpmean + 6) * RAD) - 0.20 * Math.cos((4 * hpmean - 63) * RAD);
  const Lpmean50sq = Math.pow(Lpmean - 50, 2);
  const SL = 1 + (0.015 * Lpmean50sq) / Math.sqrt(20 + Lpmean50sq);
  const SC = 1 + 0.045 * Cpmean;
  const SH = 1 + 0.015 * Cpmean * T;
  const theta = 30 * Math.exp(-Math.pow((hpmean - 275) / 25, 2));
  const Cpmean7 = Math.pow(Cpmean, 7);
  const RC = 2 * Math.sqrt(Cpmean7 / (Cpmean7 + 6103515625));
  const RT = -Math.sin(2 * theta * RAD) * RC;
  return Math.sqrt(
    Math.pow(dLp / SL, 2) + Math.pow(dCp / SC, 2) + Math.pow(dHp / SH, 2) + RT * (dCp / SC) * (dHp / SH)
  );
}

function deltaEToScore(dE) {
  return 10 / (1 + Math.pow(dE / 23.0, 1.7));
}

function hueDiff(h1, h2) {
  let d = Math.abs(h1 - h2);
  return d > 180 ? 360 - d : d;
}

/**
 * Full scoring breakdown returning all intermediate values.
 */
function scoreBreakdown(target, guess) {
  if (target.h === guess.h && target.s === guess.s && target.b === guess.b) {
    return { score: 10.00, dE: 0, base: 10, recovery: 0, penalty: 0 };
  }

  const targetLab = hsbToLab(target.h, target.s, target.b);
  const guessLab = hsbToLab(guess.h, guess.s, guess.b);
  const dE = ciede2000(targetLab, guessLab);
  const base = deltaEToScore(dE);

  const hDiff = hueDiff(target.h, guess.h);
  const avgSat = (target.s + guess.s) / 2;

  const hueAccuracy = Math.max(0, 1 - Math.pow(hDiff / 20, 1.5));
  const recoverySatWeight = Math.min(1, avgSat / 30);
  const recovery = (10 - base) * hueAccuracy * recoverySatWeight * 0.20;

  const huePenFactor = Math.max(0, (hDiff - 12) / 100);
  const penaltySatWeight = Math.min(1, avgSat / 30);
  const penalty = base * Math.min(1, huePenFactor) * penaltySatWeight * 0.28;

  const score = Math.max(0, Math.min(10, parseFloat((base + recovery - penalty).toFixed(2))));
  return { score, dE, base, recovery, penalty };
}

// ── State ─────────────────────────────────────────────────────────────────────

let target = { h: 210, s: 70, b: 80 };
let guess  = { h: 180, s: 50, b: 60 };

// ── DOM Elements ──────────────────────────────────────────────────────────────

const targetBox    = document.getElementById('demo-target-box');
const guessBox     = document.getElementById('demo-guess-box');
const scoreValue   = document.getElementById('demo-score-value');
const metricDeltaE = document.getElementById('metric-delta-e');
const metricRec    = document.getElementById('metric-recovery');
const metricPen    = document.getElementById('metric-penalty');
const sliderHue    = document.getElementById('slider-hue');
const sliderSat    = document.getElementById('slider-sat');
const sliderBri    = document.getElementById('slider-bri');
const valHue       = document.getElementById('val-hue');
const valSat       = document.getElementById('val-sat');
const valBri       = document.getElementById('val-bri');
const btnNewTarget = document.getElementById('btn-new-target');
const btnReset     = document.getElementById('btn-reset-guess');
const canvas       = document.getElementById('score-curve-canvas');

// ── S-Curve Chart ─────────────────────────────────────────────────────────────

function drawChart(currentDeltaE, currentScore) {
  const ctx = canvas.getContext('2d');
  const dpr = window.devicePixelRatio || 1;

  // Set canvas resolution
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);

  const W = rect.width;
  const H = rect.height;
  const padLeft = 40;
  const padRight = 20;
  const padTop = 16;
  const padBottom = 40;
  const chartW = W - padLeft - padRight;
  const chartH = H - padTop - padBottom;

  // Clear
  ctx.clearRect(0, 0, W, H);

  // Axis labels
  ctx.fillStyle = 'rgba(255,255,255,0.25)';
  ctx.font = '11px Inter, sans-serif';
  ctx.textAlign = 'right';
  ctx.textBaseline = 'middle';

  // Y-axis labels (score 0–10)
  for (let s = 0; s <= 10; s += 2) {
    const y = padTop + chartH - (s / 10) * chartH;
    ctx.fillText(s.toString(), padLeft - 8, y);

    // Grid line
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(padLeft + chartW, y);
    ctx.stroke();
  }

  // X-axis labels (ΔE 0–100)
  ctx.textAlign = 'center';
  ctx.textBaseline = 'top';
  for (let d = 0; d <= 100; d += 20) {
    const x = padLeft + (d / 100) * chartW;
    ctx.fillText(d.toString(), x, padTop + chartH + 12);

    // Vertical grid
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.beginPath();
    ctx.moveTo(x, padTop);
    ctx.lineTo(x, padTop + chartH);
    ctx.stroke();
  }

  // Draw S-curve
  ctx.beginPath();
  ctx.strokeStyle = '#f97316';
  ctx.lineWidth = 2.5;
  ctx.lineJoin = 'round';

  for (let i = 0; i <= chartW; i++) {
    const dE = (i / chartW) * 100;
    const sc = deltaEToScore(dE);
    const x = padLeft + i;
    const y = padTop + chartH - (sc / 10) * chartH;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  // Draw midpoint dashed line at ΔE = 23
  const midX = padLeft + (23 / 100) * chartW;
  ctx.strokeStyle = 'rgba(255,255,255,0.15)';
  ctx.lineWidth = 1;
  ctx.setLineDash([4, 4]);
  ctx.beginPath();
  ctx.moveTo(midX, padTop);
  ctx.lineTo(midX, padTop + chartH);
  ctx.stroke();
  ctx.setLineDash([]);

  // Tracking dot — current position
  if (currentDeltaE !== undefined) {
    const dotX = padLeft + Math.min(1, currentDeltaE / 100) * chartW;
    const dotY = padTop + chartH - (Math.max(0, Math.min(10, currentScore)) / 10) * chartH;

    // Glow
    ctx.beginPath();
    ctx.arc(dotX, dotY, 10, 0, Math.PI * 2);
    ctx.fillStyle = 'rgba(255, 255, 255, 0.12)';
    ctx.fill();

    // Dot
    ctx.beginPath();
    ctx.arc(dotX, dotY, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#ffffff';
    ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,0.3)';
    ctx.lineWidth = 1.5;
    ctx.stroke();
  }
}

// ── Color for score value ─────────────────────────────────────────────────────

function getScoreColor(score) {
  if (score >= 9.5) return '#34d399';
  if (score >= 8.0) return '#fbbf24';
  if (score >= 6.0) return '#fb923c';
  if (score >= 4.0) return '#ef4444';
  if (score >= 2.0) return '#a16207';
  return '#666';
}

// ── Update Everything ─────────────────────────────────────────────────────────

function update() {
  // Read slider values
  guess.h = parseInt(sliderHue.value);
  guess.s = parseInt(sliderSat.value);
  guess.b = parseInt(sliderBri.value);

  // Update slider value labels
  valHue.textContent = guess.h + '°';
  valSat.textContent = guess.s + '%';
  valBri.textContent = guess.b + '%';

  // Update color boxes
  targetBox.style.backgroundColor = hsbToCss(target.h, target.s, target.b);
  guessBox.style.backgroundColor = hsbToCss(guess.h, guess.s, guess.b);

  // Compute scoring breakdown
  const bd = scoreBreakdown(target, guess);

  // Update score display
  scoreValue.textContent = bd.score.toFixed(2);
  scoreValue.style.color = getScoreColor(bd.score);

  // Update metrics
  metricDeltaE.textContent = bd.dE.toFixed(1);
  metricRec.textContent = '+' + bd.recovery.toFixed(2);
  metricPen.textContent = '-' + bd.penalty.toFixed(2);

  // Update chart
  drawChart(bd.dE, bd.score);

  // Update saturation slider gradient (grey → saturated at current hue)
  sliderSat.style.background = `linear-gradient(to right, ${hsbToCss(guess.h, 0, guess.b)}, ${hsbToCss(guess.h, 100, guess.b)})`;

  // Update brightness slider gradient (black → bright at current hue+sat)
  sliderBri.style.background = `linear-gradient(to right, #000, ${hsbToCss(guess.h, guess.s, 100)})`;
}

// ── Random Target ─────────────────────────────────────────────────────────────

function newTarget() {
  target.h = Math.floor(Math.random() * 361);
  target.s = 30 + Math.floor(Math.random() * 71); // 30-100 for visible colors
  target.b = 30 + Math.floor(Math.random() * 71);
  update();
}

function resetGuess() {
  sliderHue.value = 180;
  sliderSat.value = 50;
  sliderBri.value = 60;
  update();
}

// ── Event Listeners ───────────────────────────────────────────────────────────

sliderHue.addEventListener('input', update);
sliderSat.addEventListener('input', update);
sliderBri.addEventListener('input', update);
btnNewTarget.addEventListener('click', newTarget);
btnReset.addEventListener('click', resetGuess);

// Handle resize for chart
window.addEventListener('resize', update);

// ── Initialize ────────────────────────────────────────────────────────────────
update();
