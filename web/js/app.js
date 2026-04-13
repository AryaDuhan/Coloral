/**
 * app.js — Entry point. Handles auth, game initialization, and score submission.
 */

import { initAntiCheat } from './anticheat.js';
import { GameEngine } from './game.js';

const container = document.getElementById('phase-container');

// ── Dev Mode (localhost only) ────────────────────────────────────────────────
const IS_DEV = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const params = new URLSearchParams(window.location.search);
const DEV_MODE = IS_DEV && params.has('dev');

// ── Auth Flow ────────────────────────────────────────────────────────────────

async function authenticate() {
  // Dev bypass: skip API auth on localhost
  if (DEV_MODE) {
    console.log('%c[DEV] Auth bypassed — using test user', 'color: #6BCB77');
    return { user_id: '000000000000000000', username: 'TestPlayer', token: 'dev-token' };
  }

  const token = params.get('token');

  if (!token) {
    showAuthError('Open this link from Discord', "Click the <strong>Play Daily</strong> button in your Discord server to get a secure game link.");
    return null;
  }

  try {
    const res = await fetch(`/api/auth?token=${encodeURIComponent(token)}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      if (res.status === 401 && err.error === 'Token expired') {
        showAuthError('Link Expired', 'This game link has expired. Go back to Discord and click <strong>Play Daily</strong> again for a fresh link.');
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
      <h1>color</h1>
      <p>We'll show you five colors, then you'll try to recreate them from memory.</p>
      <p>Five rounds. 0–10 per round. Max 50.</p>
      <div class="player-name">Playing as ${username}</div>
      <button class="action-btn" id="start-btn" aria-label="Start game">▶</button>
    </div>
  `;

  document.getElementById('start-btn').addEventListener('click', onStart);
}

// ── Score Submission ─────────────────────────────────────────────────────────

async function submitScore(token, totalScore, roundScores, emojis, cheatEvents) {
  const statusEl = document.getElementById('results-status');

  // Dev mode: skip API submission
  if (DEV_MODE) {
    console.log('%c[DEV] Score submission skipped', 'color: #FFD166', { totalScore, roundScores, cheatEvents });
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
      }),
    });

    if (res.ok) {
      if (statusEl) {
        statusEl.textContent = '✓ Score submitted to Discord!';
        statusEl.className = 'results-status success';
      }
    } else {
      const err = await res.json().catch(() => ({}));
      if (statusEl) {
        statusEl.textContent = err.error === 'Score already recorded'
          ? '🔒 Score already recorded for today'
          : '⚠ Could not submit — copy your score manually';
        statusEl.className = 'results-status error';
      }
    }
  } catch (e) {
    if (statusEl) {
      statusEl.textContent = '⚠ Network error — copy your score manually';
      statusEl.className = 'results-status error';
    }
  }
}

// ── Boot ─────────────────────────────────────────────────────────────────────

async function main() {
  // Initialize anti-cheat listeners (passive, invisible)
  initAntiCheat();

  // Authenticate via token in URL
  const auth = await authenticate();
  if (!auth) return;

  const { user_id, username, token } = auth;

  // Show intro screen
  showIntro(username, () => {
    const engine = new GameEngine(container, {
      onComplete: (totalScore, roundScores, emojis, cheatEvents) => {
        submitScore(token, totalScore, roundScores, emojis, cheatEvents);
      },
    });
    engine.start();
  });
}

main();
