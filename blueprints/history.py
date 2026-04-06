# blueprints/history.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles scan history:
#   GET /api/history  → return last 10 scans for logged-in user (Redis cached)
# ─────────────────────────────────────────────────────────────────────────────

import json
from flask import Blueprint, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import Scan

history_bp = Blueprint("history", __name__)


@history_bp.route("/api/history", methods=["GET"])
@jwt_required()
def get_history():
    user_id = get_jwt_identity()

    # Unique cache key per user — e.g. "history:42"
    cache_key = f"history:{user_id}"

    # Get Redis client attached to app in app.py
    redis_client = current_app.extensions["redis_client"]

    try:
        # ── Step 1: Check Redis first ─────────────────────────────────────
        # If the data is cached, return it immediately without hitting the DB
        cached = redis_client.get(cache_key)
        if cached:
            print(f"[Cache] HIT for {cache_key}")
            return jsonify(json.loads(cached))

        # ── Step 2: Cache miss — query PostgreSQL/SQLite ──────────────────
        print(f"[Cache] MISS for {cache_key} — querying DB")
        scans = Scan.query.filter_by(
            user_id=int(user_id)
        ).order_by(Scan.timestamp.desc()).limit(10).all()

        result = [{
            "fen": s.fen,
            "image": s.image_data,
            "date": s.timestamp.strftime("%b %d, %H:%M"),
        } for s in scans]

        # ── Step 3: Store in Redis for 60 seconds ─────────────────────────
        redis_client.set(cache_key, json.dumps(result), ex=60)

        return jsonify(result)

    except Exception as e:
        print(f"[Cache] Redis error: {e} — falling back to DB directly")
        # If Redis is down, fall back gracefully — cache must never break the app
        try:
            scans = Scan.query.filter_by(
                user_id=int(user_id)
            ).order_by(Scan.timestamp.desc()).limit(10).all()

            return jsonify([{
                "fen": s.fen,
                "image": s.image_data,
                "date": s.timestamp.strftime("%b %d, %H:%M"),
            } for s in scans])

        except Exception as db_e:
            print(f"[History] DB error: {db_e}")
            return jsonify([])