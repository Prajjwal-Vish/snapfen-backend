# inference.py
# Pure ML inference — no Celery, no Flask, just Python
import os, cv2, numpy as np, base64
from pathlib import Path

BASE_DIR   = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "Fine_tuned_CNN_Model" / "chess_model_v5.tflite"
LABELS_PATH= BASE_DIR / "labels" / "class_names.txt"

# ── Load model once at module level (when gunicorn worker starts) ─────────
try:
    import tflite_runtime.interpreter as tflite
except ImportError:
    import tensorflow.lite as tflite

INTERPRETER   = None
INPUT_DETAILS = None
OUTPUT_DETAILS= None
CLASS_NAMES   = None

def _load():
    global INTERPRETER, INPUT_DETAILS, OUTPUT_DETAILS, CLASS_NAMES
    if not MODEL_PATH.exists(): return
    INTERPRETER = tflite.Interpreter(model_path=str(MODEL_PATH))
    INTERPRETER.allocate_tensors()
    INPUT_DETAILS  = INTERPRETER.get_input_details()
    OUTPUT_DETAILS = INTERPRETER.get_output_details()
    CLASS_NAMES    = LABELS_PATH.read_text().splitlines()
    print(f"[Inference] Model loaded. {len(CLASS_NAMES)} classes.")

_load()

# ── Helpers ───────────────────────────────────────────────────────────────
def _predict(batch):
    preds = []
    for i in range(len(batch)):
        img = batch[i:i+1].astype(np.float32)
        INTERPRETER.set_tensor(INPUT_DETAILS[0]["index"], img)
        INTERPRETER.invoke()
        preds.append(INTERPRETER.get_tensor(OUTPUT_DETAILS[0]["index"])[0])
    return np.array(preds)

def _vote(squares):
    augmented = []
    for sq in squares:
        augmented += [sq, np.roll(sq,-2,axis=1), np.roll(sq,-2,axis=0),
                      np.clip(sq*0.7,0,255), cv2.resize(sq[4:60,4:60],(64,64))]
    preds = _predict(np.array(augmented))
    reshaped = preds.reshape(64, 5, preds.shape[1])
    return [int(np.argmax(np.bincount(np.argmax(reshaped[i],axis=1)))) for i in range(64)]

def _fix_colors(img_rgb, label):
    if "empty" in label or "_" not in label: return label
    color, piece = label.split("_", 1)
    gray = cv2.cvtColor(cv2.cvtColor(
        img_rgb.astype(np.uint8), cv2.COLOR_RGB2BGR), cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    brightness = np.mean(gray[h//4:3*h//4, w//4:3*w//4])
    if brightness < 60  and color == "light": return f"dark_{piece}"
    if brightness > 180 and color == "dark":  return f"light_{piece}"
    return label

def _manual_slice(img):
    img = cv2.resize(img, (512, 512))
    squares = []
    for r in range(8):
        for c in range(8):
            squares.append(img[r*64:(r+1)*64, c*64:(c+1)*64])
    return np.array(squares), img, None

# ── Public API ────────────────────────────────────────────────────────────
def run_inference_sync(img_bytes, pov, is_manual, user_id):
    from chessboard_snipper import process_image, NoChessboardDetected
    from flip_board_to_black_pov import assemble_fen_from_predictions, black_perspective_fen

    if INTERPRETER is None:
        return {"error": "Model not loaded on server."}

    nparr = np.frombuffer(img_bytes, np.uint8)
    img   = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return {"error": "Could not decode image."}

    try:
        processed = _manual_slice(img) if is_manual else process_image(img)
    except NoChessboardDetected:
        return {"error": "No chessboard detected. Try the Crop tool."}

    if processed is None:
        return {"error": "No chessboard detected. Try the Crop tool."}

    model_inputs, board_viz, _ = processed
    indices  = _vote(model_inputs)
    labels   = [CLASS_NAMES[i] for i in indices]
    labels   = [_fix_colors(model_inputs[i], l) for i, l in enumerate(labels)]

    fen  = assemble_fen_from_predictions(labels)
    turn = "w"
    if pov == "b":
        fen  = black_perspective_fen(fen)
        turn = "b"
    final_fen = f"{fen} {turn} KQkq - 0 1"

    ok, buf = cv2.imencode(".jpg", board_viz)
    img_data = None
    if ok:
        from tasks import _upload_image_to_b2
        jpeg = buf.tobytes()
        url  = _upload_image_to_b2(jpeg)
        img_data = url or f"data:image/jpeg;base64,{base64.b64encode(jpeg).decode()}"

    if user_id:
        try:
            from tasks import _save_scan_to_db, _prune_old_scans
            _save_scan_to_db(final_fen, img_data, user_id)
            _prune_old_scans(user_id, keep=10)
        except Exception as e:
            print(f"[Inference] DB save failed (non-fatal): {e}")

    return {"fen": final_fen, "cropped_image": img_data}