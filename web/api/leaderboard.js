module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');

  if (req.method === 'OPTIONS') {
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
    return res.status(200).end();
  }

  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const webhookUrl = process.env.DISCORD_WEBHOOK_URL;
  const msgId = process.env.LEADERBOARD_MSG_ID;

  if (!webhookUrl || !msgId) {
    return res.status(200).json({ scores: [] });
  }

  try {
    // Parse webhook URL to get id/token
    const parts = webhookUrl.replace(/\/$/, '').split('/');
    const webhookToken = parts.pop();
    const webhookId = parts.pop();

    // Fetch the leaderboard message
    const response = await fetch(
      `https://discord.com/api/v10/webhooks/${webhookId}/${webhookToken}/messages/${msgId}`
    );

    if (!response.ok) {
      console.error('Failed to fetch leaderboard message:', response.status);
      return res.status(200).json({ scores: [] });
    }

    const message = await response.json();

    // Parse JSON from message content
    let data;
    try {
      // Content is stored as raw JSON
      data = JSON.parse(message.content);
    } catch (e) {
      return res.status(200).json({ scores: [] });
    }

    // Check if the game is current (today in game timezone = IST, UTC+5:30)
    const now = new Date();
    const istTime = new Date(now.getTime() + (5.5 * 60 * 60 * 1000));
    const todayGame = parseInt(
      `${istTime.getUTCFullYear()}${String(istTime.getUTCMonth() + 1).padStart(2, '0')}${String(istTime.getUTCDate()).padStart(2, '0')}`
    );

    if (data.game !== todayGame) {
      // Stale data from a previous day
      return res.status(200).json({ scores: [] });
    }

    // Return sorted scores
    const sorted = (data.scores || []).sort((a, b) => b.total_score - a.total_score);
    return res.status(200).json({ scores: sorted });

  } catch (e) {
    console.error('Leaderboard fetch error:', e);
    return res.status(200).json({ scores: [] });
  }
};
