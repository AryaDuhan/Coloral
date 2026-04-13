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
export function getDailyColors() {
  const dateStr = todayStr();
  const seed = hashString('coloral-daily-' + dateStr);
  const rng = mulberry32(seed);

  const colors = [];
  for (let i = 0; i < 5; i++) {
    colors.push({
      h: Math.floor(rng() * 360),         // full hue range
      s: Math.floor(rng() * 55) + 25,     // 25–80%  (avoids near-grey)
      b: Math.floor(rng() * 55) + 25,     // 25–80%  (avoids near-black/white)
    });
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
