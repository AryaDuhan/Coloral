/**
 * game.js — 5-round color memory game engine + DOM rendering.
 *
 * Game flow per round: MEMORIZE (7s) → RECREATE (user adjusts sliders) → REVEAL (score + comparison)
 * After 5 rounds: RESULTS (total score, emoji bar, auto-submit)
 */

import { scoreRound, scoreEmoji, hsbToCss, getTextColor } from './scoring.js';
import { getDailyColors, todayLabel } from './colors.js';
import { createSliders } from './sliders.js';
import { startMonitoring, stopMonitoring, getEvents } from './anticheat.js';

const ROUNDS = 5;
const MEMORIZE_SECONDS = 7;

const QUIPS_GREAT = [
  "Dialed.",
  "Your eyes are calibrated.",
  "Color scientist material.",
  "Flawless recall.",
];
const QUIPS_GOOD = [
  "Solid memory.",
  "Close enough to impress.",
  "You see color well.",
];
const QUIPS_MEH = [
  "Room for improvement.",
  "Your monitor might need calibrating.",
  "Approximately colorful.",
];
const QUIPS_BAD = [
  "Were you looking?",
  "Creative interpretation.",
  "That's... a color, technically.",
  "Bold choice.",
];

function pickQuip(score) {
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];
  if (score >= 8.5) return pick(QUIPS_GREAT);
  if (score >= 6) return pick(QUIPS_GOOD);
  if (score >= 3.5) return pick(QUIPS_MEH);
  return pick(QUIPS_BAD);
}

/**
 * @typedef {Object} GameCallbacks
 * @property {function(number, Array<number>, string, object[]): void} onComplete
 *   Called with (totalScore, roundScores, emojiBar, cheatEvents) when game finishes
 */

export class GameEngine {
  /**
   * @param {HTMLElement} container  The #phase-container element
   * @param {GameCallbacks} callbacks
   */
  constructor(container, callbacks) {
    this.container = container;
    this.callbacks = callbacks;
    this.round = 0;
    this.scores = [];
    this.guesses = [];
    this.dailyColors = [];
    this.gameNumber = 0;
    this._sliderInstance = null;
    this._timer = null;
  }

  /** Start a new daily game. */
  start() {
    const daily = getDailyColors();
    this.dailyColors = daily.colors;
    this.gameNumber = daily.gameNumber;
    this.round = 0;
    this.scores = [];
    this.guesses = [];
    this._nextRound();
  }

  destroy() {
    if (this._sliderInstance) {
      this._sliderInstance.destroy();
      this._sliderInstance = null;
    }
    if (this._timer) {
      clearInterval(this._timer);
      this._timer = null;
    }
  }

  // ── Round Flow ─────────────────────────────────────────────────────────────

  _nextRound() {
    if (this.round >= ROUNDS) {
      this._showResults();
      return;
    }
    this._startMemorize();
  }

  _startMemorize() {
    const target = this.dailyColors[this.round];
    const textColor = getTextColor(target.h, target.s, target.b);
    let remaining = MEMORIZE_SECONDS;

    // Start anti-cheat monitoring
    startMonitoring(this.round + 1);

    this.container.innerHTML = `
      <div class="memorize" style="background: ${hsbToCss(target.h, target.s, target.b)}">
        <span class="overlay-label round-label" style="color: ${textColor}">${this.round + 1} / ${ROUNDS}</span>
        <span class="overlay-label brand-label" style="color: ${textColor}">Coloral</span>
        <span class="countdown" id="countdown" style="color: ${textColor}">${remaining}</span>
      </div>
    `;

    const countdownEl = document.getElementById('countdown');

    this._timer = setInterval(() => {
      remaining--;
      if (remaining <= 0) {
        clearInterval(this._timer);
        this._timer = null;
        stopMonitoring();
        this._startRecreate();
      } else {
        countdownEl.textContent = remaining;
      }
    }, 1000);
  }

  _startRecreate() {
    const target = this.dailyColors[this.round];

    this.container.innerHTML = `
      <div class="recreate">
        <div class="sliders-panel" id="sliders-panel"></div>
        <div class="color-preview" id="color-preview">
          <span class="overlay-label round-label" id="recreate-round" style="color: rgba(0,0,0,0.5)">${this.round + 1} / ${ROUNDS}</span>
          <span class="preview-hsb" id="preview-hsb"></span>
          <button class="submit-btn" id="submit-btn" aria-label="Submit guess">→</button>
        </div>
      </div>
    `;

    const preview = document.getElementById('color-preview');
    const hsbLabel = document.getElementById('preview-hsb');
    const submitBtn = document.getElementById('submit-btn');
    const slidersPanel = document.getElementById('sliders-panel');
    const roundLabel = document.getElementById('recreate-round');

    // Update preview color + text readability
    const updatePreview = (h, s, b) => {
      const css = hsbToCss(h, s, b);
      const textCol = getTextColor(h, s, b);
      preview.style.backgroundColor = css;
      hsbLabel.textContent = `H${h} S${s} B${b}`;
      hsbLabel.style.color = textCol;
      roundLabel.style.color = textCol;
      submitBtn.style.borderColor = textCol.replace('0.7', '0.2');
    };

    this._sliderInstance = createSliders(slidersPanel, updatePreview);

    // Initial preview
    const init = this._sliderInstance.getValues();
    updatePreview(init.h, init.s, init.b);

    submitBtn.addEventListener('click', () => {
      const guess = this._sliderInstance.getValues();
      this._sliderInstance.destroy();
      this._sliderInstance = null;
      this.guesses.push({ ...guess });
      const score = scoreRound(target, guess);
      this.scores.push(score);
      this._showReveal(target, guess, score);
    });
  }

  _showReveal(target, guess, score) {
    const guessColor = hsbToCss(guess.h, guess.s, guess.b);
    const targetColor = hsbToCss(target.h, target.s, target.b);
    const guessText = getTextColor(guess.h, guess.s, guess.b);
    const targetText = getTextColor(target.h, target.s, target.b);
    const quip = pickQuip(score);
    const isLast = this.round + 1 >= ROUNDS;

    this.container.innerHTML = `
      <div class="reveal">
        <div class="reveal-top" style="background: ${guessColor}">
          <span class="overlay-label round-label" style="color: ${guessText}">${this.round + 1} / ${ROUNDS}</span>
          <span class="reveal-score" style="color: ${guessText}">${score.toFixed(2)}</span>
          <span class="reveal-quip" style="color: ${guessText}">${quip}</span>
          <div class="reveal-info" style="color: ${guessText}">
            <div class="reveal-info-label">Your selection</div>
            <div class="reveal-info-value">H${guess.h} S${guess.s} B${guess.b}</div>
          </div>
        </div>
        <div class="reveal-bottom" style="background: ${targetColor}">
          <div class="reveal-info" style="color: ${targetText}">
            <div class="reveal-info-label">Original</div>
            <div class="reveal-info-value">H${target.h} S${target.s} B${target.b}</div>
          </div>
          <button class="next-btn" id="next-btn" aria-label="${isLast ? 'See results' : 'Next round'}">→</button>
        </div>
      </div>
    `;

    document.getElementById('next-btn').addEventListener('click', () => {
      this.round++;
      this._nextRound();
    });
  }

  _showResults() {
    const total = this.scores.reduce((a, b) => a + b, 0);
    const totalStr = total.toFixed(2);
    const emojis = this.scores.map(scoreEmoji).join('');

    const breakdownHtml = this.scores
      .map((s, i) => `<span class="round-score-chip">${s.toFixed(1)}</span>`)
      .join('');

    this.container.innerHTML = `
      <div class="results">
        <div class="results-total">${totalStr}</div>
        <div class="results-max">/ 50</div>
        <div class="results-emojis">${emojis}</div>
        <div class="results-breakdown">${breakdownHtml}</div>
        <div class="results-status submitting" id="results-status">Submitting score…</div>
        <button class="share-btn" id="share-btn">📋 Copy Score</button>
      </div>
    `;

    // Share button: copy score text to clipboard
    document.getElementById('share-btn').addEventListener('click', () => {
      const shareText = `Dialed Daily — ${todayLabel()}\n${totalStr}/50 ${emojis}`;
      navigator.clipboard.writeText(shareText).then(() => {
        document.getElementById('share-btn').textContent = '✓ Copied!';
        setTimeout(() => {
          document.getElementById('share-btn').textContent = '📋 Copy Score';
        }, 2000);
      });
    });

    // Fire completion callback
    const cheatEvents = getEvents();
    this.callbacks.onComplete(total, this.scores, emojis, cheatEvents);
  }
}
