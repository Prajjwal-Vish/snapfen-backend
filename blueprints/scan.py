import base64
import ssl
import os
from flask import Blueprint, request, jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from celery import Celery
from celery.result import AsyncResult
from extensions import limiter

scan_bp = Blueprint("scan", __name__)

# Lightweight Celery connector — only needs Redis URL, no ML imports
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_ssl_kwargs = {"ssl_cert_reqs": None} if REDIS_URL.startswith("rediss://") else {}

celery_app = Celery("snapfen", broker=REDIS_URL, backend=REDIS_URL)

if REDIS_URL.startswith("rediss://"):
    import ssl as _ssl
    celery_app.conf.update(
        broker_use_ssl={"ssl_cert_reqs": _ssl.CERT_NONE},
        redis_backend_use_ssl={"ssl_cert_reqs": _ssl.CERT_NONE},
    )

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@scan_bp.route("/predict", methods=["POST"])
@limiter.limit("15 per minute")
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

    # send_task() by name — Flask never imports tasks.py, zero ML dependencies
    task = celery_app.send_task(
        "tasks.run_inference",
        kwargs={
            "img_b64": img_b64,
            "pov": pov,
            "is_manual": is_manual,
            "user_id": user_id,
        }
    )

    return jsonify({"task_id": task.id}), 202


@scan_bp.route("/result/<task_id>", methods=["GET"])
@limiter.exempt
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



## Code for the /scan endpoint, which handles image uploads and runs inference using Celery tasks. (last working without os and ssl import on top)


# import base64
# from flask import Blueprint, request, jsonify
# from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
# from celery.result import AsyncResult

# from tasks import celery_app, run_inference
# from extensions import limiter

# scan_bp = Blueprint("scan", __name__)

# ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "bmp"}

# def allowed_file(filename: str) -> bool:
#     return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# @scan_bp.route("/predict", methods=["POST"])
# @limiter.limit("15 per minute")  # <--- Use it as a normal decorator!
# def predict():
#     if "file" not in request.files:
#         return jsonify({"error": "No file uploaded"}), 400

#     file = request.files["file"]
#     if not file.filename or not allowed_file(file.filename):
#         return jsonify({"error": "Invalid file type. Use PNG, JPG, or WEBP."}), 400

#     pov = request.form.get("pov", "w")
#     is_manual = request.form.get("is_manual") == "true"

#     img_b64 = base64.b64encode(file.read()).decode("utf-8")

#     user_id = None
#     try:
#         verify_jwt_in_request(optional=True)
#         uid = get_jwt_identity()
#         user_id = int(uid) if uid else None
#     except Exception:
#         pass

#     task = celery_app.send_task(
#         "tasks.run_inference", 
#         kwargs={
#             "img_b64": img_b64,
#             "pov": pov,
#             "is_manual": is_manual,
#             "user_id": user_id,
#         }
#     )

#     return jsonify({"task_id": task.id}), 202


# @scan_bp.route("/result/<task_id>", methods=["GET"])
# @limiter.exempt  # <--- This now works perfectly!
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
