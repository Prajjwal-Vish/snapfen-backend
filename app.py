# app code with flask blueprints for better organization

import os
import ssl
import json
import redis
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()

from flask import Flask
from flask_cors import CORS
# from flask_limiter import Limiter
# from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager
from models import db
from extensions import limiter

# ── App factory ───────────────────────────────────────────────────────────────
app = Flask(__name__)

# ── Secret key (crash on missing — never silently fall back) ──────────────────
secret = os.environ.get("SECRET_KEY")
if not secret:
    raise RuntimeError("SECRET_KEY environment variable not set!")

# ── Config ────────────────────────────────────────────────────────────────────
IS_PRODUCTION = os.environ.get("FLASK_ENV") == "production"
print(f">>> FLASK_ENV      = {os.environ.get('FLASK_ENV')}")
print(f">>> IS_PRODUCTION  = {IS_PRODUCTION}")

app.config["SECRET_KEY"] = secret
app.config["JWT_SECRET_KEY"] = secret
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "None" if IS_PRODUCTION else "Lax"
app.config["SESSION_COOKIE_SECURE"] = IS_PRODUCTION

app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload limit

# ── Database ──────────────────────────────────────────────────────────────────
database_url = os.environ.get("DATABASE_URL", "sqlite:///chessvision.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = (
    {"pool_pre_ping": True, "connect_args": {"sslmode": "require"}}
    if database_url.startswith("postgresql")
    else {"pool_pre_ping": True}
)

# ── Extensions ────────────────────────────────────────────────────────────────
db.init_app(app)
jwt = JWTManager(app)
limiter.init_app(app)

# ── Redis client (shared across blueprints via app.extensions) ────────────────
# We attach the redis client to app.extensions so blueprints can access it
# without a circular import. Blueprints import 'current_app' and do
# current_app.extensions["redis_client"] to get it.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
ssl_kwargs = {"ssl_cert_reqs": None} if REDIS_URL.startswith("rediss://") else {}
redis_client = redis.from_url(REDIS_URL, decode_responses=True, **ssl_kwargs)
app.extensions["redis_client"] = redis_client

# ── CORS ──────────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://your-snapfen-frontend.netlify.app",
    "https://snapfen-frontend.onrender.com",
    "https://snapfen.vercel.app",
    "https://snapfen-git-main-prajwal-vishwakarmas-projects.vercel.app",
    "https://snapfen-mljn3kv7b-prajwal-vishwakarmas-projects.vercel.app",
]
CORS(app, 
     resources={r"/*": {
         "origins": ALLOWED_ORIGINS,
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization"],
         "supports_credentials": True,
         "max_age": 3600
     }})

# ── Register blueprints ───────────────────────────────────────────────────────
# Each blueprint is a separate file in the blueprints/ folder.
# url_prefix means all routes in that blueprint are prefixed.
# e.g. auth blueprint's /login becomes /login (no prefix needed here)
from blueprints.auth import auth_bp
from blueprints.scan import scan_bp
from blueprints.history import history_bp
from blueprints.report import report_bp

app.register_blueprint(auth_bp)
app.register_blueprint(scan_bp)
app.register_blueprint(history_bp)
app.register_blueprint(report_bp)

# ── Health check route ────────────────────────────────────────────────────────
from flask import jsonify

@app.route("/")
def health():
    return jsonify({"status": "SnapFen backend running"})

# ── Create DB tables on first run ─────────────────────────────────────────────
with app.app_context():
    db.create_all()

# ── Dev server ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)