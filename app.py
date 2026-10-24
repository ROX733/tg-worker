# ULTRA FIX V2 - app.py - paste FULL file
import os, asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError, PhoneNumberInvalidError, FloodWaitError
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)
API_ID = int(os.getenv("API_ID","0") or 0)
API_HASH = os.getenv("API_HASH","")
# Ab hum hash + session dono save karenge
sessions = {} # {phone: {"hash": "...", "session_str": "..."}}

def run(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@app.route("/send_code", methods=["POST"])
def send_code():
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "").strip()
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH
    
    if not api_id or not api_hash:
        return jsonify({"ok":False,"error":"API_ID/HASH not set"})
    
    async def _send():
        # 1. Naya session banao
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        res = await client.send_code_request(phone)
        
        # 2. IMPORTANT FIX: session string + hash dono save karo
        sessions[phone] = {
            "hash": res.phone_code_hash,
            "session_str": client.session.save()
        }
        
        h = res.phone_code_hash
        # disconnect mat karo immediately, ya karo to session save karke karo
        await client.disconnect()
        return h
        
    try:
        h = run(_send())
        return jsonify({"ok":True, "phone_code_hash":h})
    except Exception as e:
        return jsonify({"ok":False,"error":f"send_code: {e}"})

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "").strip()
    code = "".join(c for c in str(data.get("code") or "") if c.isdigit())
    password = data.get("password")
    
    # Bot se aaya hua pch pehle use karo, nahi to memory wala
    mem = sessions.get(phone, {})
    pch = (data.get("phone_code_hash") or mem.get("hash") or "").strip()
    session_str = mem.get("session_str") or ""
    
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH

    if not pch:
        return jsonify({"ok":False,"error":"Missing phone_code_hash - request new OTP"})
    
    async def _verify():
        # FIX: Wahi session use karo jo send_code me banaya tha
        if session_str:
            client = TelegramClient(StringSession(session_str), api_id, api_hash)
        else:
            # fallback - agar memory clear ho gayi to
            client = TelegramClient(StringSession(), api_id, api_hash)
            
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=pch)
        except SessionPasswordNeededError:
            if not password:
                await client.disconnect()
                return {"need_2fa":True}
            await client.sign_in(password=password)
        
        sess = client.session.save()
        me = await client.get_me()
        await client.disconnect()
        # verify ke baad memory clear
        if phone in sessions:
            del sessions[phone]
        return {"ok":True, "session":sess, "user_id":me.id}

    try:
        r = run(_verify())
        if r.get("need_2fa"):
            return jsonify({"ok":False,"need_2fa":True})
        return jsonify(r)
    except PhoneCodeExpiredError:
        return jsonify({"ok":False,"error":"OTP expired - request new OTP, use within 90 sec","expired":True})
    except PhoneCodeInvalidError:
        return jsonify({"ok":False,"error":"Invalid OTP"})
    except Exception as e:
        return jsonify({"ok":False,"error":f"{e} type:{type(e).__name__}"})

@app.route("/")
def home():
    return "TG Worker OK - V2 FIXED"

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
