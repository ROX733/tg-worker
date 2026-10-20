# app.py
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
    return "TG Worker OK"


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "ok": True,
        "service": "tg-worker",
        "api_configured": bool(API_ID and API_HASH)
    })


@app.route("/debug", methods=["GET"])
def debug():
    # Do not expose credentials or session data.
    return jsonify({
        "ok": True,
        "has_api_id": bool(API_ID),
        "has_api_hash": bool(API_HASH)
    })


@app.route("/send_code", methods=["POST"])
def send_code():
    data = request.get_json(silent=True) or {}
    phone = str(data.get("phone") or "").strip()

    # Validate international phone-number formatting.
    if not re.fullmatch(r"\+[1-9][0-9]{7,14}", phone):
        return jsonify({
            "ok": False,
            "error": "Invalid phone format. Use international format, e.g. +919999999999."
        }), 400

    if not API_ID or not API_HASH:
        return jsonify({
            "ok": False,
            "error": "API_ID/API_HASH are not configured on Render."
        }), 503

    # This diagnostic endpoint intentionally does not send an OTP.
    return jsonify({
        "ok": False,
        "error": "OTP sending is not enabled in this diagnostic worker."
    }), 501


@app.route("/verify", methods=["POST"])
def verify():
    return jsonify({
        "ok": False,
        "error": "OTP verification is not enabled in this diagnostic worker."
    }), 501


@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "ok": False,
        "error": "Unknown endpoint"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    app.logger.exception("Internal server error")
    return jsonify({
        "ok": False,
        "error": "Internal server error"
    }), 500


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080"))
    )
