/**
 * colors.js — Deterministic daily color generation.
 *
 * Uses a seeded PRNG so every player gets the same 5 colors on a given day.
 * Colors avoid extremes (no near-white, near-black, or near-grey) for fair gameplay.
 */

/** Mulberry32 — fast, small, good-quality 32-bit PRNG */
function mulberry32(seed) {
  return function () {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Hash a string to a 32-bit integer */
function hashString(str) {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    hash = ((hash << 5) - hash + str.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/** Format today's date as YYYYMMDD integer */
function todayStr() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}${mm}${dd}`;
}

/**
 * Generate 5 daily HSB colors.
 * Deterministic: same date → same colors for everyone.
 *
 * @returns {{ colors: Array<{h: number, s: number, b: number}>, gameNumber: number }}
 */
export function getDailyColors(dateOverride = null) {
  const dateStr = dateOverride || todayStr();
  const seed = hashString('coloral-daily-' + dateStr);
  const rng = mulberry32(seed);

  let pdf = new Array(360).fill(1.0);

  function decreaseProb(centerHue, sigma) {
    for (let i = 0; i < 360; i++) {
        let dist = Math.min(Math.abs(i - centerHue), 360 - Math.abs(i - centerHue));
        let decline = Math.exp(- (dist * dist) / (2 * sigma * sigma));
        pdf[i] -= decline;
        if (pdf[i] < 0) pdf[i] = 0;
    }
  }

  // Penalize yesterday's hues to ensure completely different colors
  if (!dateOverride) {
    const d = new Date();
    d.setDate(d.getDate() - 1);
    const yyyy = d.getFullYear();
    const mm = String(d.getMonth() + 1).padStart(2, '0');
    const dd = String(d.getDate()).padStart(2, '0');
    const yesterdayStr = `${yyyy}${mm}${dd}`;
    
    const yesterdayColors = getDailyColors(yesterdayStr).colors;
    for (const c of yesterdayColors) {
      decreaseProb(c.h, 45); // Spread yesterday's penalty wide
    }
  }

  const colors = [];
  for (let i = 0; i < 5; i++) {
    let totalWeight = pdf.reduce((a, b) => a + b, 0);
    // Fallback if all probabilities are crushed
    if (totalWeight <= 0) { 
        pdf.fill(1.0);
        totalWeight = 360;
    }
    
    let r = rng() * totalWeight;
    let curr = 0;
    let pickedHue = 0;
    for (let j = 0; j < 360; j++) {
        curr += pdf[j];
        if (curr >= r) {
            pickedHue = j;
            break;
        }
    }

    colors.push({
      h: pickedHue,
      s: Math.floor(rng() * 55) + 25,     // 25–80%
      b: Math.floor(rng() * 55) + 25,     // 25–80%
    });
    
    // decrease probability of nearby color being chosen
    decreaseProb(pickedHue, 30);
  }

  return { colors, gameNumber: parseInt(dateStr, 10) };
}

/**
 * Format a date string like "Apr 13" from today's date.
 * @returns {string}
 */
export function todayLabel() {
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const d = new Date();
  return `${months[d.getMonth()]} ${d.getDate()}`;
}
