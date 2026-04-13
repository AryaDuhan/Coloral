/**
 * anticheat.js — Silent screenshot/snip detection during memorize phases.
 *
 * Monitors for:
 *  - PrintScreen key
 *  - Ctrl+Shift+S / Win+Shift+S (Snipping Tool shortcuts)
 *  - Alt+PrintScreen
 *  - Window blur (losing focus → switching to screenshot tool)
 *  - Tab hidden (visibility change)
 *  - Right-click (context menu → "Save Image")
 *
 * Events are collected silently and sent with the score submission.
 * The player NEVER sees any indication of detection.
 */

let _monitoring = false;
let _currentRound = 0;
const _events = [];

/**
 * Start monitoring for suspicious activity (called when memorize phase begins).
 * @param {number} round  Current round number (1-5)
 */
export function startMonitoring(round) {
  _monitoring = true;
  _currentRound = round;
}

/** Stop monitoring (called when memorize phase ends). */
export function stopMonitoring() {
  _monitoring = false;
}

/** Get all recorded suspicious events. */
export function getEvents() {
  return [..._events];
}

function record(type) {
  if (!_monitoring) return;
  _events.push({ type, round: _currentRound, time: Date.now() });
}

/**
 * Initialize all event listeners. Call once on page load.
 * Listeners are passive — they never preventDefault or give any visual hint.
 */
export function initAntiCheat() {
  // Keyboard shortcuts
  window.addEventListener('keydown', (e) => {
    if (!_monitoring) return;

    if (e.key === 'PrintScreen') {
      record('print_screen');
    }
    // Ctrl+Shift+S (common snip shortcut)
    if (e.ctrlKey && e.shiftKey && (e.key === 'S' || e.key === 's')) {
      record('ctrl_shift_s');
    }
    // Alt+PrintScreen (capture active window)
    if (e.altKey && e.key === 'PrintScreen') {
      record('alt_print_screen');
    }
    // Meta (Win) + Shift + S  —  sometimes detectable
    if (e.metaKey && e.shiftKey && (e.key === 'S' || e.key === 's')) {
      record('win_shift_s');
    }
  });

  // Window losing focus (e.g., Snipping Tool overlay activates)
  window.addEventListener('blur', () => {
    record('window_blur');
  });

  // Tab becomes hidden (alt-tab, minimize, etc.)
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      record('tab_hidden');
    }
  });

  // Right-click on the page
  document.addEventListener('contextmenu', () => {
    record('right_click');
    // Do NOT call e.preventDefault() — that would reveal detection
  });
}
