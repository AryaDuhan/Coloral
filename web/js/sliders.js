/**
 * sliders.js — Custom vertical HSB slider controls.
 *
 * Creates three vertical sliders (Hue, Saturation, Brightness) with:
 *  - Hue: full rainbow gradient (static)
 *  - Saturation: dynamic gradient from grey to fully saturated at current hue
 *  - Brightness: dynamic gradient from black to current hue+sat
 *  - Touch + mouse drag support
 *  - White circle thumb
 */

import { hsbToCss } from './scoring.js';
import { playSliderTick } from './audio.js';

/**
 * Create HSB sliders inside a container element.
 *
 * @param {HTMLElement} container  The .sliders-panel element
 * @param {function}    onChange   Callback: (h, s, b) => void — called on every drag tick
 * @returns {{ getValues: () => {h,s,b}, destroy: () => void }}
 */
export function createSliders(container, onChange) {
  let h = 180, s = 50, b = 50;

  // ── Build DOM ──────────────────────────────────────────────────────────────
  const sliders = [
    { key: 'h', label: 'H', min: 0, max: 360, className: 'hue-track' },
    { key: 's', label: 'S', min: 0, max: 100, className: 'sat-track' },
    { key: 'b', label: 'B', min: 0, max: 100, className: 'bri-track' },
  ];

  const els = {};

  sliders.forEach((cfg) => {
    const group = document.createElement('div');
    group.className = 'slider-group';

    const track = document.createElement('div');
    track.className = `slider-track ${cfg.className}`;
    track.dataset.key = cfg.key;

    const thumb = document.createElement('div');
    thumb.className = 'slider-thumb';
    track.appendChild(thumb);

    group.appendChild(track);
    container.appendChild(group);

    els[cfg.key] = { track, thumb };
  });

  // ── Gradient Updates ───────────────────────────────────────────────────────
  function updateGradients() {
    // Saturation track: grey → fully saturated at current hue & brightness
    const greyCol = hsbToCss(h, 0, b);
    const fullSatCol = hsbToCss(h, 100, b);
    els.s.track.style.backgroundImage = `linear-gradient(to bottom, ${fullSatCol}, ${greyCol})`;

    // Brightness track: current hue+sat → black
    const brightCol = hsbToCss(h, s, 100);
    els.b.track.style.backgroundImage = `linear-gradient(to bottom, ${brightCol}, #000)`;
  }

  // ── Thumb Positioning ──────────────────────────────────────────────────────
  function updateThumbs() {
    const hPct = h / 360;
    const sPct = 1 - s / 100; // inverted: top = 100%
    const bPct = 1 - b / 100;

    const setPos = (thumb, track, pct) => {
      const trackH = track.clientHeight;
      const clampedPct = Math.max(0, Math.min(1, pct));
      thumb.style.top = `${clampedPct * trackH - 11}px`;
    };

    setPos(els.h.thumb, els.h.track, hPct);
    setPos(els.s.thumb, els.s.track, sPct);
    setPos(els.b.thumb, els.b.track, bPct);
  }

  // ── Drag Logic ─────────────────────────────────────────────────────────────
  function handleDrag(track, key, clientY) {
    const rect = track.getBoundingClientRect();
    let pct = (clientY - rect.top) / rect.height;
    pct = Math.max(0, Math.min(1, pct));

    let changed = false;

    if (key === 'h') {
      const n = Math.round(pct * 360);
      if (h !== n) { h = n; changed = true; }
    } else if (key === 's') {
      const n = Math.round((1 - pct) * 100); // inverted
      if (s !== n) { s = n; changed = true; }
    } else {
      const n = Math.round((1 - pct) * 100); // inverted
      if (b !== n) { b = n; changed = true; }
    }

    if (changed) {
      // Throttle ticking by only ticking when the value crosses a threshold (like every 2 units)
      // to avoid sound buzz when dragging slowly.
      if ((key === 'h' && h % 2 === 0) || (key !== 'h' && (key === 's' ? s % 2 === 0 : b % 2 === 0))) {
         playSliderTick(0.6);
      }
      
      updateGradients();
      updateThumbs();
      onChange(h, s, b);
    }
  }

  // Attach pointer events to each track
  const cleanups = [];

  Object.entries(els).forEach(([key, { track }]) => {
    let dragging = false;

    const onDown = (e) => {
      dragging = true;
      const y = e.touches ? e.touches[0].clientY : e.clientY;
      handleDrag(track, key, y);
    };

    const onMove = (e) => {
      if (!dragging) return;
      e.preventDefault();
      const y = e.touches ? e.touches[0].clientY : e.clientY;
      handleDrag(track, key, y);
    };

    const onUp = () => { dragging = false; };

    track.addEventListener('mousedown', onDown);
    track.addEventListener('touchstart', onDown, { passive: true });
    window.addEventListener('mousemove', onMove);
    window.addEventListener('touchmove', onMove, { passive: false });
    window.addEventListener('mouseup', onUp);
    window.addEventListener('touchend', onUp);

    cleanups.push(() => {
      track.removeEventListener('mousedown', onDown);
      track.removeEventListener('touchstart', onDown);
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('touchmove', onMove);
      window.removeEventListener('mouseup', onUp);
      window.removeEventListener('touchend', onUp);
    });
  });

  // ── Initial render ─────────────────────────────────────────────────────────
  updateGradients();
  // Thumbs positioned after a RAF to ensure layout is ready
  requestAnimationFrame(() => {
    updateThumbs();
  });

  return {
    getValues: () => ({ h, s, b }),
    destroy: () => cleanups.forEach((fn) => fn()),
  };
}
