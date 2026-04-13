const crypto = require('crypto');

module.exports = (req, res) => {
  if (req.method !== 'GET') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  const { token } = req.query;
  if (!token) {
    return res.status(400).json({ error: 'Token required' });
  }

  const secret = process.env.HMAC_SECRET;
  if (!secret) {
    return res.status(500).json({ error: 'Server misconfigured' });
  }

  const dotIdx = token.lastIndexOf('.');
  if (dotIdx === -1) {
    return res.status(401).json({ error: 'Invalid token format' });
  }

  const payloadB64 = token.slice(0, dotIdx);
  const sig = token.slice(dotIdx + 1);

  // Verify HMAC signature
  const expectedSig = crypto
    .createHmac('sha256', secret)
    .update(payloadB64)
    .digest('hex');

  if (sig !== expectedSig) {
    return res.status(401).json({ error: 'Invalid signature' });
  }

  // Decode payload
  try {
    const padded = payloadB64 + '='.repeat((4 - (payloadB64.length % 4)) % 4);
    const payload = JSON.parse(Buffer.from(padded, 'base64url').toString('utf-8'));

    // Check expiry
    if (payload.exp && payload.exp < Math.floor(Date.now() / 1000)) {
      return res.status(401).json({ error: 'Token expired' });
    }

    return res.status(200).json({
      user_id: payload.user_id,
      username: payload.username,
    });
  } catch (e) {
    return res.status(401).json({ error: 'Malformed token payload' });
  }
};
