# FINAL V4 - Only 3 Status - app.py
import os, asyncio, re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
API_ID = int(os.getenv("API_ID","0") or 0)
API_HASH = os.getenv("API_HASH","")
sessions = {}

def run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

async def check_bots(client):
    year = "2023"
    created_str = "2023-01"
    spam_status = "HEALTHY"
    spam_raw = ""
    
    # 1. TGDNA CHECK
    try:
        await client.send_message('TGDNAbot', '/start')
        await asyncio.sleep(3)
        msgs = await client.get_messages('TGDNAbot', limit=2)
        for m in msgs:
            if not m.text: continue
            match = re.search(r'(\d{4})-(\d{2})', m.text)
            if match:
                year = match.group(1)
                created_str = f"{match.group(1)}-{match.group(2)}"
                break
    except Exception as e:
        print(f"TGDNA Error {e}")

    # 2. SPAM BOT CHECK - ONLY 3 STATUS
    try:
        await client.send_message('SpamBot', '/start')
        await asyncio.sleep(4)
        msgs = await client.get_messages('SpamBot', limit=1)
        if msgs and msgs[0].text:
            spam_raw = msgs[0].text
            low = spam_raw.lower()
            
            if "no limits" in low or "good news" in low or "free" in low:
                spam_status = "HEALTHY"
            elif "permanently" in low or "permanent" in low:
                spam_status = "PERMANENT SPAM"
            else:
                # Agar limit hai toh temporary
                spam_status = "TEMPORARY SPAM"
    except Exception as e:
        print(f"SpamBot Error {e}")
        spam_status = "HEALTHY"

    return year, created_str, spam_status, spam_raw

@app.route("/send_code", methods=["POST"])
def send_code():
    data = request.get_json(force=True) or {}
    phone = data.get("phone","").strip()
    api_id = int(data.get("api_id") or API_ID); api_hash = data.get("api_hash") or API_HASH
    async def _send():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        res = await client.send_code_request(phone)
        sessions[phone] = {"hash": res.phone_code_hash, "session_str": client.session.save()}
        await client.disconnect()
        return res.phone_code_hash
    try:
        h = run(_send())
        return jsonify({"ok":True, "phone_code_hash":h})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)})

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True) or {}
    phone = data.get("phone","").strip(); code = "".join(c for c in str(data.get("code") or "") if c.isdigit())
    password = data.get("password"); pch = (data.get("phone_code_hash") or sessions.get(phone,{}).get("hash") or "").strip()
    sess_str = sessions.get(phone,{}).get("session_str") or ""
    api_id = int(data.get("api_id") or API_ID); api_hash = data.get("api_hash") or API_HASH

    async def _verify():
        client = TelegramClient(StringSession(sess_str) if sess_str else StringSession(), api_id, api_hash)
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=pch)
        except SessionPasswordNeededError:
            if not password: await client.disconnect(); return {"need_2fa":True}
            await client.sign_in(password=password)
        
        year, created, spam_status, spam_raw = await check_bots(client)
        me = await client.get_me()
        final_sess = client.session.save()
        await client.disconnect()
        if phone in sessions: del sessions[phone]
        return {"ok":True, "session":final_sess, "user_id":me.id, "name": me.first_name, "year": year, "created": created, "spam_status": spam_status, "spam_raw": spam_raw}

    try:
        r = run(_verify())
        if r.get("need_2fa"): return jsonify({"ok":False,"need_2fa":True})
        return jsonify(r)
    except Exception as e:
        return jsonify({"ok":False,"error":f"{e}"})

@app.route("/")
def home(): return "WORKER V4 - 3 STATUS ONLY"
