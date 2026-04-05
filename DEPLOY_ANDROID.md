# 📱 Hosting Dialed Bot on Android (Termux)

This guide walks you through running the bot 24/7 on an old Android phone using **Termux**.

---

## 1. Install Termux

Download **Termux** from [F-Droid](https://f-droid.org/en/packages/com.termux/) (NOT from the Play Store — the Play Store version is outdated and broken).

> **Tip:** Also install **Termux:Boot** from F-Droid if you want the bot to auto-start when the phone reboots.

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

> **Private repo?** Use a Personal Access Token:
> ```bash
> git clone https://<YOUR_PAT>@github.com/AryaDuhan/Coloral.git
> ```
> Generate one at: GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens.

---

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

Save with `Ctrl+X`, then `Y`, then `Enter`.

---

## 6. Run the Bot

### Option A: Foreground (simple)
```bash
bash start.sh
```
The bot runs and auto-restarts on crash. Press `Ctrl+C` to stop.

### Option B: Background (survives closing Termux)
```bash
nohup bash start.sh > bot.log 2>&1 &
```
Check logs anytime with:
```bash
tail -f bot.log
```
Stop it with:
```bash
pkill -f "python bot.py"
```

---

## 7. Keep the Phone Awake

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

## 8. Auto-Start on Reboot (Optional)

If you installed **Termux:Boot**:

```bash
mkdir -p ~/.termux/boot
nano ~/.termux/boot/start-dialed.sh
```

Paste this:
```bash
#!/data/data/com.termux/files/usr/bin/bash
termux-wake-lock
cd ~/Coloral
source venv/bin/activate
nohup bash start.sh > bot.log 2>&1 &
```

Make it executable:
```bash
chmod +x ~/.termux/boot/start-dialed.sh
```

Now the bot will auto-start every time the phone boots.

---

## 9. Pulling Updates Later

```bash
cd ~/Coloral
git pull
# Restart the bot
pkill -f "python bot.py"
nohup bash start.sh > bot.log 2>&1 &
```

---

## Quick Reference

| Task | Command |
|---|---|
| Start bot (foreground) | `bash start.sh` |
| Start bot (background) | `nohup bash start.sh > bot.log 2>&1 &` |
| View live logs | `tail -f bot.log` |
| Stop bot | `pkill -f "python bot.py"` |
| Prevent sleep | `termux-wake-lock` |
| Update code | `git pull` |
