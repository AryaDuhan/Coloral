const crypto = require('crypto');

module.exports = async (req, res) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const secret = process.env.HMAC_SECRET;
  const webhookUrl = process.env.DISCORD_WEBHOOK_URL;

  if (!secret || !webhookUrl) {
    console.error('Missing HMAC_SECRET or DISCORD_WEBHOOK_URL');
    return res.status(500).json({ error: 'Server misconfigured' });
  }

  const { token, scores, totalScore, cheatEvents, isTest, roundData } = req.body;

  if (!token || !scores || totalScore == null) {
    return res.status(400).json({ error: 'Missing required fields' });
  }

  // ── Validate Token ───────────────────────────────────────────────────────
  const dotIdx = token.lastIndexOf('.');
  if (dotIdx === -1) {
    return res.status(401).json({ error: 'Invalid token' });
  }

  const payloadB64 = token.slice(0, dotIdx);
  const sig = token.slice(dotIdx + 1);

  const expectedSig = crypto
    .createHmac('sha256', secret)
    .update(payloadB64)
    .digest('hex');

  if (sig !== expectedSig) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  let userId, username;
  try {
    const padded = payloadB64 + '='.repeat((4 - (payloadB64.length % 4)) % 4);
    const payload = JSON.parse(Buffer.from(padded, 'base64url').toString('utf-8'));

    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return res.status(401).json({ error: 'Token expired' });
    }

    userId = payload.user_id;
    username = payload.username;
  } catch (e) {
    return res.status(401).json({ error: 'Malformed token' });
  }

  // ── Build Score Data ─────────────────────────────────────────────────────
  const now = new Date();
  const gameNumber = parseInt(
    `${now.getFullYear()}${String(now.getMonth() + 1).padStart(2, '0')}${String(now.getDate()).padStart(2, '0')}`
  );

  const roundedTotal = parseFloat(totalScore.toFixed(2));
  const cheatCount = Array.isArray(cheatEvents) ? cheatEvents.length : 0;

  // Emoji bar
  const emojis = scores
    .map((s) => {
      if (s >= 8) return '🟩';
      if (s >= 6) return '🟨';
      if (s >= 4) return '🟧';
      return '🟥';
    })
    .join('');

  // Date label
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  const dateLabel = `${months[now.getMonth()]} ${now.getDate()}`;

  // HMAC signature of score data for bot verification
  const scoreData = `${userId}:${gameNumber}:${roundedTotal}:${cheatCount}`;
  const scoreSig = crypto
    .createHmac('sha256', secret)
    .update(scoreData)
    .digest('hex')
    .slice(0, 16);

  // ── Build Cheat Details (if any) ─────────────────────────────────────────
  let cheatDetails = '';
  if (cheatCount > 0) {
    cheatDetails = cheatEvents
      .map((e) => `R${e.round}:${e.type}`)
      .join(',');
  }

  // ── Post to Discord Webhook ──────────────────────────────────────────────
  // The embed footer carries verification data for the bot to parse.
  const footerParts = [userId, gameNumber, roundedTotal, cheatCount, scoreSig];
  if (cheatDetails) footerParts.push(cheatDetails);
  else if (roundData) footerParts.push(""); // pad if missing and we need to append more 
  
  if (roundData) footerParts.push(""); // pad the "TEST" spot to maintain the pipe delimited protocol

  if (roundData) footerParts.push(roundData);

  // Pick embed color based on score
  let embedColor = 0x6BCB77; // green
  if (roundedTotal < 25) embedColor = 0xEF233C; // red
  else if (roundedTotal < 35) embedColor = 0xFFD166; // yellow

  const scoreBar = scores.map((s) => `\`${s.toFixed(1)}\``).join('  ');
  const displayTitle = `🎨 ${username}`;

  const webhookPayload = {
    username: 'Colorle',
    embeds: [
      {
        title: displayTitle,
        description: `**Dialed Daily** — ${dateLabel}\n**${roundedTotal}/50** ${emojis}\n\n${scoreBar}`,
        color: embedColor,
        footer: {
          text: footerParts.join('|'),
        },
      },
    ],
  };

  try {
    const response = await fetch(webhookUrl + '?wait=true', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(webhookPayload),
    });

    if (!response.ok) {
      const errText = await response.text();
      console.error('Webhook failed:', response.status, errText);
      // Even if webhook fails, generate share link as fallback
    }

    // Generate tamper-proof share link
    const shareData = `${userId}:${gameNumber}:${roundedTotal}:${roundData || ''}`;
    const shareSig = crypto
      .createHmac('sha256', secret)
      .update(shareData)
      .digest('hex')
      .slice(0, 16);

    const shareParams = new URLSearchParams({
      u: userId,
      g: String(gameNumber),
      s: String(roundedTotal),
      n: username,
    });
    if (roundData) shareParams.set('r', roundData);
    shareParams.set('sig', shareSig);

    const siteUrl = process.env.WEBSITE_URL || req.headers.host;
    const shareUrl = `https://${siteUrl}/share?${shareParams.toString()}`;

    if (!response || !response.ok) {
      return res.status(200).json({
        success: true,
        score: roundedTotal,
        emojis,
        shareUrl,
        webhookFailed: true,
      });
    }

    return res.status(200).json({
      success: true,
      score: roundedTotal,
      emojis,
      shareUrl,
    });
  } catch (e) {
    console.error('Webhook error:', e);
    return res.status(500).json({ error: 'Failed to post score to Discord' });
  }
};
