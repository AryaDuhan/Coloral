# 🎨 Coloral — Dialed.gg Discord Bot

A Discord bot that tracks daily scores from [dialed.gg](https://dialed.gg), a color memory game. Players paste their daily results in chat and the bot automatically parses, records, and ranks them on a live leaderboard.

## Features

- **📅 Daily Score Tracking** — Paste your daily result and the bot records it instantly
- **🏆 Live Leaderboard** — See today's rankings after every submission
- **📊 Player Stats** — Track your average, personal best, streak, and more
- **📈 Score Graph** — Visualize your score history over time
- **🎨 Color Command** — Random color info for fun
- **⏰ Daily Reminder** — Automatic midnight (12:00 AM IST) ping to all leaderboard players to play the new daily
- **🎮 Play Button** — One-click link to dialed.gg with a smart 40-second "share your score" reminder (skipped if you already submitted)

## Setup

### 1. Create a Discord Bot
1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
2. New Application → Bot tab → Copy the token
3. Enable **Message Content Intent** under Privileged Gateway Intents
4. Invite the bot using: `https://discord.com/oauth2/authorize?client_id=YOUR_APP_ID&scope=bot+applications.commands&permissions=93248`

### 2. Configure
```bash
cp .env.example .env
```
Edit `.env` and paste your bot token.

To restrict score tracking to one channel, edit `config.py`:
```python
SCORE_CHANNEL_ID = 1234567890  # Your channel ID
```

### 3. Set Up Reminders

Once the bot is online, use the `/set_reminder_channel` slash command in your server to choose where daily reminders are posted. The bot sends reminders at **12:00 AM IST (18:30 UTC)** by default.

You can customize the time via environment variables:
```bash
# In your .env file (24-hour UTC format)
REMINDER_HOUR=18
REMINDER_MINUTE=30
```

> **Note:** The reminder has catch-up logic — if the bot is offline at the scheduled time, it will send the reminder as soon as it comes back online.

### 4. Run

**With Python:**
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
python bot.py
```

**With Docker:**
```bash
docker compose up -d
```

**On Android (Termux):** See [DEPLOY_ANDROID.md](DEPLOY_ANDROID.md) for a full guide.

## Score Format

The bot accepts daily scores in these formats:

```
Dialed Daily — Apr 5
40.41/50 🟨🟧🟩🟧🟨
dialed.gg?d=1&s=40.41
```

Or just the URL:
```
https://dialed.gg?d=1&s=46.24
```

## Commands

| Command | Description |
|---------|-------------|
| `/leaderboard` | Today's daily rankings |
| `/stats` | Your personal stats |
| `/stats @player` | Another player's stats |
| `/graph` | Your score history chart |
| `/color` | Random color info |
| `/set_reminder_channel` | Set where daily reminders are posted (Admin) |
| `/test_reminder` | Send a test reminder to verify setup (Admin) |

## Reminders

The bot has two types of reminders:

1. **Daily Reminder (12:00 AM IST)** — Automatically pings all leaderboard players in the configured channel to play the new daily puzzle. Uses catch-up logic so it never misses a day even if the bot restarts.

2. **Play Reminder (40 seconds)** — When a player clicks the "▶️ Play Daily" button, the bot waits 40 seconds then nudges them to share their score. This reminder is **automatically skipped** if the player already submitted their score.

## License

MIT
