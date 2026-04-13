#!/bin/bash
# SnapDraw – one-time setup
set -e

echo "🔧 Installing dependencies..."
pip3 install rumps Pillow 2>/dev/null || pip install rumps Pillow

echo ""
echo "✅ Done! To run SnapDraw:"
echo ""
echo "   python3 screenshot_app.py"
echo ""
echo "It will appear as 📷 in your menu bar."
echo ""
echo "💡 To auto-start on login:"
echo "   1. Open System Settings → General → Login Items"
echo "   2. Add this script (wrap it in an Automator app if needed)"