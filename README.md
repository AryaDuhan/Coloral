# 🎨 Coloral — Dialed.gg Discord Bot

A Discord bot that tracks daily scores from [dialed.gg](https://dialed.gg), a color memory game. Players paste their daily results in chat and the bot automatically parses, records, and ranks them on a live leaderboard.

## Features

- **📅 Daily Score Tracking** — Paste your daily result and the bot records it instantly
- **🏆 Live Leaderboard** — See today's rankings after every submission
- **📊 Player Stats** — Track your average, personal best, streak, and more
- **📈 Score Graph** — Visualize your score history over time
- **🎨 Color Command** — Random color info for fun
- **⏰ Daily Reminder** — Configurable daily ping to play the puzzle
- **🎮 Play Button** — One-click link to dialed.gg with a "I'm Playing!" reminder

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
Edit `.env` and paste your bot token. Optionally set `REMINDER_CHANNEL_ID` to a channel ID for daily reminders.

To restrict score tracking to one channel, edit `config.py`:
```python
SCORE_CHANNEL_ID = 1234567890  # Your channel ID
```

### 3. Run

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

**On Android (Termux):**
```bash
pkg install python git
git clone https://github.com/YOUR_USERNAME/dialed-bot.git
cd dialed-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

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

## License

MIT
