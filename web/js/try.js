/**
 * try.js — Public tryout entry point.
 *
 * Same game engine, random colors each play, NO authentication, NO score submission.
 * Anyone can visit /singleplayer and play instantly.
 */

import { GameEngine } from './game.js';
import { initAudio } from './audio.js';
import { getRandomColors } from './colors.js';

const container = document.getElementById('phase-container');

// ── Intro Screen ─────────────────────────────────────────────────────────────

function showIntro(onStart) {
  container.innerHTML = `
    <div class="intro">
      <h1>try<br>colorle</h1>
      <p>How well can you remember colors? Five rounds — memorize a color, then recreate it from memory.</p>
      <p style="color: rgba(255,255,255,0.45); font-size: 13px; margin-bottom: 0;">No account needed. Play as many times as you want.</p>
      <button class="action-btn" id="start-btn" aria-label="Start game">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M8 5.14v14l11-7-11-7z" fill="currentColor"/></svg>
      </button>
    </div>
  `;

  document.getElementById('start-btn').addEventListener('click', async () => {
    const btn = document.getElementById('start-btn');
    btn.style.opacity = '0.5';
    btn.style.pointerEvents = 'none';
    await initAudio();
    onStart();
  });
}

// ── Boot ─────────────────────────────────────────────────────────────────────

function main() {
  function startGame() {
    const randomColors = getRandomColors();

    const engine = new GameEngine(container, {
      onComplete: (_totalScore, _roundScores, _emojis, _cheatEvents, _roundDataB64) => {
        // No score submission — just show the scorecard

        // After scorecard renders, customize the buttons
        setTimeout(() => {
          // Hide the submission status line
          const statusEl = document.getElementById('results-status');
          if (statusEl) {
            statusEl.innerHTML = `
              <span style="color: #aaa;">✨ Want to compete with friends?</span><br>
              <a href="https://github.com/AryaDuhan/Coloral" target="_blank" rel="noopener"
                 style="color: #6BCB77; text-decoration: underline; text-underline-offset: 3px; font-size: 13px;">
                Host Coloral on your Discord server →
              </a>
            `;
            statusEl.className = 'results-status';
            statusEl.style.opacity = '1';
          }

          // Replace the leaderboard button with Play Again
          const lbBtn = document.getElementById('leaderboard-btn');
          if (lbBtn) {
            lbBtn.textContent = '🎲 Play Again';
            lbBtn.id = 'play-again-btn';
            lbBtn.addEventListener('click', () => {
              startGame();
            });
          }
        }, 100);
      },
    });

    engine.start(randomColors);
  }

  showIntro(startGame);
}

main();
