# TG Account Worker - REAL OTP Sender (Telethon)
# Deploy on Render/Railway/VPS - pip install telethon flask flask-cors

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError
from flask import Flask, request, jsonify
import asyncio, os

app = Flask(__name__)
API_ID = int(os.getenv("API_ID","31724382"))
API_HASH = os.getenv("API_HASH","cdaa5c6f43ec7eccbe7142d25e6e1c67")
# store phone_code_hash per phone
sessions = {}

def run(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()

@app.route("/send_code", methods=["POST"])
def send_code():
    data = request.json
    phone = data.get("phone")
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH
    async def _send():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        res = await client.send_code_request(phone)
        sessions[phone] = res.phone_code_hash
        await client.disconnect()
        return res.phone_code_hash
    try:
        h = run(_send())
        return jsonify({"ok":True, "phone_code_hash":h, "msg":"OTP sent to "+phone})
    except Exception as e:
        return jsonify({"ok":False, "error":str(e)}),400

@app.route("/verify", methods=["POST"])
def verify():
    data = request.json
    phone = data.get("phone")
    code = data.get("code")
    password = data.get("password")
    pch = data.get("phone_code_hash") or sessions.get(phone)
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH
    async def _verify():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=pch)
        except SessionPasswordNeededError:
            if not password:
                return {"need_2fa":True}
            await client.sign_in(password=password)
        # success -> export session
        sess = client.session.save()
        me = await client.get_me()
        await client.disconnect()
        return {"ok":True, "session":sess, "user_id":me.id, "username":getattr(me,"username",""), "phone":phone}
    try:
        r = run(_verify())
        if r.get("need_2fa"):
            return jsonify({"ok":False,"need_2fa":True})
        return jsonify(r)
    except PhoneCodeInvalidError:
        return jsonify({"ok":False,"error":"Invalid OTP"}),400
    except PhoneCodeExpiredError:
        return jsonify({"ok":False,"error":"OTP expired"}),400
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}),400

@app.route("/")
def home():
    return "TG Worker OK"
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
# ENV: API_ID, API_HASH
# Endpoints: POST /send_code {phone,api_id,api_hash} -> sends OTP (core.telegram.org/api/auth)
#            POST /verify {phone,code,password,phone_code_hash,api_id,api_hash} -> returns session string
# Buyer uses session -> NO OTP (via StringSession)
