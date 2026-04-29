# blueprints/scan.py
import base64
import cv2
import numpy as np
from pathlib import Path
from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from extensions import limiter

scan_bp = Blueprint("scan", __name__)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

def allowed_file(f):
    return "." in f and f.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@scan_bp.route("/predict", methods=["POST"])
@limiter.limit("15 per minute")
def predict():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if not file.filename or not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type"}), 400

    pov       = request.form.get("pov", "w")
    is_manual = request.form.get("is_manual") == "true"
    img_bytes = file.read()

    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        uid = get_jwt_identity()
        user_id = int(uid) if uid else None
    except Exception:
        pass

    # Run inference directly — no Celery
    from inference import run_inference_sync
    result = run_inference_sync(img_bytes, pov, is_manual, user_id)

    if "error" in result:
        return jsonify({"error": result["error"]}), 400

    return jsonify({
        "fen":           result["fen"],
        "cropped_image": result["cropped_image"],
    })


# @scan_bp.route("/result/<task_id>", methods=["GET"])
# @limiter.exempt
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
#             return jsonify({
#                 "status": "error",
#                 "error": "Inference failed after retries. Please try again.",
#             }), 500

#         return jsonify({"status": "pending"})

#     except Exception as e:
#         print(f"[get_result ERROR] {e}")
#         return jsonify({"status": "error", "error": str(e)}), 500