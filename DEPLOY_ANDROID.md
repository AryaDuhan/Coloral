# 📱 Hosting Dialed Bot on Android (Termux)

This guide walks you through running the bot 24/7 on an Android phone using **Termux**.

> **Recommended:** Use an old/spare phone you can keep plugged in — it'll act as a dedicated mini server.

---

## 1. Install Termux

Download **Termux** from [F-Droid](https://f-droid.org/en/packages/com.termux/) (NOT from the Play Store — the Play Store version is outdated and broken).


---

## 2. Initial Setup (run once)

Open Termux and run these commands one by one:

```bash
# Update packages
pkg update && pkg upgrade -y

# Install required tools
pkg install -y python git

# (Optional) Install build tools — needed if pip packages have C extensions
pkg install -y build-essential libffi openssl
```

---

## 3. Clone the Repo

```bash
# Clone your repo (use HTTPS — works even if the repo is private with a PAT)
git clone https://github.com/AryaDuhan/Coloral.git
cd Coloral
```

## 4. Set Up Python Environment

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 5. Create Your `.env` File

```bash
cp .env.example .env
nano .env
```

Fill in your bot token:
```
DISCORD_TOKEN=your_actual_bot_token_here
```

The reminder time defaults to **12:00 AM IST (18:30 UTC)**. To customize:
```
REMINDER_HOUR=18
REMINDER_MINUTE=30
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

---

## 6. Run the Bot

```bash
bash start.sh
```
The bot runs and auto-restarts on crash. Press `Ctrl+C` to stop.

---

## 7. Set Up Reminders

Once the bot is online and in your Discord server:

1. **Run `/set_reminder_channel`** and pick the channel where daily reminders should go.
2. **Run `/test_reminder`** to verify it works — a test message should appear in your chosen channel.

The bot will now:
- **Daily at 12:00 AM IST** — Tag all leaderboard players to play the new puzzle
- **40s after clicking Play** — Nudge the player to share their score (skipped if they already submitted)

> **Note:** If the bot is offline at midnight, it will send the reminder as soon as it comes back online (catch-up logic).

---

## 8. Keep the Phone Awake

Android aggressively kills background processes. Do ALL of these:

1. **Disable battery optimization for Termux:**
   Settings → Apps → Termux → Battery → Unrestricted

2. **Acquire a Termux wakelock** (prevents the CPU from sleeping):
   ```bash
   termux-wake-lock
   ```

3. **Keep the screen on** (optional but helps on older phones):
   Settings → Developer options → Stay awake while charging

4. **Keep it plugged in** — it's a server now, treat it like one.

---

## 9. Pulling Updates Later

```bash
cd ~/Coloral
git pull
# Restart the bot (Ctrl+C the running one first)
bash start.sh
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start bot | `bash start.sh` |
| Stop bot | `Ctrl+C` |
| Prevent sleep | `termux-wake-lock` |
| Update code | `git pull` |
| Set reminder channel | `/set_reminder_channel` (in Discord) |
| Test reminder | `/test_reminder` (in Discord) |
