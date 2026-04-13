import { scoreRound, scoreEmoji, hsbToCss, getTextColor } from './scoring.js';
import { getDailyColors, todayLabel } from './colors.js';
import { createSliders } from './sliders.js';
import { startMonitoring, stopMonitoring, getEvents } from './anticheat.js';
import { startTimerTick, stopTimerTick, startScoreTick, updateScoreTickRate, stopScoreTick, playDing, playCountdownAudio, playTimerEnd, stopCountdownAudio } from './audio.js';

const ROUNDS = 5;
const MEMORIZE_SECONDS = 5;
const COUNTDOWN_STEPS = [3, 2, 1];
const COUNTDOWN_STEP_MS = 1000;

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
    this._rafId = null;
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
    if (this._rafId) {
      cancelAnimationFrame(this._rafId);
      this._rafId = null;
    }
    if (this._countdownTimer) {
      clearTimeout(this._countdownTimer);
      this._countdownTimer = null;
    }
    stopTimerTick();
    stopScoreTick();
    stopCountdownAudio();
  }

  // ── Round Flow ─────────────────────────────────────────────────────────────

  _nextRound() {
    if (this.round >= ROUNDS) {
      this._showResults();
      return;
    }
    this._startCountdown();
  }

  /** 3-2-1 countdown with zoom-in/out animation before memorize */
  _startCountdown() {
    this.container.innerHTML = `
      <div class="countdown-phase" style="background: #000">
        <span class="overlay-label round-label" style="color: #fff">${this.round + 1} / ${ROUNDS}</span>
        <div class="countdown-number" id="countdown-num" style="color: #fff">3</div>
      </div>
    `;

    // Play the countdown audio file
    playCountdownAudio();

    const numEl = document.getElementById('countdown-num');
    let stepIdx = 0;

    const showStep = () => {
      if (stepIdx >= COUNTDOWN_STEPS.length) {
        // Countdown finished → start memorize
        this._startMemorize();
        return;
      }

      numEl.textContent = COUNTDOWN_STEPS[stepIdx];
      // Trigger zoom animation: remove class, force reflow, add class
      numEl.classList.remove('countdown-zoom');
      void numEl.offsetWidth;
      numEl.classList.add('countdown-zoom');

      stepIdx++;
      this._countdownTimer = setTimeout(showStep, COUNTDOWN_STEP_MS);
    };

    showStep();
  }

  _startMemorize() {
    const target = this.dailyColors[this.round];
    const textColor = getTextColor(target.h, target.s, target.b);

    // Start anti-cheat monitoring
    startMonitoring(this.round + 1);

    this.container.innerHTML = `
      <div class="memorize" style="background: ${hsbToCss(target.h, target.s, target.b)}">
        <span class="overlay-label round-label" style="color: ${textColor}">${this.round + 1} / ${ROUNDS}</span>
        <span class="overlay-label brand-label" style="color: ${textColor}">Coloral</span>
        <span class="countdown" id="countdown" style="color: ${textColor}"><span class="timer-int" id="timer-int">${MEMORIZE_SECONDS}</span><span class="timer-dec" id="timer-dec">00</span></span>
      </div>
    `;

    const timerIntEl = document.getElementById('timer-int');
    const timerDecEl = document.getElementById('timer-dec');
    const startTime = performance.now();
    let lastTickValue = MEMORIZE_SECONDS;
    let lastIntVal = MEMORIZE_SECONDS;

    // Start mechanical timer sound loop
    startTimerTick();

    const loop = (time) => {
      const elapsed = (time - startTime) / 1000;
      let remaining = MEMORIZE_SECONDS - elapsed;

      if (remaining <= 0) {
        remaining = 0;
        timerIntEl.textContent = '0';
        timerDecEl.textContent = '00';
        stopTimerTick(); // STOP the repeating mechanical watch clip
        playTimerEnd(); // beep when timer ends
        stopMonitoring();
        this._startRecreate();
        return;
      }

      const intPart = Math.floor(remaining);
      const decPart = Math.floor((remaining % 1) * 100);
      
      // Animate integer changes
      if (intPart !== lastIntVal) {
        timerIntEl.classList.remove('num-in-fast');
        void timerIntEl.offsetWidth;
        timerIntEl.classList.add('num-in-fast');
        lastIntVal = intPart;
      }
      timerIntEl.textContent = intPart;
      timerDecEl.textContent = String(decPart).padStart(2, '0');

      this._rafId = requestAnimationFrame(loop);
    };

    this._rafId = requestAnimationFrame(loop);
  }

  _startRecreate() {
    const target = this.dailyColors[this.round];

    this.container.innerHTML = `
      <div class="recreate">
        <div class="sliders-panel" id="sliders-panel"></div>
        <div class="color-preview" id="color-preview">
          <span class="overlay-label round-label" id="recreate-round" style="color: rgba(0,0,0,0.5)">${this.round + 1} / ${ROUNDS}</span>
          <span class="preview-hsb" id="preview-hsb"></span>
          <button class="submit-btn" id="submit-btn" aria-label="Submit guess"><svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18.75 5.25037L18.0332 5.47093C18.1062 5.70832 18.292 5.89416 18.5294 5.9672L18.75 5.25037ZM11.4697 11.47C11.1768 11.7629 11.1768 12.2378 11.4697 12.5307C11.7626 12.8236 12.2374 12.8236 12.5303 12.5307L11.4697 11.47ZM12.013 16.5003C9.52054 16.5003 7.5 14.4797 7.5 11.9873H6C6 15.3082 8.69211 18.0003 12.013 18.0003V16.5003ZM7.5 11.9873C7.5 9.79277 9.06706 7.96265 11.1435 7.55779L10.8565 6.08552C8.08896 6.62511 6 9.06141 6 11.9873H7.5ZM16.4425 12.8568C16.0376 14.9333 14.2075 16.5003 12.013 16.5003V18.0003C14.9388 18.0003 17.3751 15.9114 17.9147 13.1439L16.4425 12.8568ZM20.5 12.0004C20.5 16.6948 16.6944 20.5004 12 20.5004V22.0004C17.5228 22.0004 22 17.5232 22 12.0004H20.5ZM12 20.5004C7.30558 20.5004 3.5 16.6948 3.5 12.0004H2C2 17.5232 6.47715 22.0004 12 22.0004V20.5004ZM3.5 12.0004C3.5 7.30595 7.30558 3.50037 12 3.50037V2.00037C6.47715 2.00037 2 6.47752 2 12.0004H3.5Z" fill="currentColor"/></svg></button>
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
      // Intentionally not displaying H S B text during guessing
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
          <span class="reveal-score" id="reveal-score-display" style="color: ${guessText}">
            <span class="score-int" id="reveal-int">0</span><span class="score-dot">.</span><span class="score-dec" id="reveal-dec">00</span>
          </span>
          <span class="reveal-quip" style="color: ${guessText}; opacity: 0;" id="reveal-quip-display">${quip}</span>
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
          <button class="next-btn" id="next-btn" aria-label="${isLast ? 'See results' : 'Next round'}" style="display: none;"><svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M14 5.75L20.25 12L14 18.25" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M19.5 12H3.75" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
        </div>
      </div>
    `;

    const intEl = document.getElementById('reveal-int');
    const decEl = document.getElementById('reveal-dec');
    const quipDisplay = document.getElementById('reveal-quip-display');
    const nextBtn = document.getElementById('next-btn');

    // Score tally animation
    const duration = 1200; // longer animation to let the ease out shine
    const startTime = performance.now();
    let lastInt = -1;

    // Start the looping score tick sound
    startScoreTick();

    const tallyLoop = (time) => {
      const now = time || performance.now();
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);
      
      // Quintic ease-out: insanely fast start, dramatic crawl at the end
      const easeOutQuint = 1 - Math.pow(1 - progress, 5);
      const currentVal = score * easeOutQuint;
      
      const newInt = Math.floor(currentVal);
      const currentHundredths = Math.floor((currentVal % 1) * 100);
      const newDec = Math.max(0, currentHundredths);
      const slow = progress > 0.7; // "Slide animations only fire when slow enough to see (last ~30% of the duration)"
      const totalHundredths = score * 100;

      // Update integer
      const isIntChange = newInt !== lastInt;
      if (isIntChange) {
        if (slow) {
          intEl.classList.remove('num-in-fast');
          void intEl.offsetWidth;
          intEl.classList.add('num-in-fast');
        }
        intEl.textContent = newInt;
        lastInt = newInt;
      }

      // Update decimal — always visible, zero-padded to 2 digits
      if (slow) {
        decEl.classList.remove('num-in-fast');
        void decEl.offsetWidth;
        decEl.classList.add('num-in-fast');
      }
      decEl.textContent = String(newDec).padStart(2, '0');

      // Disable the manual discrete ticks, let the loop handle it
      // but update the playback rate according to progress
      updateScoreTickRate(progress);

      if (progress < 1) {
        this._rafId = requestAnimationFrame(tallyLoop);
      } else {
        // Finalize state
        stopScoreTick();
        const finalInt = Math.floor(score);
        const finalDec = Math.floor((score % 1) * 100);
        intEl.textContent = finalInt;
        decEl.textContent = String(finalDec).padStart(2, '0');
        playDing(score);
        quipDisplay.style.opacity = '1';
        quipDisplay.style.transition = 'opacity 0.4s';
        nextBtn.style.display = 'flex';
      }
    };

    this._rafId = requestAnimationFrame(tallyLoop);

    nextBtn.addEventListener('click', () => {
      this.round++;
      this._nextRound();
    });
  }

  _showResults() {
    const total = this.scores.reduce((a, b) => a + b, 0);
    const emojis = this.scores.map(scoreEmoji).join('');
    const cheatEvents = getEvents();

    const roundDataObj = this.rounds.map((r, i) => ({
      t: [r.target.h, r.target.s, r.target.b],
      g: [this.guesses[i].h, this.guesses[i].s, this.guesses[i].b],
      s: this.scores[i]
    }));
    
    // Convert to base64url so it safely passes through discord webhook
    const roundDataB64 = btoa(JSON.stringify(roundDataObj))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=/g, '');

    // Fire network completion callback first
    this.callbacks.onComplete(total, this.scores, emojis, cheatEvents, roundDataB64);

    this._renderScorecard(total, roundDataObj);
  }

  showHistoricalScorecard(finalScore, replayData, isTest) {
    this.container.innerHTML = '';
    this._renderScorecard(finalScore, replayData, true);
  }

  _renderScorecard(totalScore, roundDataObj, isReplay = false) {
    const totalStr = totalScore.toFixed(2);
    const scoreNums = roundDataObj.map(r => r.s);
    const emojis = scoreNums.map(scoreEmoji).join('');
    
    // Pick quip roughly based on average 50 max score
    const quip = totalScore >= 45 ? "Okay, this is actually good. We hate admitting that." : 
                 totalScore >= 40 ? "Pretty solid memory today." : 
                 totalScore >= 30 ? "Passable, but we expect better." : 
                 "Yikes. Let's pretend this didn't happen.";

    // Determine the short date for the card "Apr 13"
    const dateObj = new Date();
    const shortDateLabel = dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const fullDateLabel = dateObj.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });

    // Generate 5 grid boxes
    const gridHtml = roundDataObj.map(r => {
      const targetCss = hsbToCss(r.t[0], r.t[1], r.t[2]);
      const guessCss = hsbToCss(r.g[0], r.g[1], r.g[2]);
      return `
        <div class="result-color-box">
           <div class="result-half result-guess" style="background:${guessCss};"></div>
           <div class="result-half result-target" style="background:${targetCss}; clip-path: polygon(100% 0, 100% 100%, 0 100%);"></div>
           <div class="result-label">${r.s.toFixed(2)}</div>
        </div>
      `;
    }).join('');

    this.container.innerHTML = `
      <div class="results" style="padding-top: 40px; justify-content: flex-start; gap: 20px;">
        <div class="results-header" style="display: flex; justify-content: space-between; width: 100%; align-items: center; margin-bottom: -10px;">
          <div class="results-title" style="font-size: 14px; color: #fff;">
            <strong style="color: #fff">Daily</strong> <span style="color: #aaa">${fullDateLabel}</span>
          </div>
          <button class="results-close" aria-label="Close" style="background: rgba(255,255,255,0.1); border: none; width: 32px; height: 32px; border-radius: 50%; color: #fff; font-size: 18px; cursor: pointer; display: flex; align-items: center; justify-content: center;">×</button>
        </div>
        
        <div class="results-score-group" style="width: 100%; text-align: left;">
          <span style="font-size: 80px; font-weight: 600; font-family: var(--font), sans-serif; letter-spacing: -3px; color: #fff; line-height: 1;">${totalStr}</span><span style="font-size: 80px; font-weight: 500; font-family: var(--font), sans-serif; letter-spacing: -3px; color: #888; line-height: 1;">/50</span>
        </div>

        <div class="results-quip" style="width: 100%; text-align: left; font-size: 15px; color: #ccc; margin-bottom: 8px;">${quip}</div>

        <div class="result-colors">
           ${gridHtml}
        </div>

        <div class="results-rank" id="results-status" style="width: 100%; text-align: left; font-weight: 600; color: #6BCB77; opacity: ${isReplay ? 0 : 1}; margin-bottom: 10px;">Submitting score...</div>

        <div class="results-card">
          <div class="card-line1" style="font-weight: 600; font-size: 15px; color: #fff; margin-bottom: 4px;">Dialed Daily — ${shortDateLabel}</div>
          <div class="card-line2" style="font-size: 14px; color: #aaa; margin-bottom: 6px;">${totalStr}/50 <span style="letter-spacing: -2px; margin-left: 4px;">${emojis}</span></div>
          <div class="card-line3" style="font-size: 13px; color: #666;">dialed.gg?d=1&s=${totalStr}</div>
        </div>

        <button class="share-btn" id="share-btn" style="background: #fff; color: #000; width: 100%; padding: 16px; border-radius: 20px; font-size: 16px; font-weight: 600; cursor: pointer; margin-top: 10px; border: none;">Share your score</button>
        <div class="leaderboard-link" style="font-size: 13px; color: #666; font-weight: 500; cursor: pointer;">Daily Leaderboard</div>
      </div>
    `;

    document.getElementById('share-btn').addEventListener('click', () => {
      const shareText = \`Dialed Daily — ${shortDateLabel}\\n${totalStr}/50 ${emojis}\\ndialed.gg?d=1&s=${totalStr}\`;
      const btn = document.getElementById('share-btn');
      navigator.clipboard.writeText(shareText).then(() => {
        btn.textContent = 'Copied!';
        btn.classList.add('copied');
        setTimeout(() => {
          btn.textContent = 'Share your score';
          btn.classList.remove('copied');
        }, 2000);
      });
    });
    
    document.querySelector('.results-close').addEventListener('click', () => {
       window.location.reload();
    });
  }
}
// EOF
