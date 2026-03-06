# import cv2
# import numpy as np
# from typing import Tuple, List, Union, Optional

# # Configuration (tweak if needed)
# MODEL_SQUARE_SIZE = 64
# BOARD_SIZE_PX = MODEL_SQUARE_SIZE * 8  # 512

# def _square_from_bbox(x:int, y:int, w:int, h:int, img_w:int, img_h:int, pad:int=0) -> Tuple[int,int,int,int]:
#     side = max(w, h) + 2*pad
#     cx = x + w // 2
#     cy = y + h // 2
#     half = side // 2
#     x1 = max(0, cx - half)
#     y1 = max(0, cy - half)
#     x2 = min(img_w, cx + half)
#     y2 = min(img_h, cy + half)
#     side_w = x2 - x1
#     side_h = y2 - y1
#     side = min(side_w, side_h)
#     x1 = max(0, cx - side // 2)
#     y1 = max(0, cy - side // 2)
#     return int(x1), int(y1), int(side), int(side)

# def _detect_square_bbox(image: np.ndarray) -> Tuple[int,int,int,int]:
#     h_img, w_img = image.shape[:2]
#     gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
#     gray = cv2.bilateralFilter(gray, 9, 75, 75)
#     clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
#     gray = clahe.apply(gray)

#     edges = cv2.Canny(gray, 40, 140)
#     kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3,3))
#     edges = cv2.dilate(edges, kernel, iterations=1)

#     contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
#     if contours:
#         img_area = float(w_img * h_img)
#         quad_candidates = []
#         for cnt in contours:
#             area = cv2.contourArea(cnt)
#             if area < 0.005 * img_area:
#                 continue
#             peri = cv2.arcLength(cnt, True)
#             approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
#             if len(approx) == 4:
#                 x,y,w,h = cv2.boundingRect(approx)
#                 aspect = w / float(h) if h != 0 else 0
#                 score = (min(aspect, 1.0/aspect)) * (area / img_area)
#                 quad_candidates.append((score, area, (x,y,w,h)))
#         if quad_candidates:
#             quad_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
#             x,y,w,h = quad_candidates[0][2]
#             print(f"Selected quad contour bbox: x={x}, y={y}, w={w}, h={h}")
#             return _square_from_bbox(x,y,w,h, w_img, h_img, pad=4)

#         # fallback to large-ish near-square bounding rects
#         rect_candidates = []
#         for cnt in contours:
#             area = cv2.contourArea(cnt)
#             if area < 0.01 * img_area:
#                 continue
#             x,y,w,h = cv2.boundingRect(cnt)
#             aspect = w / float(h) if h != 0 else 0
#             if 0.6 <= aspect <= 1.6:
#                 rect_candidates.append((area, (x,y,w,h)))
#         if rect_candidates:
#             rect_candidates.sort(key=lambda x: x[0], reverse=True)
#             x,y,w,h = rect_candidates[0][1]
#             print(f"Selected rect candidate bbox: x={x}, y={y}, w={w}, h={h}")
#             return _square_from_bbox(x,y,w,h, w_img, h_img, pad=6)

#         # minAreaRect fallback
#         for cnt in contours:
#             area = cv2.contourArea(cnt)
#             if area < 0.01 * img_area:
#                 continue
#             rect = cv2.minAreaRect(cnt)
#             box = cv2.boxPoints(rect).astype(np.int32)
#             x_min = int(box[:,0].min())
#             y_min = int(box[:,1].min())
#             x_max = int(box[:,0].max())
#             y_max = int(box[:,1].max())
#             w = x_max - x_min
#             h = y_max - y_min
#             if w > 10 and h > 10:
#                 print(f"Selected minAreaRect fallback bbox: x={x_min}, y={y_min}, w={w}, h={h}")
#                 return _square_from_bbox(x_min, y_min, w, h, w_img, h_img, pad=6)

#     # final centered fallback
#     print("Warning: no suitable contour found -> will fallback to center crop.")
#     margin = int(min(h_img, w_img) * 0.04)
#     side = min(h_img, w_img) - 2 * margin
#     cx, cy = w_img // 2, h_img // 2
#     x1 = max(0, cx - side // 2)
#     y1 = max(0, cy - side // 2)
#     return (int(x1), int(y1), int(side), int(side))

# def _crop_board(image: np.ndarray, bbox: Tuple[int,int,int,int]) -> np.ndarray:
#     x, y, w, h = bbox
#     h_img, w_img = image.shape[:2]
#     x1 = max(0, x)
#     y1 = max(0, y)
#     x2 = min(w_img, x + w)
#     y2 = min(h_img, y + h)
#     crop = image[y1:y2, x1:x2].copy()
#     if crop.size == 0:
#         raise ValueError("Empty crop produced; bbox may be invalid.")
#     return crop

# def _preprocess_board_to_tiles(board_image: np.ndarray) -> List[np.ndarray]:
#     resized = cv2.resize(board_image, (BOARD_SIZE_PX, BOARD_SIZE_PX), interpolation=cv2.INTER_AREA)
#     tiles: List[np.ndarray] = []
#     for r in range(8):
#         for c in range(8):
#             y1 = r * MODEL_SQUARE_SIZE
#             y2 = (r + 1) * MODEL_SQUARE_SIZE
#             x1 = c * MODEL_SQUARE_SIZE
#             x2 = (c + 1) * MODEL_SQUARE_SIZE
#             tile = resized[y1:y2, x1:x2]
#             tile_rgb = cv2.cvtColor(tile, cv2.COLOR_BGR2RGB)
#             tile_f = tile_rgb.astype(np.float32)
#             tiles.append(tile_f)
#     return tiles

# ImageInput = Union[np.ndarray, bytes, str]

# def process_image(image_input: ImageInput) -> Optional[Tuple[List[np.ndarray], np.ndarray, Tuple[int,int,int,int]]]:

#     try:
#         # load image depending on type
#         if isinstance(image_input, np.ndarray):
#             image = image_input
#         elif isinstance(image_input, bytes):
#             nparr = np.frombuffer(image_input, np.uint8)
#             image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#             if image is None:
#                 raise ValueError("Could not decode image from given bytes.")
#         elif isinstance(image_input, str):
#             image = cv2.imread(image_input, cv2.IMREAD_COLOR)
#             if image is None:
#                 raise ValueError(f"Could not read image from path: {image_input}")
#         else:
#             raise TypeError("image_input must be numpy array, bytes, or path string.")

#         # detect board bbox
#         bbox = _detect_square_bbox(image)
#         # crop
#         board_crop = _crop_board(image, bbox)
#         # preprocess tiles
#         model_inputs = _preprocess_board_to_tiles(board_crop)
#         # Ensure board_image returned is standardized 512x512 BGR uint8
#         board_image = cv2.resize(board_crop, (BOARD_SIZE_PX, BOARD_SIZE_PX), interpolation=cv2.INTER_AREA)
#         return model_inputs, board_image, bbox
#     except Exception as e:
#         print(f"Error in process_image: {e}")
#         return None



import cv2
import numpy as np
from typing import Tuple, List, Union, Optional

MODEL_SQUARE_SIZE = 64
BOARD_SIZE_PX = MODEL_SQUARE_SIZE * 8  # 512

MIN_BOARD_AREA_RATIO = 0.08   # board must occupy >= 8% of image
MIN_QUAD_SCORE = 0.02         # contour confidence threshold
MIN_EDGE_DENSITY = 0.02       # sanity check after crop

# ============================================================
# Custom Exception
# ============================================================
class NoChessboardDetected(Exception):
    """Raised when no chessboard-like structure is detected."""
    pass

# ============================================================
# Helpers
# ============================================================

_MIN_BOARD_AREA_RATIO = 0.05   # minimum area ratio to consider a contour candidate
_MIN_GRID_AREA_RATIO = 0.06
_MIN_GRID_CANDIDATE_ASPECT_TOL = 0.8
_HOUGH_MIN_LINES = 6

def _pad_image_for_mobile(img: np.ndarray, pad_px: int) -> np.ndarray:
    # replicate border so we don't introduce artificial flat colors
    return cv2.copyMakeBorder(img, pad_px, pad_px, pad_px, pad_px, borderType=cv2.BORDER_REPLICATE)

def _try_contour_detect(gray: np.ndarray, orig_img_area: float, min_area_ratio=_MIN_BOARD_AREA_RATIO):
    # CLAHE + edges -> find quad contours (desktop-style)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    edges = cv2.Canny(enhanced, 40, 140)
    edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    quad_candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area_ratio * orig_img_area:
            continue
        peri = cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)
        if len(approx) == 4:
            x, y, w, h = cv2.boundingRect(approx)
            if w == 0 or h == 0:
                continue
            aspect = w / float(h)
            score = min(aspect, 1.0/aspect) * (area / orig_img_area)
            quad_candidates.append((score, area, (x, y, w, h)))

    if not quad_candidates:
        return None
    quad_candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return quad_candidates[0][2]  # x,y,w,h of best quad

def _try_grid_morph(gray: np.ndarray, h_img: int, w_img: int, orig_img_area: float):
    # adaptive threshold -> morphological open to extract vertical & horizontal lines
    bin_img = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                    cv2.THRESH_BINARY_INV, 15, 5)
    kernel_len = max(8, min(h_img, w_img) // 20)
    vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, kernel_len))
    hor_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (kernel_len, 1))

    vertical = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, vert_kernel)
    horizontal = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, hor_kernel)
    grid = cv2.add(vertical, horizontal)

    contours, _ = cv2.findContours(grid, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < _MIN_GRID_AREA_RATIO * orig_img_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / float(h) if h else 0
        if _MIN_GRID_CANDIDATE_ASPECT_TOL <= aspect <= (1.0 / _MIN_GRID_CANDIDATE_ASPECT_TOL):
            candidates.append((area, (x, y, w, h)))

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]  # x,y,w,h

def _cluster_coords(coords: List[float], tol: float) -> List[float]:
    """Simple 1D clustering: group nearby coordinates and return cluster centers."""
    if not coords:
        return []
    coords = sorted(coords)
    clusters = []
    cur = [coords[0]]
    for v in coords[1:]:
        if v - cur[-1] <= tol:
            cur.append(v)
        else:
            clusters.append(sum(cur) / len(cur))
            cur = [v]
    clusters.append(sum(cur) / len(cur))
    return clusters

def _try_hough_grid(gray: np.ndarray, h_img: int, w_img: int):
    # Canny + HoughLinesP
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    minLineLen = max(20, min(h_img, w_img) // 10)
    maxGap = max(5, min(h_img, w_img) // 40)
    lines = cv2.HoughLinesP(edges, rho=1, theta=np.pi/180, threshold= max(50, (w_img + h_img)//40),
                            minLineLength=minLineLen, maxLineGap=maxGap)
    if lines is None:
        return None

    vert_x = []
    hor_y = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):
        dx = x2 - x1
        dy = y2 - y1
        angle = abs(math.degrees(math.atan2(dy, dx)))
        if angle < 20:  # nearly horizontal
            hor_y.append((y1 + y2) / 2.0)
        elif abs(angle - 90) < 20:  # nearly vertical
            vert_x.append((x1 + x2) / 2.0)

    if len(vert_x) < _HOUGH_MIN_LINES or len(hor_y) < _HOUGH_MIN_LINES:
        return None

    tol_x = max(6, w_img * 0.03)
    tol_y = max(6, h_img * 0.03)
    vx = _cluster_coords(vert_x, tol_x)
    hy = _cluster_coords(hor_y, tol_y)

    # We expect ~9 vertical and 9 horizontal grid lines (including borders); accept 6+ as heuristic
    if len(vx) < 6 or len(hy) < 6:
        return None

    x_min = int(max(0, min(vx)))
    x_max = int(min(w_img, max(vx)))
    y_min = int(max(0, min(hy)))
    y_max = int(min(h_img, max(hy)))

    # make square bbox by expanding smaller dimension
    w = x_max - x_min
    h = y_max - y_min
    side = max(w, h)
    cx = x_min + w // 2
    cy = y_min + h // 2
    half = side // 2
    x1 = max(0, int(cx - half))
    y1 = max(0, int(cy - half))
    # clamp
    x1 = min(x1, w_img - side)
    y1 = min(y1, h_img - side)
    return (x1, y1, int(side), int(side))

def _square_from_bbox(
    x: int, y: int, w: int, h: int,
    img_w: int, img_h: int,
    pad: int = 0
) -> Tuple[int, int, int, int]:
    side = max(w, h) + 2 * pad
    cx = x + w // 2
    cy = y + h // 2
    half = side // 2

    x1 = max(0, cx - half)
    y1 = max(0, cy - half)
    x2 = min(img_w, cx + half)
    y2 = min(img_h, cy + half)

    side = min(x2 - x1, y2 - y1)
    x1 = max(0, cx - side // 2)
    y1 = max(0, cy - side // 2)

    return int(x1), int(y1), int(side), int(side)


def _detect_square_bbox(image: np.ndarray) -> Tuple[int, int, int, int]:
    h_img, w_img = image.shape[:2]
    orig_area = float(h_img * w_img)

    # Convert once
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # 1) First try: contour-based (fast)
    try:
        quad = _try_contour_detect(gray, orig_area, min_area_ratio=_MIN_BOARD_AREA_RATIO)
        if quad is not None:
            x, y, w, h = quad
            return _square_from_bbox(x, y, w, h, w_img, h_img, pad=4)
    except Exception:
        pass

    # 2) Second try: grid morphological (handles internal grid lines and edge-touching boards)
    try:
        candidate = _try_grid_morph(gray, h_img, w_img, orig_area)
        if candidate is not None:
            x, y, w, h = candidate
            return _square_from_bbox(x, y, w, h, w_img, h_img, pad=3)
    except Exception:
        pass

    # 3) Third try: Hough-line based detection (most robust)
    try:
        hough_bbox = _try_hough_grid(gray, h_img, w_img)
        if hough_bbox is not None:
            return hough_bbox
    except Exception:
        pass

    # 4) Try small padding and retry (helps when board touches edges)
    # Pad 5% and 10% and retry the above methods
    for pad_frac in (0.05, 0.12):
        pad_px = int(min(h_img, w_img) * pad_frac)
        padded = _pad_image_for_mobile(image, pad_px)
        gray_p = cv2.cvtColor(padded, cv2.COLOR_BGR2GRAY)
        p_h, p_w = padded.shape[:2]
        p_area = float(p_h * p_w)
        try:
            quad = _try_contour_detect(gray_p, p_area, min_area_ratio=_MIN_BOARD_AREA_RATIO)
            if quad is not None:
                x, y, w, h = quad
                # convert coords back to original by subtracting pad_px
                return _square_from_bbox(x - pad_px, y - pad_px, w, h, w_img, h_img, pad=4)
        except Exception:
            pass
        try:
            cand = _try_grid_morph(gray_p, p_h, p_w, p_area)
            if cand is not None:
                x, y, w, h = cand
                return _square_from_bbox(x - pad_px, y - pad_px, w, h, w_img, h_img, pad=3)
        except Exception:
            pass
        try:
            hough_bbox = _try_hough_grid(gray_p, p_h, p_w)
            if hough_bbox is not None:
                x, y, s, _ = hough_bbox
                return (max(0, x - pad_px), max(0, y - pad_px), s, s)
        except Exception:
            pass

    # nothing found
    raise NoChessboardDetected("No chessboard detected after multi-strategy checks.")

# ============================================================
# Crop & Sanity Check
# ============================================================
def _crop_board(image: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = bbox
    crop = image[y:y + h, x:x + w].copy()

    if crop.size == 0:
        raise NoChessboardDetected("Invalid board crop.")

    return crop


def _board_sanity_check(board_crop: np.ndarray) -> None:
    gray = cv2.cvtColor(board_crop, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 60, 180)
    edge_density = edges.mean() / 255.0

    if edge_density < MIN_EDGE_DENSITY:
        raise NoChessboardDetected("Cropped region lacks chessboard structure.")


# ============================================================
# Tile Preprocessing
# ============================================================
def _preprocess_board_to_tiles(board_image: np.ndarray) -> List[np.ndarray]:
    resized = cv2.resize(board_image, (BOARD_SIZE_PX, BOARD_SIZE_PX))
    tiles = []

    for r in range(8):
        for c in range(8):
            y1 = r * MODEL_SQUARE_SIZE
            x1 = c * MODEL_SQUARE_SIZE
            tile = resized[y1:y1 + MODEL_SQUARE_SIZE, x1:x1 + MODEL_SQUARE_SIZE]
            tile = cv2.cvtColor(tile, cv2.COLOR_BGR2RGB).astype(np.float32)
            tiles.append(tile)

    return tiles


# ============================================================
# Public API
# ============================================================
ImageInput = Union[np.ndarray, bytes, str]

def process_image(
    image_input: ImageInput
) -> Tuple[List[np.ndarray], np.ndarray, Tuple[int, int, int, int]]:

    # Load image
    if isinstance(image_input, np.ndarray):
        image = image_input
    elif isinstance(image_input, bytes):
        nparr = np.frombuffer(image_input, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image bytes.")
    elif isinstance(image_input, str):
        image = cv2.imread(image_input, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Invalid image path.")
    else:
        raise TypeError("Unsupported image input.")

    # Detect board
    bbox = _detect_square_bbox(image)

    # Crop board
    board_crop = _crop_board(image, bbox)

    # Sanity check
    _board_sanity_check(board_crop)

    # Prepare model input
    model_inputs = _preprocess_board_to_tiles(board_crop)
    board_image = cv2.resize(board_crop, (BOARD_SIZE_PX, BOARD_SIZE_PX))

    return model_inputs, board_image, bbox

