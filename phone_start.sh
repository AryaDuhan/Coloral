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

# ── Ctrl+C handler ────────────────────────────────────────────────────────
# Without this, Ctrl+C only kills the inner python process and the
# while-true loop immediately restarts it.
KEEP_RUNNING=true
trap 'echo ""; echo "🛑  Caught Ctrl+C — shutting down."; KEEP_RUNNING=false; kill $BOT_PID 2>/dev/null; exit 0' INT TERM

echo "📱 Starting Dialed bot (Phone Mode)..."

while $KEEP_RUNNING; do
    # 7h timeout = safety net in case the bot's 6h self-restart hangs
    timeout 7h python bot.py &
    BOT_PID=$!
    wait $BOT_PID
    EXIT_CODE=$?

    # If we were told to stop (Ctrl+C), don't loop
    if ! $KEEP_RUNNING; then
        break
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
