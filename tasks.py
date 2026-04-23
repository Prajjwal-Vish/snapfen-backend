import sys
from pathlib import Path

# This must come BEFORE any local module imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

import os
import cv2
import numpy as np
import base64
import boto3
from botocore.client import Config
import uuid
from pathlib import Path
from dotenv import load_dotenv
from email_sending import send_report_email

load_dotenv()
 

# Creating celery functions here instead of in app.py avoids circular imports.
import os
import ssl
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery("snapfen", broker=REDIS_URL, backend=REDIS_URL)

if REDIS_URL.startswith("rediss://"):
    ssl_config = {"ssl_cert_reqs": ssl.CERT_NONE}
    celery_app.conf.update(
        broker_use_ssl=ssl_config,
        redis_backend_use_ssl=ssl_config,
    )

celery_app.conf.result_expires = 3600

# ── Base directory and model initialization ─────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "Fine_tuned_CNN_Model" / "chess_model_v5.tflite"
CLASS_NAMES_PATH = BASE_DIR / "labels" / "class_names.txt"

# Load TFLite model and create interpreter
INTERPRETER = None
INPUT_DETAILS = None
OUTPUT_DETAILS = None
CLASS_NAMES = []

try:
    import tensorflow as tf
    
    # Load the TFLite model
    with open(MODEL_PATH, 'rb') as f:
        model_data = f.read()
    
    # Create interpreter from the model data
    INTERPRETER = tf.lite.Interpreter(model_content=model_data)
    INTERPRETER.allocate_tensors()
    
    # Get input and output details
    INPUT_DETAILS = INTERPRETER.get_input_details()
    OUTPUT_DETAILS = INTERPRETER.get_output_details()
    
    print(f"[Worker] TFLite model loaded from {MODEL_PATH}")
    print(f"[Worker] Input shape: {INPUT_DETAILS[0]['shape']}")
    print(f"[Worker] Output shape: {OUTPUT_DETAILS[0]['shape']}")
    
except ImportError:
    print("[Worker] TensorFlow not installed, trying tflite-runtime...")
    try:
        import tflite_runtime.interpreter as tflite
        
        INTERPRETER = tflite.Interpreter(model_path=str(MODEL_PATH))
        INTERPRETER.allocate_tensors()
        
        INPUT_DETAILS = INTERPRETER.get_input_details()
        OUTPUT_DETAILS = INTERPRETER.get_output_details()
        
        print(f"[Worker] TFLite model loaded from {MODEL_PATH}")
        print(f"[Worker] Input shape: {INPUT_DETAILS[0]['shape']}")
        print(f"[Worker] Output shape: {OUTPUT_DETAILS[0]['shape']}")
        
    except Exception as e:
        print(f"[Worker] Model loading failed: {e}")
        INTERPRETER = None
        INPUT_DETAILS = None
        OUTPUT_DETAILS = None

except Exception as e:
    print(f"[Worker] Model loading failed: {e}")
    INTERPRETER = None
    INPUT_DETAILS = None
    OUTPUT_DETAILS = None

# Load class names
try:
    with open(CLASS_NAMES_PATH, 'r') as f:
        CLASS_NAMES = [line.strip() for line in f.readlines()]
    print(f"[Worker] Loaded {len(CLASS_NAMES)} class names from {CLASS_NAMES_PATH}")
except Exception as e:
    print(f"[Worker] Failed to load class names: {e}")
    CLASS_NAMES = []

# ── Helper functions (copied from app.py — worker is self-contained) ──────────
 
def _tflite_predict(input_data: np.ndarray) -> np.ndarray:
    """Run TFLite inference on a batch of images, one at a time."""
    predictions = []
    for i in range(len(input_data)):
        img = input_data[i:i+1].astype(np.float32)
        INTERPRETER.set_tensor(INPUT_DETAILS[0]["index"], img)
        INTERPRETER.invoke()
        output = INTERPRETER.get_tensor(OUTPUT_DETAILS[0]["index"])
        predictions.append(output[0])
    return np.array(predictions)
 
 
def _predict_with_voting(squares_batch: list) -> list:
    """
    Run augmented voting inference on 64 board squares.
    Each square is predicted 5 times with slight variations,
    and the majority vote wins. More accurate than single prediction.
    """
    augmented = []
    for sq in squares_batch:
        augmented.append(sq)
        augmented.append(np.roll(sq, -2, axis=1))
        augmented.append(np.roll(sq, -2, axis=0))
        augmented.append(np.clip(sq * 0.7, 0, 255))
        crop = sq[4:60, 4:60]
        augmented.append(cv2.resize(crop, (64, 64)))
 
    big_batch = np.array(augmented)
    preds = _tflite_predict(big_batch)
    num_classes = preds.shape[1]
    reshaped = preds.reshape(64, 5, num_classes)
 
    final_indices = []
    for i in range(64):
        votes = np.argmax(reshaped[i], axis=1)
        counts = np.bincount(votes)
        final_indices.append(int(np.argmax(counts)))
 
    return final_indices
 
 
def _correct_color_errors(image_rgb: np.ndarray, predicted_label: str) -> str:
    """
    Sanity-check piece color against pixel brightness.
    A 'light' piece on a very dark tile is probably misclassified — fix it.
    """
    if "empty" in predicted_label:
        return predicted_label
 
    parts = predicted_label.split("_")
    if len(parts) < 2:
        return predicted_label
 
    current_color, piece_type = parts[0], parts[1]
    img_uint8 = image_rgb.astype(np.uint8) if image_rgb.dtype != np.uint8 else image_rgb
    img_bgr = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    center = gray[h // 4: 3 * h // 4, w // 4: 3 * w // 4]
    brightness = np.mean(center)
 
    if brightness < 60 and current_color == "light":
        return f"dark_{piece_type}"
    if brightness > 180 and current_color == "dark":
        return f"light_{piece_type}"
    return predicted_label
 
 
def _manual_slice(img: np.ndarray):
    """Bypass auto-detection: resize to 512x512 and slice into 64 tiles."""
    img_resized = cv2.resize(img, (512, 512))
    squares = []
    for row in range(8):
        for col in range(8):
            y1, y2 = row * 64, (row + 1) * 64
            x1, x2 = col * 64, (col + 1) * 64
            squares.append(img_resized[y1:y2, x1:x2])
    return np.array(squares), img_resized, None
 

# ── B2 Object Storage ─────────────────────────────────────────────────────────

def _get_b2_client():
    """
    Create a boto3 client pointed at Backblaze B2.
    boto3 normally talks to AWS S3, but B2 is S3-compatible —
    we just swap the endpoint URL to point at B2 instead.
    Think of it like using the same phone but calling a different number.
    """
    return boto3.client(
        "s3",
        endpoint_url=os.environ.get("B2_ENDPOINT"),
        aws_access_key_id=os.environ.get("B2_KEY_ID"),
        aws_secret_access_key=os.environ.get("B2_APP_KEY"),
        config=Config(signature_version="s3v4"),
    )


def _upload_image_to_b2(image_jpeg_bytes: bytes) -> str | None:
    """
    Upload a JPEG image to Backblaze B2 and return its public URL.
    
    Instead of storing the image as Base64 text in PostgreSQL (bad),
    we store the actual image file in B2 (good) and only save the
    URL string in the database. Like the difference between storing
    a photo in your email vs storing a link to the photo.
    
    Returns the public URL string, or None if upload failed.
    """
    try:
        client = _get_b2_client()
        bucket = os.environ.get("B2_BUCKET_NAME")
        
        # Generate a unique filename — uuid4 gives a random unique ID
        # e.g. "boards/a3f9c2d1-4b5e-4c6f-8d9e-1a2b3c4d5e6f.jpg"
        filename = f"boards/{uuid.uuid4()}.jpg"
        
        client.put_object(
            Bucket=bucket,
            Key=filename,
            Body=image_jpeg_bytes,
            ContentType="image/jpeg",
        )
        
        # Construct the public URL
        endpoint = os.environ.get("B2_ENDPOINT")
        public_url = f"{endpoint}/{bucket}/{filename}"
        
        print(f"[Worker] Image uploaded to B2: {filename}")
        return public_url
        
    except Exception as e:
        print(f"[Worker] B2 upload failed (non-fatal): {e}")
        return None


def _delete_image_from_b2(image_url: str):
    try:
        client = _get_b2_client()
        bucket = os.environ.get("B2_BUCKET_NAME")
        
        # Extract the key (filename) from the full URL
        # URL looks like: https://s3.us-west-004.backblazeb2.com/snapfen-boards/boards/uuid.jpg
        # Key is everything after the bucket name: boards/uuid.jpg
        endpoint = os.environ.get("B2_ENDPOINT")
        prefix = f"{endpoint}/{bucket}/"
        key = image_url.replace(prefix, "")
        
        client.delete_object(Bucket=bucket, Key=key)
        print(f"[Worker] Deleted from B2: {key}")
        
    except Exception as e:
        print(f"[Worker] B2 delete failed (non-fatal): {e}")


def _prune_old_scans(user_id: int, keep: int = 10):
    """
    Keep only the most recent `keep` scans for a user.
    Delete the rest from both the database AND B2 storage.
    """
    import sqlalchemy as sa

    database_url = os.environ.get("DATABASE_URL", "sqlite:///chessvision.db")
    if database_url == "sqlite:///chessvision.db":
        instance_path = BASE_DIR / "instance" / "chessvision.db"
        database_url = f"sqlite:///{instance_path}"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    connect_args = {"sslmode": "require"} if database_url.startswith("postgresql") else {}
    engine = sa.create_engine(database_url, connect_args=connect_args)

    with engine.connect() as conn:
        # Get all scans for this user, newest first
        rows = conn.execute(
            sa.text(
                "SELECT id, image_data FROM scan "
                "WHERE user_id = :user_id "
                "ORDER BY timestamp DESC"
            ),
            {"user_id": user_id}
        ).fetchall()

        # If under the limit, nothing to do
        if len(rows) <= keep:
            return

        # Everything after the first `keep` rows needs to be deleted
        rows_to_delete = rows[keep:]
        ids_to_delete = [row[0] for row in rows_to_delete]
        urls_to_delete = [row[1] for row in rows_to_delete if row[1] and row[1].startswith("http")]

        # Delete images from B2 first
        for url in urls_to_delete:
            _delete_image_from_b2(url)

        # Then delete the database rows
        if database_url.startswith("postgresql"):
            conn.execute(
                sa.text("DELETE FROM scan WHERE id = ANY(:ids)"),
                {"ids": ids_to_delete}
            )
        else:
            placeholders = ",".join(f":id{i}" for i in range(len(ids_to_delete)))
            params = {f"id{i}": id_val for i, id_val in enumerate(ids_to_delete)}
            conn.execute(sa.text(f"DELETE FROM scan WHERE id IN ({placeholders})"), params)
        
        conn.commit()
        print(f"[Worker] Pruned {len(rows_to_delete)} old scans for user {user_id}")
 
@celery_app.task(bind=True, max_retries=2)
def run_inference(self, img_b64: str, pov: str, is_manual: bool, user_id):
    # Decode Base64 string back to bytes at the start of the task

    from chessboard_snipper import process_image
    from flip_board_to_black_pov import assemble_fen_from_predictions, black_perspective_fen

    img_bytes = base64.b64decode(img_b64)

    if INTERPRETER is None:
        # Model failed to load when worker started — raise so Celery retries
        raise RuntimeError("TFLite model not loaded in worker. Check MODEL_PATH.")
 
    try:
        # ── Step 1: Decode image bytes → OpenCV image ─────────────────────
        # img_bytes came from Flask (file.read()) and was passed here via Redis.
        # Redis stores it as a binary blob. We decode it back to a numpy array.
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return {"error": "Could not decode image. Is it a valid PNG/JPG?"}
 
        # ── Step 2: Detect and crop the board ────────────────────────────
        if is_manual:
            processed = _manual_slice(img)
        else:
            processed = process_image(img)
 
        if processed is None:
            return {"error": "No chessboard detected. Try using the Crop tool."}
 
        model_inputs, board_viz, _ = processed
 
        # ── Step 3: Run ML inference with voting ─────────────────────────
        pred_indices = _predict_with_voting(model_inputs)
        pred_labels = [CLASS_NAMES[i] for i in pred_indices]
 
        # ── Step 4: Correct any color misclassifications ─────────────────
        final_labels = [
            _correct_color_errors(model_inputs[i], label)
            for i, label in enumerate(pred_labels)
        ]
 
        # ── Step 5: Assemble FEN string ───────────────────────────────────
        fen = assemble_fen_from_predictions(final_labels)
        turn = "w"
        if pov == "b":
            fen = black_perspective_fen(fen)
            turn = "b"
        final_fen = f"{fen} {turn} KQkq - 0 1"
 
        # ── Step 6: Encode cropped board image as Base64 for display ─────
        is_success, buffer = cv2.imencode(".jpg", board_viz)
        
        image_url = None
        cropped_image_data = None  # what we show in the browser (data: URL)
        
        if is_success:
            jpeg_bytes = buffer.tobytes()
            
            # Try uploading to B2
            image_url = _upload_image_to_b2(jpeg_bytes)
            
            if image_url:
                # Successfully uploaded — browser will load from B2 URL
                cropped_image_data = image_url
            else:
                # B2 failed — fall back to Base64 so user still sees the image
                cropped_image_data = f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('utf-8')}"
 
        # ── Step 7: Save scan to DB if user is logged in ──────────────────
        # Note: We use a minimal DB save here without Flask-SQLAlchemy.
        # The worker doesn't have Flask's app context. We use SQLAlchemy directly.
        if user_id:
            try:
                _save_scan_to_db(final_fen, image_url or cropped_image_data, user_id)
                _prune_old_scans(user_id, keep=10)
            except Exception as db_err:
                print(f"[Worker] DB save failed (non-fatal): {db_err}")

        return {
            "status": "done",
            "fen": final_fen,
            "cropped_image": cropped_image_data,
        }
 
    except Exception as exc:
        # Celery retry: wait 5 seconds, then try again (up to max_retries=2)
        # This handles transient failures like a momentary Redis blip
        raise self.retry(exc=exc, countdown=5)
 
@celery_app.task(bind=True, max_retries=3)
def send_email_task(self, text: str, tags: str, fen: str,
                    orig_b64: str | None, crop_b64: str | None,
                    attach_b64: str | None):
    """
    Background task for sending feedback/bug report emails.
    
    Same problem as ML inference — email sending can take 2-3 seconds
    and blocks the HTTP thread if done synchronously.
    
    We Base64-encode the image bytes before passing them here
    because Celery serializes arguments as JSON, and JSON can't
    handle raw bytes — same fix as we did for the ML task.
    
    max_retries=3 means if Brevo API is down, Celery automatically
    retries 3 times with increasing delays. threading.Thread had
    zero retry logic — if it failed, the email was just lost silently.
    """
    try:

        # Decode Base64 strings back to bytes (or None if not provided)
        orig_bytes = base64.b64decode(orig_b64) if orig_b64 else None
        crop_bytes = base64.b64decode(crop_b64) if crop_b64 else None
        attach_bytes = base64.b64decode(attach_b64) if attach_b64 else None

        send_report_email(text, tags, fen, orig_bytes, crop_bytes, attach_bytes)
        print(f"[Worker] Email sent successfully. Tags: {tags}")

    except Exception as exc:
        print(f"[Worker] Email failed, retrying... Error: {exc}")
        # countdown=2**self.request.retries gives exponential backoff:
        # retry 1 → wait 2s, retry 2 → wait 4s, retry 3 → wait 8s
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
 
def _save_scan_to_db(fen: str, image_data: str, user_id: int):
    import sqlalchemy as sa
    from datetime import datetime

    database_url = os.environ.get("DATABASE_URL", "sqlite:///chessvision.db")
    if database_url == "sqlite:///chessvision.db":
        instance_path = BASE_DIR / "instance" / "chessvision.db"
        database_url = f"sqlite:///{instance_path}"
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    connect_args = {"sslmode": "require"} if database_url.startswith("postgresql") else {}
    engine = sa.create_engine(database_url, connect_args=connect_args)

    with engine.connect() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO scan (fen, image_data, timestamp, user_id) "
                "VALUES (:fen, :image_data, :timestamp, :user_id)"
            ),
            {
                "fen": fen,
                "image_data": image_data or "",
                "timestamp": datetime.utcnow(),
                "user_id": user_id,
            }
        )
        conn.commit()

    # Invalidate the user's history cache so next request gets fresh data
    try:
        import redis as redis_lib
        redis_client = redis_lib.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            ssl_cert_reqs=None,
            decode_responses=True
        )
        cache_key = f"history:{user_id}"
        redis_client.delete(cache_key)
        print(f"[Cache] Invalidated {cache_key}")
    except Exception as e:
        print(f"[Cache] Invalidation failed (non-fatal): {e}")