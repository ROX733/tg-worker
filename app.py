# FINAL V6 - FULL CODE - ZG OTP BOT CLONE
# Features: Add Account + Buy Account + Get OTP Again + Manage Devices Inline + Terminate + Logout
# Deploy: gunicorn --workers 1 --threads 4 --timeout 180 app:app

import os
import asyncio
import re
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "")

# In-memory store - DO NOT use >1 worker on Render
sessions = {}

def run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

async def check_bots(client):
    year = "2023"
    created_str = "2023-01"
    spam_status = "HEALTHY"
    spam_raw = ""
    # 1. Check TGDNAbot for creation date
    try:
        await client.send_message('TGDNAbot', '/start')
        await asyncio.sleep(3)
        msgs = await client.get_messages('TGDNAbot', limit=3)
        for m in msgs:
            if not m.text:
                continue
            match = re.search(r'(\d{4})-(\d{2})', m.text)
            if match:
                year = match.group(1)
                created_str = f"{match.group(1)}-{match.group(2)}"
                break
    except Exception as e:
        print(f"TGDNA check fail: {e}")
    
    # 2. Check SpamBot
    try:
        await client.send_message('SpamBot', '/start')
        await asyncio.sleep(4)
        msgs = await client.get_messages('SpamBot', limit=1)
        if msgs and msgs[0].text:
            spam_raw = msgs[0].text
            low = spam_raw.lower()
            if "no limits" in low or "good news" in low or "free" in low or "no restrictions" in low:
                spam_status = "HEALTHY"
            elif "permanently" in low or "permanent" in low:
                spam_status = "PERMANENT SPAM"
            elif "limited" in low or "until" in low:
                spam_status = "TEMPORARY SPAM"
            else:
                spam_status = "HEALTHY"
    except Exception as e:
        print(f"SpamBot check fail: {e}")
        spam_raw = str(e)
        
    return year, created_str, spam_status, spam_raw

# ========== ACCOUNT ADD FLOW ==========

@app.route("/send_code", methods=["POST"])
def send_code():
    data = request.get_json(force=True) or {}
    phone = data.get("phone", "").strip()
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    if not phone or not api_id or not api_hash:
        return jsonify({"ok": False, "error": "Missing phone/api_id/api_hash"})

    async def _send():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        res = await client.send_code_request(phone)
        sessions[phone] = {"hash": res.phone_code_hash, "session_str": client.session.save()}
        await client.disconnect()
        return res.phone_code_hash

    try:
        h = run(_send())
        return jsonify({"ok": True, "phone_code_hash": h})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True) or {}
    phone = data.get("phone", "").strip()
    code = "".join(c for c in str(data.get("code") or "") if c.isdigit())
    password = data.get("password")
    pch = (data.get("phone_code_hash") or sessions.get(phone, {}).get("hash") or "").strip()
    sess_str = sessions.get(phone, {}).get("session_str") or ""
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    if not phone or not code:
        return jsonify({"ok": False, "error": "Missing phone/code"})

    async def _verify():
        client = TelegramClient(StringSession(sess_str) if sess_str else StringSession(), api_id, api_hash)
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=pch)
        except SessionPasswordNeededError:
            if not password:
                await client.disconnect()
                return {"need_2fa": True}
            await client.sign_in(password=password)
        
        year, created, spam_status, spam_raw = await check_bots(client)
        me = await client.get_me()
        final_sess = client.session.save()
        await client.disconnect()
        if phone in sessions:
            del sessions[phone]
        return {
            "ok": True,
            "session": final_sess,
            "user_id": me.id,
            "name": me.first_name,
            "year": year,
            "created": created,
            "spam_status": spam_status,
            "spam_raw": spam_raw
        }

    try:
        r = run(_verify())
        if r.get("need_2fa"):
            return jsonify({"ok": False, "need_2fa": True})
        return jsonify(r)
    except Exception as e:
        return jsonify({"ok": False, "error": f"{e}"})

# ========== ACCOUNT BUY FLOW - OTP WALA BOT ==========

@app.route("/get_otp", methods=["POST"])
def get_otp():
    data = request.get_json(force=True) or {}
    sess = data.get("session", "")
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    async def _get():
        client = TelegramClient(StringSession(sess), api_id, api_hash)
        await client.connect()
        msgs = await client.get_messages(777000, limit=3)
        code = "No OTP yet - Wait 1 min"
        for m in msgs:
            if m.text:
                match = re.search(r'(\d{5})', m.text)
                if match:
                    code = match.group(1)
                    break
        await client.disconnect()
        return code

    try:
        otp = run(_get())
        return jsonify({"ok": True, "otp": otp})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/manage_devices", methods=["POST"])
def manage_devices():
    data = request.get_json(force=True) or {}
    sess = data.get("session", "")
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    async def _get():
        from telethon.tl.functions.account import GetAuthorizationsRequest
        client = TelegramClient(StringSession(sess), api_id, api_hash)
        await client.connect()
        auths = await client(GetAuthorizationsRequest())
        await client.disconnect()
        devices = []
        for a in auths.authorizations:
            devices.append({
                "hash": a.hash,
                "device": f"{a.device_model} - {a.platform}",
                "country": a.country,
                "ip": a.ip,
                "current": bool(a.current),
                "date": str(a.date_created)[:19],
                "region": a.region
            })
        return devices

    try:
        devs = run(_get())
        return jsonify({"ok": True, "devices": devs})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/terminate_session", methods=["POST"])
def terminate_session():
    data = request.get_json(force=True) or {}
    sess = data.get("session", "")
    target_hash = int(data.get("hash") or 0)
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    async def _term():
        from telethon.tl.functions.account import ResetAuthorizationRequest
        client = TelegramClient(StringSession(sess), api_id, api_hash)
        await client.connect()
        await client(ResetAuthorizationRequest(hash=target_hash))
        await client.disconnect()
        return True

    try:
        run(_term())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/finish_logout", methods=["POST"])
def finish_logout():
    data = request.get_json(force=True) or {}
    sess = data.get("session", "")
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    async def _logout():
        client = TelegramClient(StringSession(sess), api_id, api_hash)
        await client.connect()
        await client.log_out()
        await client.disconnect()
        return True

    try:
        run(_logout())
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@app.route("/")
def home():
    return "WORKER V6 - FINAL - ADD + BUY + MANAGE DEVICES INLINE"
