#!/bin/bash
# Hermes Gateway Tunnel - Auto-restart script
# این اسکریپت tunnel رو همیشه زنده نگه میداره

LOG_FILE="/tmp/hermes_tunnel.log"
PID_FILE="/tmp/hermes_tunnel.pid"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG_FILE"
    echo "$1"
}

# توقف tunnel قبلی
stop_tunnel() {
    if [ -f "$PID_FILE" ]; then
        OLD_PID=$(cat "$PID_FILE")
        if kill -0 "$OLD_PID" 2>/dev/null; then
            kill "$OLD_PID" 2>/dev/null
            log "Stopped old tunnel (PID: $OLD_PID)"
        fi
        rm -f "$PID_FILE"
    fi
}

# شروع tunnel
start_tunnel() {
    log "Starting Cloudflare tunnel..."
    cloudflared tunnel --url http://localhost:8000 2>&1 | tee -a "$LOG_FILE" &
    NEW_PID=$!
    echo "$NEW_PID" > "$PID_FILE"
    log "Tunnel started (PID: $NEW_PID)"
    
    # صبر برای دریافت URL
    sleep 5
    
    # استخراج URL از لاگ
    TUNNEL_URL=$(grep -o 'https://[^[:space:]]*trycloudflare.com' "$LOG_FILE" | tail -1)
    
    if [ -n "$TUNNEL_URL" ]; then
        log "✅ Tunnel URL: $TUNNEL_URL"
        echo "$TUNNEL_URL" > /tmp/hermes_tunnel_url.txt
    else
        log "⚠️ Waiting for tunnel URL..."
    fi
}

# بررسی وضعیت
check_tunnel() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Main
case "${1:-start}" in
    start)
        stop_tunnel
        start_tunnel
        log "Tunnel monitor started. Use '$0 status' to check."
        ;;
    stop)
        stop_tunnel
        log "Tunnel stopped."
        ;;
    status)
        if check_tunnel; then
            PID=$(cat "$PID_FILE")
            URL=$(cat /tmp/hermes_tunnel_url.txt 2>/dev/null || echo "Unknown")
            echo "✅ Tunnel is running"
            echo "   PID: $PID"
            echo "   URL: $URL"
        else
            echo "❌ Tunnel is not running"
        fi
        ;;
    restart)
        stop_tunnel
        sleep 1
        start_tunnel
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart}"
        ;;
esac
