#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# phone_start.sh — Run the Dialed bot inside Termux with a 6-hour safety net
# Usage:  bash phone_start.sh          (foreground)
#         nohup bash phone_start.sh &  (background — survives closing Termux)
#
# The bot's lifecycle cog calls sys.exit(0) to restart.
# This loop catches the exit and boots the bot back up.
# The timeout is a SAFETY NET: if the bot freezes, this script
# force-kills it after 7 hours and starts fresh.
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Ctrl+C exits the entire script cleanly
trap 'echo ""; echo "🛑  Caught Ctrl+C — shutting down."; exit 0' INT TERM

echo "📱 Starting Dialed bot (Phone Mode)..."

while true; do
    # 7h timeout = safety net in case the bot freezes
    timeout 7h python bot.py
    EXIT_CODE=$?

    # Exit code 130 = Ctrl+C was pressed (SIGINT), so stop looping
    if [ $EXIT_CODE -eq 130 ]; then
        echo "🛑  Stopped."
        exit 0
    fi

    echo ""
    if [ $EXIT_CODE -eq 124 ]; then
        echo "🔒  Bot was unresponsive for 7 hours — force-killed by safety net."
    else
        echo "⚠️  Bot exited (code $EXIT_CODE)."
    fi
    echo "🔄  Restarting in 5 seconds... (Ctrl+C to stop)"
    sleep 5
done
