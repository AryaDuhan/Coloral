/**
 * anticheat.js — Silent detection & penalty system.
 *
 * Monitors for suspicious browser events during gameplay.
 * Events are collected silently — the player NEVER sees any indication.
 *
 * Penalty tiers:
 *   1-2 events  → severity-based cap (mild 0.1, severe 0.2 per event)
 *   3+ events   → flat 0.5/round cap (max 9.5)
 *   Reputation   → returning cheaters get subtler persistent caps
 *   Streak 3+   → guess corruption on last round(s)
 *
 * Robustness rules (to avoid false positives):
 *   - window_blur during 'guess' phase is IGNORED (user may click sliders near edge)
 *   - window_blur events are debounced (rapid blur/focus cycles from notifications)
 *   - A blur must be SUSTAINED (>2s) during memorize to count
 *   - Single right-clicks are ignored (only repeated ones flag)
 *   - tab_hidden during guess phase is ignored
 */

let _monitoring = false;
let _currentRound = 0;
let _currentPhase = 'memorize';
const _events = [];

// ── Blur tracking state ────────────────────────────────────────────────────
let _blurStart = 0;          // timestamp when blur started (0 = not blurred)
let _blurDebounce = 0;       // timestamp of last recorded blur (for debouncing)
const _BLUR_MIN_DURATION = 2000;   // blur must last 2s+ to count during memorize
const _BLUR_DEBOUNCE_MS = 3000;    // ignore rapid blur/focus cycles within 3s

// ── Right-click tracking ───────────────────────────────────────────────────
let _rightClickCount = 0;         // clicks per monitoring session
const _RIGHTCLICK_THRESHOLD = 2;  // must right-click 2+ times to flag

// ── Severity tiers (for 1-2 event penalty only) ────────────────────────────
const _SEVERITY = {
  window_blur:      0.1,
  tab_hidden:       0.1,
  right_click:      0.1,
  print_screen:     0.2,
  ctrl_shift_s:     0.2,
  win_shift_s:      0.2,
  alt_print_screen: 0.2,
};

// localStorage key — looks like a harmless render preference
const _REP_KEY = '_pref_render';

// ── Date helpers (IST to match game day boundary) ──────────────────────────

function _nowIST() {
  return new Date(Date.now() + 5.5 * 3600000);
}

function _todayIST() {
  return _nowIST().toISOString().slice(0, 10);
}

function _yesterdayIST() {
  const d = new Date(Date.now() + 5.5 * 3600000 - 86400000);
  return d.toISOString().slice(0, 10);
}

// ── Reputation persistence ─────────────────────────────────────────────────

function _readReputation() {
  try {
    const raw = localStorage.getItem(_REP_KEY);
    if (!raw) return { d: [], n: 0 };
    try {
      const data = JSON.parse(raw);
      return { d: Array.isArray(data.d) ? data.d : [], n: data.n || 0 };
    } catch {
      // Backward compat: old format was a plain number string
      return { d: [], n: parseInt(raw, 10) || 0 };
    }
  } catch { return { d: [], n: 0 }; }
}

function _getReputationPenalty() {
  const { n } = _readReputation();
  if (n >= 3) return 0.3;
  if (n >= 2) return 0.2;
  if (n >= 1) return 0.1;
  return 0;
}

function _getCheatStreak() {
  const data = _readReputation();
  if (data.d.length === 0) return 0;
  const dates = [...new Set(data.d)].sort().reverse();
  const yesterday = _yesterdayIST();
  const today = _todayIST();
  // Streak must be recent (end at today or yesterday)
  if (dates[0] !== today && dates[0] !== yesterday) return 0;
  let streak = 1;
  for (let i = 1; i < dates.length; i++) {
    const diff = (new Date(dates[i - 1]) - new Date(dates[i])) / 86400000;
    if (Math.abs(diff - 1) < 0.1) { streak++; } else { break; }
  }
  return streak;
}

// ── Public API ─────────────────────────────────────────────────────────────

export function startMonitoring(round) {
  _monitoring = true;
  _currentRound = round;
  _currentPhase = 'memorize';
  _blurStart = 0;
  _rightClickCount = 0;
}

export function setPhaseGuess() {
  // If the user was blurred during memorize and timer expired,
  // check if we should record it before switching phase
  if (_blurStart > 0) {
    const duration = Date.now() - _blurStart;
    if (duration >= _BLUR_MIN_DURATION && _currentPhase === 'memorize') {
      _recordIfNotDebounced('window_blur');
    }
    _blurStart = 0;
  }
  _currentPhase = 'guess';
}

export function stopMonitoring() {
  _monitoring = false;
  _blurStart = 0;
}

export function getEvents() {
  return [..._events];
}

/**
 * Per-round score cap based on current cheat events + reputation.
 */
export function getScoreCap() {
  const count = _events.length;
  let inGamePenalty = 0;
  if (count >= 3) {
    inGamePenalty = 0.5;
  } else if (count > 0) {
    inGamePenalty = _events.reduce((sum, e) => sum + (_SEVERITY[e.type] || 0.1), 0);
  }
  const repPenalty = _getReputationPenalty();
  return Math.max(0, Math.min(10 - inGamePenalty, 10 - repPenalty));
}

/**
 * Which rounds (1-indexed) should have their guess corrupted.
 * Only triggers if the player is also cheating in the current session.
 */
export function getGlitchRounds() {
  if (_events.length === 0) return [];
  const pastStreak = _getCheatStreak();
  const today = _todayIST();
  const alreadyCounted = _readReputation().d.includes(today);
  const effective = alreadyCounted ? pastStreak : pastStreak + 1;
  if (effective >= 5) return [4, 5];
  if (effective >= 3) return [5];
  return [];
}

/**
 * Silently corrupt a guess to produce a bad CIEDE2000 score.
 * The corruption intensity scales with streak length.
 */
export function corruptGuess(guess) {
  const pastStreak = _getCheatStreak();
  const effective = pastStreak + 1;
  const intensity = Math.min(1.0, (effective - 2) * 0.25);
  // Hue: shift 50-90°
  const hShift = 50 + intensity * 40;
  const hDir = Math.random() > 0.5 ? 1 : -1;
  const h = Math.round((guess.h + hDir * hShift + 360) % 360);
  // Saturation: shift 20-40
  const sShift = 20 + intensity * 20;
  const sDir = Math.random() > 0.5 ? 1 : -1;
  const s = Math.round(Math.max(0, Math.min(100, guess.s + sDir * sShift)));
  // Brightness: shift 10-20
  const bShift = 10 + intensity * 10;
  const bDir = Math.random() > 0.5 ? 1 : -1;
  const b = Math.round(Math.max(0, Math.min(100, guess.b + bDir * bShift)));
  return { h, s, b };
}

/**
 * Commit this cheat session to persistent reputation.
 * Called once at game end when cheat events were detected.
 */
export function commitReputation() {
  if (_events.length === 0) return;
  try {
    const data = _readReputation();
    const today = _todayIST();
    if (!data.d.includes(today)) {
      data.d.push(today);
      data.n++;
    }
    // Keep only last 30 days
    const cutoff = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
    data.d = data.d.filter(d => d >= cutoff);
    localStorage.setItem(_REP_KEY, JSON.stringify(data));
  } catch { /* no-op */ }
}

// ── Event recording ────────────────────────────────────────────────────────

function record(type) {
  if (!_monitoring) return;
  _events.push({ type, round: _currentRound, phase: _currentPhase, time: Date.now() });
}

/**
 * Record only if we haven't recently recorded a blur (debounce).
 */
function _recordIfNotDebounced(type) {
  const now = Date.now();
  if (now - _blurDebounce < _BLUR_DEBOUNCE_MS) return;
  _blurDebounce = now;
  record(type);
}

/**
 * Initialize all event listeners. Call once on page load.
 * Listeners are passive — they never preventDefault or give any visual hint.
 */
export function initAntiCheat() {
  // ── Keyboard shortcuts (screenshot tools) ──────────────────────────────
  // These are always suspicious regardless of phase — immediately recorded.
  window.addEventListener('keydown', (e) => {
    if (!_monitoring) return;
    if (e.key === 'PrintScreen') record('print_screen');
    if (e.ctrlKey && e.shiftKey && (e.key === 'S' || e.key === 's')) record('ctrl_shift_s');
    if (e.altKey && e.key === 'PrintScreen') record('alt_print_screen');
    if (e.metaKey && e.shiftKey && (e.key === 'S' || e.key === 's')) record('win_shift_s');
  });

  // ── Window blur (focus loss) ───────────────────────────────────────────
  // Only suspicious during MEMORIZE phase (user is supposed to be staring
  // at the color, so switching apps is fishy). During GUESS phase the user
  // may accidentally click near the browser edge, get a notification, etc.
  // Additionally, the blur must be SUSTAINED (≥2 seconds) — brief flickers
  // from OS notifications, taskbar hover, etc. are harmless.
  window.addEventListener('blur', () => {
    if (!_monitoring) return;
    // Only track during memorize — guess-phase blurs are harmless
    if (_currentPhase !== 'memorize') return;
    _blurStart = Date.now();
  });

  window.addEventListener('focus', () => {
    if (!_monitoring) return;
    if (_blurStart === 0) return;
    const duration = Date.now() - _blurStart;
    _blurStart = 0;
    // Only flag if the blur lasted long enough to actually look something up
    if (duration >= _BLUR_MIN_DURATION && _currentPhase === 'memorize') {
      _recordIfNotDebounced('window_blur');
    }
  });

  // ── Tab hidden (visibility change) ─────────────────────────────────────
  // Like blur, only meaningful during memorize. Switching tabs during guess
  // phase doesn't help cheating (color is already gone from screen).
  document.addEventListener('visibilitychange', () => {
    if (!_monitoring) return;
    if (_currentPhase !== 'memorize') return;
    if (document.hidden) record('tab_hidden');
  });

  // ── Right-click ────────────────────────────────────────────────────────
  // A single right-click can be accidental. Only flag if the user does it
  // repeatedly (trying to inspect element / save image).
  document.addEventListener('contextmenu', () => {
    if (!_monitoring) return;
    _rightClickCount++;
    if (_rightClickCount >= _RIGHTCLICK_THRESHOLD) {
      record('right_click');
    }
  });
}
