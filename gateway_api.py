import os
import subprocess
import psutil
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Hermes Gateway API", version="3.5")

# 🔓 CORS — اجازه دسترسی به مینی‌اپ
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Models ────────────────────────────────────────────────────────
class ScriptPayload(BaseModel):
    filename: str
    code: str

class CronPayload(BaseModel):
    name: str
    schedule: str
    command: str

# ── 1. آمار و منابع سیستم ────────────────────────────────────────
@app.get("/api/v1/system/stats")
async def get_system_stats():
    return {
        "status": "online",
        "cpu_percent": psutil.cpu_percent(interval=0.5),
        "ram_percent": psutil.virtual_memory().percent,
        "ram_used_gb": round(psutil.virtual_memory().used / (1024**3), 1),
        "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 1),
        "disk_percent": psutil.disk_usage('/').percent,
        "disk_used_gb": round(psutil.disk_usage('/').used / (1024**3), 1),
        "disk_total_gb": round(psutil.disk_usage('/').total / (1024**3), 1),
        "uptime": subprocess.getoutput("uptime -p"),
        "load_avg": list(os.getloadavg()) if hasattr(os, 'getloadavg') else [0, 0, 0],
    }

# ── 2. لاگ‌های Gateway ───────────────────────────────────────────
@app.get("/api/v1/system/logs")
async def get_system_logs(lines: int = 30):
    log_file = os.path.expanduser("~/.hermes/logs/gateway.log")
    if os.path.exists(log_file):
        output = subprocess.getoutput(f"tail -n {lines} {log_file}")
        return {"logs": output.split('\n')}
    return {"logs": ["⚠️ فایل لاگ یافت نشد."]}

# ── 3. اجرای اسکریپت پایتون ─────────────────────────────────────
@app.post("/api/v1/script/deploy")
async def deploy_script(payload: ScriptPayload):
    try:
        # محدودیت امنیتی: فقط فایل‌های .py
        if not payload.filename.endswith('.py'):
            raise HTTPException(status_code=400, detail="فقط فایل‌های .py مجاز هستند.")
        
        scripts_dir = os.path.expanduser("~/.hermes/scripts")
        os.makedirs(scripts_dir, exist_ok=True)
        file_path = os.path.join(scripts_dir, payload.filename)
        
        # ذخیره فایل
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(payload.code)
            
        # اجرای آزمایشی (timeout 15 ثانیه)
        result = subprocess.run(
            ["python3", file_path],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=scripts_dir
        )
        
        output = result.stdout if result.returncode == 0 else f"ERROR:\n{result.stderr}"
        return {
            "status": "success" if result.returncode == 0 else "error",
            "file": payload.filename,
            "output": output[:2000],  # محدود کردن خروجی
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="اسکریپت بیش از ۱۵ ثانیه طول کشید.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 4. ثبت کرون‌جاب ──────────────────────────────────────────────
@app.post("/api/v1/cron/create")
async def create_cron(payload: CronPayload):
    try:
        cron_line = f"{payload.schedule} {payload.command} # HERMES:{payload.name}\n"
        current_cron = subprocess.getoutput("crontab -l 2>/dev/null")
        if "no crontab for" in current_cron:
            current_cron = ""
            
        new_cron = current_cron.rstrip() + "\n" + cron_line
        
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_cron)
        
        return {"status": "success", "message": f"جاب '{payload.name}' ثبت شد."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ── 5. لیست کرون‌جاب‌ها ──────────────────────────────────────────
@app.get("/api/v1/cron/list")
async def list_crons():
    try:
        output = subprocess.getoutput("crontab -l 2>/dev/null")
        lines = [l.strip() for l in output.split('\n') if l.strip() and not l.startswith('#')]
        hermes_jobs = [l for l in lines if '# HERMES:' in l]
        return {"jobs": hermes_jobs, "total": len(hermes_jobs)}
    except:
        return {"jobs": [], "total": 0}

# ── 6. وضعیت کلی هرمس ───────────────────────────────────────────
@app.get("/api/v1/hermes/status")
async def hermes_status():
    try:
        # بررسی وضعیت gateway
        result = subprocess.run(["pidof", "hermes"], capture_output=True, text=True)
        if result.returncode != 0:
            result = subprocess.run(["bash", "-c", "ps aux | grep 'hermes gateway' | grep -v grep | awk '{print $2}'"], capture_output=True, text=True)
        gateway_running = result.returncode == 0 and bool(result.stdout.strip())
        
        # بررسی config
        config_path = os.path.expanduser("~/.hermes/config.yaml")
        config_exists = os.path.exists(config_path)
        
        return {
            "gateway_running": gateway_running,
            "config_exists": config_exists,
            "hermes_home": os.path.expanduser("~/.hermes"),
            "status": "healthy" if gateway_running else "down"
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    import uvicorn
    print("🚀 Hermes Gateway API starting on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
