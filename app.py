
# app.py — Safe Telegram Worker Diagnostics
# Render Start Command:
# gunicorn --workers 1 app:app

import os
import re
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

API_ID = os.getenv("API_ID", "").strip()
API_HASH = os.getenv("API_HASH", "").strip()


@app.route("/", methods=["GET"])
def home():
    return "Telegram Worker Diagnostics OK"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "service": "telegram-worker",
        "api_configured": bool(API_ID and API_HASH)
    })


@app.route("/debug", methods=["GET"])
def debug():
    # Never return API hashes, OTPs, passwords, or session strings.
    return jsonify({
        "ok": True,
        "has_api_id": bool(API_ID),
        "has_api_hash": bool(API_HASH)
    })


@app.route("/validate_phone", methods=["POST"])
def validate_phone():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone") or "").strip()

    # E.164-like format check; this does not verify ownership.
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        return jsonify({
            "ok": False,
            "error": "Invalid phone format. Use international format, e.g. +919999999999."
        }), 400

    return jsonify({
        "ok": True,
        "phone_format": "valid"
    })


@app.errorhandler(404)
def not_found(_error):
    return jsonify({
        "ok": False,
        "error": "Endpoint not found"
    }), 404


@app.errorhandler(500)
def internal_error(_error):
    return jsonify({
        "ok": False,
        "error": "Internal server error"
    }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080"))
    )
    
