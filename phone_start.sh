#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# phone_start.sh — Run the Dialed bot inside Termux with a 6-hour safety net
# Usage:  bash phone_start.sh          (foreground)
#         nohup bash phone_start.sh &  (background — survives closing Termux)
#
# The bot restarts itself every 6 hours via its lifecycle cog (os.execv).
# The timeout here is a SAFETY NET: if the bot freezes and can't self-restart,
# this script force-kills it after 7 hours and starts fresh.
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "📱 Starting Dialed bot (Phone Mode)..."

while true; do
    # 7h timeout = safety net in case the bot's 6h self-restart hangs
    timeout 7h python bot.py
    EXIT_CODE=$?

    echo ""
    if [ $EXIT_CODE -eq 124 ]; then
        echo "🔒  Bot was unresponsive for 7 hours — force-killed by safety net."
    else
        echo "⚠️  Bot exited (code $EXIT_CODE)."
    fi
    echo "🔄  Restarting in 5 seconds... (Ctrl+C to stop)"
    sleep 5
done
