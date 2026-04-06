"""
config.py — Bot-wide settings. Edit these or override via environment variables.
"""

import os

# ── Score Listener ────────────────────────────────────────────────────────────

# Set to a specific channel ID (int) to restrict score detection to one channel.
# Leave as None to allow ALL channels the bot can read.
SCORE_CHANNEL_ID: int | None = None  # e.g. 1234567890

# Reaction emoji posted when a score is successfully recorded
CONFIRM_EMOJI = "🎨"

# ── Daily Reminder ────────────────────────────────────────────────────────────

# Channel where the daily reminder is posted (REQUIRED for reminders to work)
REMINDER_CHANNEL_ID: int | None = int(os.getenv("REMINDER_CHANNEL_ID", "0")) or None

# 24-hour UTC time for the daily reminder
# Default: 18:30 UTC = 12:00 AM IST (midnight Indian time)
REMINDER_HOUR   = int(os.getenv("REMINDER_HOUR",   "18"))
REMINDER_MINUTE = int(os.getenv("REMINDER_MINUTE", "30"))

# ── Graph ─────────────────────────────────────────────────────────────────────

GRAPH_DAYS = 14          # How many recent scores to plot

# ── Colours (hex) ─────────────────────────────────────────────────────────────

COLOR_PRIMARY   = 0xE96479   # Embed accent — warm pink (dialed.gg palette)
COLOR_SUCCESS   = 0x6BCB77   # Green — successful submission
COLOR_WARNING   = 0xFFD166   # Yellow — warnings / duplicates
COLOR_ERROR     = 0xEF233C   # Red — errors
