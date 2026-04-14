/**
 * audio.js — Audio system using real MP3 files.
 *
 * Files:
 *  - /audio/mech timer better.mp3  → score counting tick (variable speed)
 *  - /audio/3 sec countdown.mp3    → 3-2-1 countdown before memorize
 *  - /audio/beap.mp3               → beep when 5s timer ends
 */

const AudioContext = window.AudioContext || window.webkitAudioContext;
let audioCtx;

// Pre-decoded audio buffers
const buffers = {};
const AUDIO_FILES = {
  mechTick:   '/audio/mech timer better.mp3',
  countdown:  '/audio/3 sec countdown.mp3',
  beep:       '/audio/beap.mp3',
  mechTimer:  '/audio/mechanical Timer.mp3',
};

/** Must be called from a user gesture (click), returns a Promise when loaded */
export async function initAudio() {
  if (!audioCtx) {
    audioCtx = new AudioContext();
  }
  if (audioCtx.state === 'suspended') {
    await audioCtx.resume();
  }
  // Pre-load all audio files
  const promises = Object.entries(AUDIO_FILES).map(async ([key, url]) => {
    if (!buffers[key]) {
      try {
        const r = await fetch(url);
        const buf = await r.arrayBuffer();
        buffers[key] = await audioCtx.decodeAudioData(buf);
      } catch (e) {
        console.warn(`[audio] Failed to load ${key}:`, e);
      }
    }
  });

  await Promise.all(promises);
}

/**
 * Play a buffer with optional playback rate and volume.
 * Returns the source node for further control.
 */
function playBuffer(key, rate = 1.0, volume = 1.0, loop = false) {
  if (!audioCtx || !buffers[key]) return null;
  const source = audioCtx.createBufferSource();
  const gain = audioCtx.createGain();
  source.buffer = buffers[key];
  source.playbackRate.value = rate;
  source.loop = loop;
  gain.gain.value = volume;
  source.connect(gain);
  gain.connect(audioCtx.destination);
  source.start(0);
  return source;
}

let currentScoreTick = null;
let currentTimerTick = null;
let currentCountdown = null;

export function startScoreTick() {
  stopScoreTick();
  currentScoreTick = playBuffer('mechTick', 2.0, 0.4, true); 
}

export function updateScoreTickRate(progress) {
  if (currentScoreTick) {
    // Map progress 0→1 to playback rate fast→slow
    const rate = Math.max(0.3, 2.0 - (progress * 1.5));
    // Provide a small ramp to prevent audio clicking
    currentScoreTick.playbackRate.setTargetAtTime(rate, audioCtx.currentTime, 0.05);
  }
}

export function stopScoreTick() {
  if (currentScoreTick) {
    try { currentScoreTick.stop(); } catch(e){}
    currentScoreTick.disconnect();
    currentScoreTick = null;
  }
}

/** Play the 3-second countdown audio */
export function playCountdownAudio() {
  if (currentCountdown) {
    try { currentCountdown.stop(); } catch(e){}
  }
  currentCountdown = playBuffer('countdown', 1.0, 0.35, false);
}

export function stopCountdownAudio() {
  if (currentCountdown) {
    try { currentCountdown.stop(); } catch(e){}
    currentCountdown = null;
  }
}

/** Play the beep when 5s timer ends */
export function playTimerEnd() {
  playBuffer('beep', 1.0, 0.4, false);
}

/** Mechanical tick for the memorize timer countdown */
export function startTimerTick() {
  stopTimerTick();
  currentTimerTick = playBuffer('mechTimer', 1.0, 0.45, true);
}

export function stopTimerTick() {
  if (currentTimerTick) {
    try { currentTimerTick.stop(); } catch(e){}
    currentTimerTick.disconnect();
    currentTimerTick = null;
  }
}

/** Final "ding" when score reveal completes */
export function playDing(score) {
  if (!audioCtx) return;
  const t = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();

  osc.type = 'sine';
  const freq = 400 + (score / 10) * 800;
  osc.frequency.setValueAtTime(freq, t);

  gain.gain.setValueAtTime(0, t);
  gain.gain.linearRampToValueAtTime(0.2, t + 0.05);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.6);

  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(t);
  osc.stop(t + 0.6);
}

/** Satisfying small mechanical click for slider dragging */
export function playSliderTick(intensity = 1.0) {
  if (!audioCtx || audioCtx.state !== 'running') return;
  const t = audioCtx.currentTime;
  const osc = audioCtx.createOscillator();
  const gain = audioCtx.createGain();

  // A very short, crisp, high-frequency ping removes the "bassy" feel
  osc.type = 'sine';
  osc.frequency.setValueAtTime(1800, t);
  osc.frequency.exponentialRampToValueAtTime(600, t + 0.02);

  // Extremely tight envelope (~15ms)
  gain.gain.setValueAtTime(0.2 * intensity, t);
  gain.gain.exponentialRampToValueAtTime(0.001, t + 0.015);

  osc.connect(gain);
  gain.connect(audioCtx.destination);
  osc.start(t);
  osc.stop(t + 0.02);
}
