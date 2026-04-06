# blueprints/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles all authentication routes:
#   POST /signup
#   POST /login
#   POST /logout
#   GET  /api/me
# ─────────────────────────────────────────────────────────────────────────────

from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from models import db, User

# Blueprint name = "auth", no url_prefix — routes stay at /login, /signup etc.
auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/signup", methods=["POST"])
def signup():
    email = request.json.get("email")
    username = request.json.get("username")
    password = request.json.get("password")

    if not email or not username or not password:
        return jsonify({"error": "All fields are required"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username taken"}), 400

    new_user = User(
        email=email,
        username=username,
        password=generate_password_hash(password),
    )
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "Signup successful"})


@auth_bp.route("/login", methods=["POST"])
def login():
    email = request.json.get("email")
    password = request.json.get("password")
    user = User.query.filter_by(email=email).first()
    print(f"Login attempt for {email}: {'Found' if user else 'Not found'}")

    if user and check_password_hash(user.password, password):
        token = create_access_token(identity=str(user.id))
        return jsonify({
            "message": "Login successful",
            "username": user.username,
            "token": token,
        })

    return jsonify({"error": "Invalid credentials"}), 401


@auth_bp.route("/logout", methods=["POST"])
def logout():
    # JWT is stateless — logout is handled client-side by deleting the token.
    # This route exists so the frontend has something to call for completeness.
    return jsonify({"message": "Logged out"})


@auth_bp.route("/api/me", methods=["GET"])
@jwt_required()
def get_me():
    user_id = get_jwt_identity()
    user = db.session.get(User, int(user_id))
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({
        "username": user.username,
        "email": user.email,
    })