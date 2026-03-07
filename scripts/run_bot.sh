#!/bin/bash
set -e

echo "Clearing __pycache__..."
find discord_bot -type d -name __pycache__ -exec rm -rf {} +

echo "Waiting 3 seconds..."
sleep 3

echo "Starting bot..."
python discord_bot/bot.py
