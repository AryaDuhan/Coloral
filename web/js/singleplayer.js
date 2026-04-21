/**
 * singleplayer.js — Entry point for single player mode.
 *
 * Same game engine, random colors each play, no daily limit.
 * Scores are submitted to Discord webhook with SP flag.
 */

import { initAntiCheat } from './anticheat.js';
import { GameEngine } from './game.js';
import { initAudio } from './audio.js';
import { getRandomColors } from './colors.js';

const container = document.getElementById('phase-container');

// ── Dev Mode (localhost only) ────────────────────────────────────────────────
const IS_DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const params = new URLSearchParams(window.location.search);
const DEV_MODE = IS_DEV && params.has('dev');

// ── Auth Flow ────────────────────────────────────────────────────────────────

async function authenticate() {
  if (DEV_MODE) {
    console.log('%c[DEV] Auth bypassed — using test user', 'color: #6BCB77');
    return { user_id: '000000000000000000', username: 'TestPlayer', token: 'dev-token' };
  }

  const token = params.get('token');

  if (!token) {
    showAuthError('Open this link from Discord', "Click the <strong>Play Single Player</strong> button in your Discord server to get a secure game link.");
    return null;
  }

  try {
    const res = await fetch(`/api/auth?token=${encodeURIComponent(token)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 401 && err.error === 'Token expired') {
        showAuthError('Link Expired', 'This game link has expired. Go back to Discord and click <strong>Play Single Player</strong> again for a fresh link.');
      } else {
        showAuthError('Invalid Link', 'This game link is invalid. Make sure you clicked the link from Discord.');
      }
      return null;
    }
    return { ...(await res.json()), token };
  } catch (e) {
    showAuthError('Connection Error', 'Could not connect to the server. Please try again.');
    return null;
  }
}

function showAuthError(title, message) {
  container.innerHTML = `
    <div class="auth-error">
      <h2>${title}</h2>
      <p>${message}</p>
    </div>
  `;
}

// ── Intro Screen ─────────────────────────────────────────────────────────────

function showIntro(username, onStart) {
  container.innerHTML = `
    <div class="intro">
      <h1>single<br>player</h1>
      <p>Unlimited practice. Random colors every game. No daily limits — play as many times as you want.</p>
      <div class="player-name">Playing as ${username}</div>
      <button class="action-btn" id="start-btn" aria-label="Start game">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M15.75 6.5C15.75 8.57107 14.0711 10.25 12 10.25C9.92893 10.25 8.25 8.57107 8.25 6.5C8.25 4.42893 9.92893 2.75 12 2.75C14.0711 2.75 15.75 4.42893 15.75 6.5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 22C16.9706 22 21 17.9706 21 13C21 8.02944 16.9706 4 12 4C7.02944 4 3 8.02944 3 13C3 17.9706 7.02944 22 12 22Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
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

// ── Score Submission (Single Player) ─────────────────────────────────────────

async function submitSPScore(token, totalScore, roundScores, emojis, cheatEvents, roundData) {
  const statusEl = document.getElementById('results-status');

  if (DEV_MODE) {
    console.log('%c[DEV] SP Score submission skipped', 'color: #FFD166', { totalScore, roundScores });
    if (statusEl) {
      statusEl.textContent = '✓ Score logged to console (dev mode)';
      statusEl.className = 'results-status success';
    }
    return;
  }

  try {
    const res = await fetch('/api/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        token,
        scores: roundScores,
        totalScore: parseFloat(totalScore.toFixed(2)),
        cheatEvents,
        isTest: false,
        roundData,
        mode: 'sp',  // ← Single player flag
      }),
    });

    const data = await res.json().catch(() => ({}));

    if (res.ok && data.success) {
      if (statusEl) {
        statusEl.textContent = '✓ Score recorded!';
        statusEl.className = 'results-status success';
      }
    } else {
      if (statusEl) {
        statusEl.textContent = '⚠ Could not submit score';
        statusEl.className = 'results-status error';
      }
    }
  } catch (e) {
    if (statusEl) {
      statusEl.textContent = '⚠ Network error';
      statusEl.className = 'results-status error';
    }
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────

async function main() {
  initAntiCheat();

  const auth = await authenticate();
  if (!auth) return;

  const { user_id, username, token } = auth;

  function startGame() {
    const randomColors = getRandomColors();

    const engine = new GameEngine(container, {
      onComplete: (totalScore, roundScores, emojis, cheatEvents, roundDataB64) => {
        submitSPScore(token, totalScore, roundScores, emojis, cheatEvents, roundDataB64);

        // After scorecard renders, add "Play Again" button
        setTimeout(() => {
          const statusEl = document.getElementById('results-status');
          if (statusEl && !statusEl.textContent) {
            statusEl.textContent = '✓ Score recorded!';
            statusEl.className = 'results-status success';
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

  showIntro(username, startGame);
}

main();
