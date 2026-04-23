# blueprints/report.py
# ─────────────────────────────────────────────────────────────────────────────
# Handles feedback and bug reports:
#   POST /report_issue
# ─────────────────────────────────────────────────────────────────────────────

import base64
from flask import Blueprint, request, jsonify
import os, ssl
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_celery = Celery("snapfen", broker=REDIS_URL, backend=REDIS_URL)
if REDIS_URL.startswith("rediss://"):
    _ssl_cfg = {"ssl_cert_reqs": ssl.CERT_NONE}
    _celery.conf.update(broker_use_ssl=_ssl_cfg, redis_backend_use_ssl=_ssl_cfg)

report_bp = Blueprint("report", __name__)


@report_bp.route("/report_issue", methods=["POST"])
def report_issue():
    """
    Accepts feedback/bug report form data and enqueues an email task.
    Returns instantly — email is sent in the background by Celery.
    """
    tags = request.form.get("tags", "General")
    text = request.form.get("feedback", "")
    fen = request.form.get("fen", "N/A")

    orig = request.files.get("original_image")
    crop = request.files.get("cropped_image")
    bug_file = request.files.get("attachment")

    # Base64-encode image bytes before passing to Celery
    # Celery serializes args as JSON — raw bytes aren't JSON-serializable
    orig_b64 = base64.b64encode(orig.read()).decode() if orig else None
    crop_b64 = base64.b64encode(crop.read()).decode() if crop else None
    attach_b64 = base64.b64encode(bug_file.read()).decode() if bug_file else None

    # Enqueue email task — returns instantly, no blocking
    _celery.send_task("tasks.send_email_task", kwargs={
    "text": text, "tags": tags, "fen": fen,
    "orig_b64": orig_b64, "crop_b64": crop_b64, "attach_b64": attach_b64,
    })

    return jsonify({"status": "success"})