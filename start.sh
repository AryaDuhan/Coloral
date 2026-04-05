#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# start.sh — Run the Dialed bot inside Termux with auto-restart on crash.
# Usage:  bash start.sh          (foreground)
#         nohup bash start.sh &  (background — survives closing Termux)
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "🎨  Starting Dialed bot..."

while true; do
    python bot.py
    EXIT_CODE=$?
    echo ""
    echo "⚠️  Bot exited with code $EXIT_CODE — restarting in 5 seconds..."
    echo "    (Press Ctrl+C to stop)"
    sleep 5
done
