import os
import subprocess
import psutil
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="HERMES Cyber Gateway", version="4.0")

# 🔓 فعال‌سازی CORS برای ارتباط زنده مینی‌اپ گیت‌هاب
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = os.path.expanduser("~/.hermes/chat_history.json")

def load_chats():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return [
        {"id": 1, "sender": "hermes", "text": "سیستم هرمس آماده به کار است.", "time": "12:00"},
        {"id": 2, "sender": "user", "text": "وضعیت سیستم چطوره؟", "time": "12:01"}
    ]

def save_chats(chats):
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(chats, f, ensure_ascii=False, indent=2)

# مدل‌های ورودی
class CronModel(BaseModel):
    name: str
    description: str
    schedule: str
    command: str

class ChatMessage(BaseModel):
    sender: str
    text: str

# 📊 1. دریافت زنده وضعیت منابع و آمار
@app.get("/api/v1/stats")
async def get_stats():
    return {
        "cpu": psutil.cpu_percent(interval=0.2),
        "ram": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "updated_at": datetime.now().strftime("%H:%M:%S")
    }

# ⚡ 2. دریافت لیست دقیق و زنده کرون‌جاب‌ها
@app.get("/api/v1/cron/list")
async def list_crons():
    raw_cron = subprocess.getoutput("crontab -l")
    if "no crontab for" in raw_cron:
        return {"crons": []}

    cron_list = []
    lines = raw_cron.split('\n')
    for line in lines:
        line = line.strip()
        if line and "# HERMES:" in line:
            is_disabled = line.startswith("#DISABLED#")
            clean_line = line.replace("#DISABLED#", "").strip()
            parts = clean_line.split("# HERMES:")
            cron_expr = parts[0].strip()
            metadata = parts[1].split("|") if "|" in parts[1] else [parts[1], "بدون توضیح"]

            cron_list.append({
                "name": metadata[0].strip(),
                "description": metadata[1].strip() if len(metadata) > 1 else "بدون توضیح",
                "schedule": cron_expr,
                "status": "disabled" if is_disabled else "active",
                "raw": line
            })
    return {"crons": cron_list}

# ➕ 3. افزودن آنی کرون‌جاب جدید
@app.post("/api/v1/cron/add")
async def add_cron(data: CronModel):
    try:
        raw_cron = subprocess.getoutput("crontab -l")
        if "no crontab for" in raw_cron:
            raw_cron = ""

        entry = f"{data.schedule} python3 ~/.hermes/scripts/runner.py '{data.name}' # HERMES:{data.name}|{data.description}\n"
        new_cron = raw_cron.rstrip() + "\n" + entry

        proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        proc.communicate(input=new_cron)
        return {"status": "success", "message": f"کرون جاب {data.name} با موفقیت فعال شد."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🛑 4. تغییر وضعیت (فعال/توقف) یا حذف کرون‌جاب
@app.post("/api/v1/cron/toggle")
async def toggle_cron(payload: dict):
    name = payload.get("name")
    action = payload.get("action")

    raw_cron = subprocess.getoutput("crontab -l")
    if "no crontab for" in raw_cron:
        return {"status": "error", "message": "هیچ کرون‌جابی وجود ندارد."}

    lines = raw_cron.split('\n')
    new_lines = []
    for line in lines:
        if f"# HERMES:{name}" in line:
            if action == "delete":
                continue
            elif action == "toggle":
                if line.startswith("#DISABLED#"):
                    line = line.replace("#DISABLED#", "").strip()
                else:
                    line = "#DISABLED# " + line
        new_lines.append(line)

    proc = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
    proc.communicate(input="\n".join(new_lines))
    return {"status": "success"}

# 💬 5. مدیریت چت‌ها (دریافت، ارسال و پاک‌سازی)
@app.get("/api/v1/chat/messages")
async def get_messages():
    return {"messages": load_chats()}

@app.post("/api/v1/chat/send")
async def send_message(msg: ChatMessage):
    chats = load_chats()
    new_msg = {
        "id": len(chats) + 1,
        "sender": msg.sender,
        "text": msg.text,
        "time": datetime.now().strftime("%H:%M")
    }
    chats.append(new_msg)
    save_chats(chats)
    return {"status": "success", "data": new_msg}

@app.post("/api/v1/chat/clear")
async def clear_chats():
    save_chats([])
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
