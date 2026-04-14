/**
 * app.js — Entry point. Handles auth, game initialization, and score submission.
 */

import { initAntiCheat } from './anticheat.js';
import { GameEngine } from './game.js';
import { initAudio } from './audio.js';
import { getDailyColors } from './colors.js';

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
      <p>Humans can't reliably recall colors. This is a simple game to see how good (or bad) you are at it.</p>
      <p>We'll show you five colors, then you'll try and recreate them.</p>
      <div class="player-name">Playing as ${username}</div>
      <button class="action-btn" id="start-btn" aria-label="Start game">
        <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M15.75 6.5C15.75 8.57107 14.0711 10.25 12 10.25C9.92893 10.25 8.25 8.57107 8.25 6.5C8.25 4.42893 9.92893 2.75 12 2.75C14.0711 2.75 15.75 4.42893 15.75 6.5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/><path d="M12 22C16.9706 22 21 17.9706 21 13C21 8.02944 16.9706 4 12 4C7.02944 4 3 8.02944 3 13C3 17.9706 7.02944 22 12 22Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
      </button>
    </div>
  `;

  const startBtn = document.getElementById('start-btn');
  startBtn.addEventListener('click', async () => {
    // Show brief loading state while audio fetches/decodes
    startBtn.style.opacity = '0.5';
    startBtn.style.pointerEvents = 'none';
    
    await initAudio(); // Must resolve before starting
    onStart();
  });
}

// ── Score Submission ─────────────────────────────────────────────────────────

async function submitScore(token, totalScore, roundScores, emojis, cheatEvents, isTest, roundData) {
  const statusEl = document.getElementById('results-status');

  // Dev mode: skip API submission
  if (DEV_MODE) {
    console.log('%c[DEV] Score submission skipped', 'color: #FFD166', { totalScore, roundScores, cheatEvents, isTest });
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
        isTest, // passes test flag to vercel
        roundData
      }),
    });

    if (res.ok) {
      if (statusEl) {
        statusEl.textContent = isTest ? '🧪 Test score sent!' : '✓ Score submitted to Discord!';
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
  const isTest = params.has('test') && params.get('test') === '1';

  // Check if this is a historical replay link
  let replayData = null;
  let finalScore = 0;
  if (params.has('replay') && params.has('score')) {
    try {
       // Decode base64url padding safely
       const b64 = params.get('replay').replace(/-/g, '+').replace(/_/g, '/');
       const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
       const raw = atob(padded);
       replayData = JSON.parse(raw);
       finalScore = parseFloat(params.get('score'));
    } catch (e) {
       console.error("Malformed replay data", e);
    }
  }

  // Get today's game number for localStorage key
  const { gameNumber } = getDailyColors();
  const todayKey = `coloral_played_${gameNumber}`;
  const savedResult = localStorage.getItem(todayKey);

  // If already played today (and not a replay link), show scorecard directly
  if (savedResult && !replayData && !DEV_MODE) {
    const saved = JSON.parse(savedResult);
    const engine = new GameEngine(container, { onComplete: () => {} });
    engine.showHistoricalScorecard(saved.totalScore, saved.roundData, gameNumber);
    // Show "already played" status after DOM renders
    setTimeout(() => {
      const statusEl = document.getElementById('results-status');
      if (statusEl) {
        statusEl.textContent = '🔒 You already played today!';
        statusEl.style.color = '#FFD166';
        statusEl.style.opacity = '1';
      }
    }, 100);
    return;
  }

  // Show intro screen
  showIntro(username, () => {
    const engine = new GameEngine(container, {
      onComplete: (totalScore, roundScores, emojis, cheatEvents, roundDataB64) => {
        // Save completion to localStorage so same-day revisits show scorecard
        try {
          const b64 = roundDataB64.replace(/-/g, '+').replace(/_/g, '/');
          const padded = b64 + '='.repeat((4 - (b64.length % 4)) % 4);
          const roundData = JSON.parse(atob(padded));
          localStorage.setItem(todayKey, JSON.stringify({
            totalScore: parseFloat(totalScore.toFixed(2)),
            roundData
          }));
        } catch (e) {
          console.warn('Could not save daily result to localStorage', e);
        }

        submitScore(token, totalScore, roundScores, emojis, cheatEvents, isTest, roundDataB64);
      },
    });

    if (replayData && replayData.length > 0) {
       engine.showHistoricalScorecard(finalScore, replayData, gameNumber);
    } else {
       engine.start();
    }
  });
}

main();
