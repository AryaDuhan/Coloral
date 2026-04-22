import { getDailyColors } from './colors.js';

export function cacheScore(scoreObj) {
  let cached = [];
  try {
    const str = localStorage.getItem('coloral_cached_scores');
    if (str) cached = JSON.parse(str);
  } catch (e) {}
  if (!Array.isArray(cached)) cached = [];
  
  cached.push(scoreObj);
  localStorage.setItem('coloral_cached_scores', JSON.stringify(cached));
}

export async function syncCachedScores() {
  const cachedStr = localStorage.getItem('coloral_cached_scores');
  if (!cachedStr) return;
  
  let cached = [];
  try { cached = JSON.parse(cachedStr); } catch(e) { return; }
  if (!Array.isArray(cached) || cached.length === 0) return;
  
  const { gameNumber: currentDailyGameNumber } = getDailyColors();
  const remaining = [];
  
  for (const scoreObj of cached) {
    if (scoreObj.mode === 'daily' && scoreObj.gameNumber !== currentDailyGameNumber) {
      // Discard old daily scores as they cannot be on today's leaderboard
      continue;
    }
    
    try {
      const res = await fetch('/api/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: scoreObj.token,
          scores: scoreObj.roundScores,
          totalScore: scoreObj.totalScore,
          cheatEvents: scoreObj.cheatEvents,
          isTest: scoreObj.isTest,
          roundData: scoreObj.roundData,
          mode: scoreObj.mode
        }),
      });
      // If the server returns an error like 4xx (e.g. invalid token, already submitted), we drop it from cache
      // If it returns 5xx, we might want to keep it, but for simplicity, we only keep if there's a network error
      if (res.status >= 500) {
        remaining.push(scoreObj);
      }
    } catch(e) {
      // Network error, keep in cache
      remaining.push(scoreObj);
    }
  }
  
  if (remaining.length > 0) {
    localStorage.setItem('coloral_cached_scores', JSON.stringify(remaining));
  } else {
    localStorage.removeItem('coloral_cached_scores');
  }
}

// Listen for connection return
window.addEventListener('online', syncCachedScores);
