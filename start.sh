#!/bin/bash
# Hermes Gateway - Startup Script
# هم بک‌اند و هم tunnel رو همزمان اجرا میکنه

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="/tmp/hermes_logs"
mkdir -p "$LOG_DIR"

echo "🚀 Hermes Gateway Starting..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ۱. اجرای بک‌اند API
echo "📡 Starting API server on port 8000..."
cd "$SCRIPT_DIR"
python3 gateway_api.py > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
echo "   API PID: $API_PID"

# صبر برای آماده شدن API
sleep 2

# بررسی وضعیت API
if curl -s http://localhost:8000/api/v1/system/stats > /dev/null 2>&1; then
    echo "   ✅ API is running"
else
    echo "   ⚠️ API might still be starting..."
fi

# ۲. اجرای Cloudflare Tunnel
echo "🔗 Starting Cloudflare tunnel..."
cloudflared tunnel --url http://localhost:8000 > "$LOG_DIR/tunnel.log" 2>&1 &
TUNNEL_PID=$!
echo "   Tunnel PID: $TUNNEL_PID"

# صبر برای دریافت URL
echo "   Waiting for tunnel URL..."
sleep 6

# استخراج URL
TUNNEL_URL=$(grep -o 'https://[^[:space:]]*trycloudflare.com' "$LOG_DIR/tunnel.log" | tail -1)

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Hermes Gateway is ready!"
echo ""
echo "📡 API:        http://localhost:8000"
if [ -n "$TUNNEL_URL" ]; then
    echo "🌐 Tunnel:     $TUNNEL_URL"
    echo "$TUNNEL_URL" > /tmp/hermes_tunnel_url.txt
else
    echo "🌐 Tunnel:     Starting... (check: cat $LOG_DIR/tunnel.log)"
fi
echo ""
echo "📊 Mini App:   https://saturn43210.github.io/hermes-miniapp-v5/"
echo ""
echo "To stop: kill $API_PID $TUNNEL_PID"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ذخیره PIDs
echo "$API_PID" > /tmp/hermes_api.pid
echo "$TUNNEL_PID" > /tmp/hermes_tunnel.pid

# نگه داشتن script
wait
