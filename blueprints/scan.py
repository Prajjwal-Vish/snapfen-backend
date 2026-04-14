# blueprints/scan.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles the ML scan pipeline:
#   POST /predict      → enqueue task, return task_id instantly
#   GET  /result/<id>  → poll for task result
# ─────────────────────────────────────────────────────────────────────────────

import base64
from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from celery.result import AsyncResult

from tasks import celery_app, run_inference
from extensions import limiter

scan_bp = Blueprint("scan", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@scan_bp.route("/predict", methods=["POST"])
@limiter.limit("15 per minute")  # <--- Use it as a normal decorator!
def predict():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Use PNG, JPG, or WEBP."}), 400

    pov = request.form.get("pov", "w")
    is_manual = request.form.get("is_manual") == "true"

    img_b64 = base64.b64encode(file.read()).decode("utf-8")

    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        user_id = int(uid) if uid else None
    except Exception:
        pass

    task = run_inference.delay(
        img_b64=img_b64,
        pov=pov,
        is_manual=is_manual,
        user_id=user_id,
    )

    return jsonify({"task_id": task.id}), 202


@scan_bp.route("/result/<task_id>", methods=["GET"])
@limiter.exempt  # <--- This now works perfectly!
def get_result(task_id: str):
    try:
        result = AsyncResult(task_id, app=celery_app)

        if result.state == "PENDING":
            return jsonify({"status": "pending"})
        if result.state == "STARTED":
            return jsonify({"status": "started"})
        if result.state == "SUCCESS":
            data = result.result
            if "error" in data:
                return jsonify({"status": "error", "error": data["error"]}), 400
            return jsonify({
                "status": "done",
                "fen": data["fen"],
                "cropped_image": data["cropped_image"],
            })
        if result.state == "FAILURE":
            return jsonify({
                "status": "error",
                "error": "Inference failed after retries. Please try again.",
            }), 500

        return jsonify({"status": "pending"})

    except Exception as e:
        print(f"[get_result ERROR] {e}")
        return jsonify({"status": "error", "error": str(e)}), 500



# import base64
# from flask import Blueprint, request, jsonify, current_app
# from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
# from celery.result import AsyncResult
# from tasks import celery_app, run_inference

# scan_bp = Blueprint("scan", __name__)

# ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}


# def allowed_file(filename: str) -> bool:
#     return (
#         "." in filename
#         and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
#     )


# @scan_bp.route("/predict", methods=["POST"])
# def predict():
#     """
#     Accepts an image upload, enqueues ML inference as a Celery task,
#     and immediately returns a task_id.
#     The client polls GET /result/<task_id> to check progress.
#     """
#     # Import limiter from app to apply rate limiting
#     # We access it via current_app to avoid circular imports
#     from app import limiter
#     limiter.limit("15 per minute")(lambda: None)()

#     if "file" not in request.files:
#         return jsonify({"error": "No file uploaded"}), 400

#     file = request.files["file"]
#     if not file.filename or not allowed_file(file.filename):
#         return jsonify({"error": "Invalid file type. Use PNG, JPG, or WEBP."}), 400

#     pov = request.form.get("pov", "w")
#     is_manual = request.form.get("is_manual") == "true"

#     # Read and Base64-encode image bytes
#     # Celery serializes args as JSON — raw bytes aren't JSON-serializable
#     img_b64 = base64.b64encode(file.read()).decode("utf-8")

#     # Get user_id if logged in (optional — anonymous users still get FEN)
#     user_id = None
#     try:
#         verify_jwt_in_request(optional=True)
#         uid = get_jwt_identity()
#         user_id = int(uid) if uid else None
#     except Exception:
#         pass

#     # Enqueue task — returns instantly with a ticket ID
#     task = run_inference.delay(
#         img_b64=img_b64,
#         pov=pov,
#         is_manual=is_manual,
#         user_id=user_id,
#     )

#     # 202 = "Accepted" — I got your request, working on it, check back later
#     return jsonify({"task_id": task.id}), 202


# @scan_bp.route("/result/<task_id>", methods=["GET"])
# @limiter.exempt 
# def get_result(task_id: str):
#     """
#     Poll this endpoint with the task_id returned by /predict.
#     Returns the scan result when ready, or a status while pending.
#     """
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
#             return jsonify({
#                 "status": "error",
#                 "error": "Inference failed after retries. Please try again.",
#             }), 500

#         return jsonify({"status": "pending"})

#     except Exception as e:
#         print(f"[get_result ERROR] {e}")
#         return jsonify({"status": "error", "error": str(e)}), 500