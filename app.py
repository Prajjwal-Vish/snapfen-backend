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
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_jwt_extended import JWTManager

from models import db

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
CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)

# ── Rate limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
)

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













# App code without blueprints


# import redis 
# import json
# import numpy as np
# import cv2
# from flask import Flask, request, jsonify, redirect, url_for
# from pathlib import Path
# import base64 
# import os
# from dotenv import load_dotenv

# # --- SMART IMPORT BLOCK ---
# try:
#     import tflite_runtime.interpreter as tflite
#     print("--- Using TFLite Runtime (Lightweight) ---")
# except ImportError:
#     try:
#         import tensorflow.lite as tflite
#         print("--- Using Full TensorFlow Lite (Local Fallback) ---")
#     except ImportError:
#         print("CRITICAL ERROR: 'tflite_runtime' not found.")

# load_dotenv()

# # --- IMPORTS ---

# from flask_sqlalchemy import SQLAlchemy
# from flask_cors import CORS
# from flask_limiter import Limiter
# from tasks import celery_app, run_inference, send_email_task
# from celery.result import AsyncResult
# from flask_limiter.util import get_remote_address
# from werkzeug.security import generate_password_hash, check_password_hash
# from models import db, User, Scan 
# from flask_jwt_extended import (
#     JWTManager,           # the extension itself — manages everything
#     create_access_token,  # function that creates a token
#     jwt_required,         # decorator that protects a route
#     get_jwt_identity,     # function that reads user ID from token
#     verify_jwt_in_request # checks for token but doesn't crash if missing
# )
# from datetime import timedelta 

# # In app.py, after: from tasks import celery_app, run_inference
# import ssl

# REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
# if REDIS_URL.startswith("rediss://"):
#     ssl_config = {"ssl_cert_reqs": ssl.CERT_NONE}
#     celery_app.conf.update(
#         broker_use_ssl=ssl_config,
#         redis_backend_use_ssl=ssl_config,
#     )
# redis_client = redis.from_url(
#     REDIS_URL,
#     ssl_cert_reqs=None,  # needed for Upstash rediss:// URLs
#     decode_responses=True  # returns strings instead of bytes
# )

# try:
#     from email_sending import send_report_email
# except ImportError:
#     print("WARNING: email_sending.py not found.")

# try:
#     from chessboard_snipper import process_image
#     from flip_board_to_black_pov import assemble_fen_from_predictions, black_perspective_fen
# except ImportError:
#     print("CRITICAL: Missing helper modules")


# app = Flask(__name__)

# # CONFIG

# secret = os.environ.get('SECRET_KEY')
# if not secret:
#     raise RuntimeError("SECRET_KEY environment variable not set!")

# app.config['SECRET_KEY'] = secret

# IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'
# print(f">>> FLASK_ENV = {os.environ.get('FLASK_ENV')}")
# print(f">>> IS_PRODUCTION = {IS_PRODUCTION}")
# print(f">>> SESSION_COOKIE_SECURE = {IS_PRODUCTION}")

# app.config['SESSION_COOKIE_HTTPONLY'] = True
# app.config['SESSION_COOKIE_SAMESITE'] = "None" if IS_PRODUCTION else "Lax"
# app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

# database_url = os.environ.get('DATABASE_URL', 'sqlite:///chessvision.db')
# if database_url.startswith("postgres://"):
#     database_url = database_url.replace("postgres://", "postgresql://", 1)

# app.config['SQLALCHEMY_DATABASE_URI'] = database_url
# app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# if database_url.startswith("postgresql"):
#     app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
#         "pool_pre_ping": True,
#         "connect_args": {"sslmode": "require"}
#     }
# else:
#     app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
#         "pool_pre_ping": True
#     }

# app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

# app.config['JWT_SECRET_KEY'] = os.environ.get('SECRET_KEY')
# # Same secret key you already have — JWT uses it to sign tokens
# # If someone doesn't know this key, they can't fake a token

# app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=7)

# jwt = JWTManager(app) # activating the JWT extension on Flask app

# # CORS AND LIMITER
# ALLOWED_ORIGINS = [
#     "http://localhost:5500",
#     "http://127.0.0.1:5500",
#     "http://localhost:3000",
#     "http://127.0.0.1:3000",
#     "https://your-snapfen-frontend.netlify.app",
#     "https://snapfen-frontend.onrender.com",
# ]

# CORS(app,
#      origins=ALLOWED_ORIGINS,
#      supports_credentials=True)

# limiter = Limiter(
#     app=app,
#     key_func=get_remote_address,
#     default_limits=["200 per day", "50 per hour"]
# )

# # --- PATHS ---
# BASE_DIR = Path(__file__).resolve().parent
# MODEL_PATH = BASE_DIR / "Fine_tuned_CNN_Model" / "chess_model_v5.tflite"
# LABELS_PATH = BASE_DIR / "labels" / "class_names.txt"

# # --- INIT ---
# db.init_app(app) 

# # --- HELPER FUNCTIONS ---

# # 1. Manual Slicer (Bypasses auto-detection)
# def manual_slice(img):
#     # Resize to standard 512x512 to ensure clean 64x64 slices
#     img_resized = cv2.resize(img, (512, 512))
#     squares = []
#     dy, dx = 64, 64 # 512 / 8
    
#     for row in range(8):
#         for col in range(8):
#             y1 = row * dy
#             y2 = (row + 1) * dy
#             x1 = col * dx
#             x2 = (col + 1) * dx
#             squares.append(img_resized[y1:y2, x1:x2])
            
#     # Return (squares_batch, visualized_image, unused)
#     return np.array(squares), img_resized, None

# # --- ROUTES ---

# @app.route('/')
# def health():
#     return jsonify({"status": "SnapFEN backend running"})

# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'bmp'}

# def allowed_file(filename):
#     return '.' in filename and \
#            filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# @app.route('/api/me', methods=['GET'])
# @jwt_required()
# def get_me():
#     user_id = get_jwt_identity()       # get ID from token
#     user = db.session.get(User, int(user_id))  # find user in DB
#     return jsonify({
#         "username": user.username,
#         "email": user.email
#     })

# @app.route("/predict", methods=["POST"])
# @limiter.limit("15 per minute")
# def predict():
#     """
#     Accepts an image upload, enqueues an ML inference task,
#     and immediately returns a task_id.
 
#     The client polls GET /result/<task_id> to check progress.
#     Flask is free to serve other requests while the worker runs inference.
#     """
#     if "file" not in request.files:
#         return jsonify({"error": "No file uploaded"}), 400
 
#     file = request.files["file"]
#     if not file.filename or not allowed_file(file.filename):
#         return jsonify({"error": "Invalid file type. Use PNG, JPG, or WEBP."}), 400
 
#     pov = request.form.get("pov", "w")
#     is_manual = request.form.get("is_manual") == "true"
#     img_bytes = file.read()
 
#     # Figure out user_id for scan saving (same JWT logic as before)
#     user_id = None
#     try:
#         verify_jwt_in_request(optional=True)
#         uid = get_jwt_identity()
#         user_id = int(uid) if uid else None
#     except Exception:
#         pass
 
#     # .delay() is the magic: instead of CALLING run_inference(...),
#     # it ENQUEUES it. Returns immediately with an AsyncResult object.
#     # task.id is the ticket number we give to the client.
#     task = run_inference.delay(
#     img_b64=base64.b64encode(img_bytes).decode("utf-8"),  # ← safe string
#     pov=pov,
#     is_manual=is_manual,
#     user_id=user_id,
# )
 
#     # Return ticket number instantly — no waiting for ML inference
#     return jsonify({"task_id": task.id}), 202
#     # 202 = "Accepted" — standard HTTP code meaning
#     # "I got your request and I'm working on it, check back later"

# @app.route("/result/<task_id>", methods=["GET"])
# def get_result(task_id: str):
#     try:
#         result = AsyncResult(task_id, app=celery_app)
        
#         if result.state == "PENDING":
#             return jsonify({"status": "pending"})
#         if result.state == "STARTED":
#             return jsonify({"status": "started"})
#         if result.state == "SUCCESS":
#             data = result.result
#             if "error" in data:
#                 return jsonify({"status": "error", "error": data["error"]}), 400
#             return jsonify({
#                 "status": "done",
#                 "fen": data["fen"],
#                 "cropped_image": data["cropped_image"],
#             })
#         if result.state == "FAILURE":
#             return jsonify({"status": "error", "error": "Inference failed after retries. Please try again."}), 500

#         return jsonify({"status": "pending"})

#     except Exception as e:
#         print(f"[get_result ERROR] {e}")  # ← this will print the real error in Flask terminal
#         return jsonify({"status": "error", "error": str(e)}), 500

# @app.route('/report_issue', methods=['POST'])
# def report_issue():
#     tags = request.form.get('tags', 'General')
#     text = request.form.get('feedback', '')
#     fen = request.form.get('fen', 'N/A')

#     orig = request.files.get('original_image')
#     crop = request.files.get('cropped_image')
#     bug_file = request.files.get('attachment')

#     # Base64-encode bytes before sending to Celery
#     # Same reason as ML task — JSON can't serialize raw bytes
#     orig_b64 = base64.b64encode(orig.read()).decode() if orig else None
#     crop_b64 = base64.b64encode(crop.read()).decode() if crop else None
#     attach_b64 = base64.b64encode(bug_file.read()).decode() if bug_file else None

#     # .delay() enqueues the task — returns instantly
#     # No more blocking the HTTP thread waiting for Brevo API
#     send_email_task.delay(
#         text=text,
#         tags=tags,
#         fen=fen,
#         orig_b64=orig_b64,
#         crop_b64=crop_b64,
#         attach_b64=attach_b64,
#     )

#     return jsonify({"status": "success"})

# # --- AUTH & HISTORY ---
# @app.route('/signup', methods=['POST'])
# def signup():
#     email = request.json.get('email')
#     username = request.json.get('username')
#     password = request.json.get('password')

#     if User.query.filter_by(email=email).first():
#         return jsonify({"error": "Email already registered"}), 400
#     if User.query.filter_by(username=username).first():
#         return jsonify({"error": "Username taken"}), 400

#     new_user = User(
#         email=email,
#         username=username,
#         password=generate_password_hash(password)
#     )
#     db.session.add(new_user)
#     db.session.commit()
#     return jsonify({"message": "Signup successful"})

# @app.route('/login', methods=['POST'])
# def login():
#     email = request.json.get('email')
#     password = request.json.get('password')
#     user = User.query.filter_by(email=email).first()
#     print(f"Login attempt for {email}: {'Found user' if user else 'No user'}") # adding print for debugging

#     if user and check_password_hash(user.password, password):
#         token = create_access_token(identity=str(user.id))
        
#         return jsonify({
#             "message": "Login successful",
#             "username": user.username,
#             "token": token        # send token to frontend — frontend will save it
#         })

#     return jsonify({"error": "Invalid credentials"}), 401

# @app.route('/logout', methods=['POST'])
# def logout():
#     return jsonify({"message": "Logged out"})

# ## Getting scan history for the logged-in user, with Redis caching

# @app.route('/api/history', methods=['GET'])
# @jwt_required()
# def get_history():
#     user_id = get_jwt_identity()

#     # Build a unique cache key per user
#     # e.g. "history:42" for user with id 42
#     cache_key = f"history:{user_id}"

#     try:
#         # Step 1: Check Redis first (the sticky note)
#         cached = redis_client.get(cache_key)
#         if cached:
#             print(f"[Cache] HIT for {cache_key}")
#             return jsonify(json.loads(cached))

#         # Step 2: Cache miss — go to PostgreSQL
#         print(f"[Cache] MISS for {cache_key} — querying DB")
#         scans = Scan.query.filter_by(
#             user_id=int(user_id)
#         ).order_by(Scan.timestamp.desc()).limit(10).all()

#         result = [{
#             'fen': s.fen,
#             'image': s.image_data,
#             'date': s.timestamp.strftime("%b %d, %H:%M")
#         } for s in scans]

#         # Step 3: Store in Redis for 60 seconds
#         # ex=60 means "expire after 60 seconds"
#         redis_client.set(cache_key, json.dumps(result), ex=60)

#         return jsonify(result)

#     except Exception as e:
#         print(f"[Cache] Error: {e} — falling back to DB")
#         # If Redis is down, fall back to direct DB query
#         # Cache should never break the app
#         try:
#             scans = Scan.query.filter_by(
#                 user_id=int(user_id)
#             ).order_by(Scan.timestamp.desc()).limit(10).all()
#             return jsonify([{
#                 'fen': s.fen,
#                 'image': s.image_data,
#                 'date': s.timestamp.strftime("%b %d, %H:%M")
#             } for s in scans])
#         except Exception as db_e:
#             print(f"History fetch error: {db_e}")
#             return jsonify([])

# with app.app_context():
#     db.create_all()


# if __name__ == '__main__':
#     app.run(debug=True, port=5000)
