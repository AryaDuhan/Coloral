#!/data/data/com.termux/files/usr/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# phone_start.sh — Run the Dialed bot inside Termux with a 6-hour auto-restart
# Usage:  bash phone_start.sh          (foreground)
#         nohup bash phone_start.sh &  (background — survives closing Termux)
# ─────────────────────────────────────────────────────────────────────────────

cd "$(dirname "$0")"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "📱 Starting Dialed bot (Phone Mode — 6-hour restart loop)..."

while true; do
    python bot.py
    EXIT_CODE=$?
    
    echo ""
    echo "⚠️  Bot shutdown sequence completed or crashed (code $EXIT_CODE). Restarting in 5 seconds..."
    echo "    (Press Ctrl+C to stop)"
    sleep 5
done
