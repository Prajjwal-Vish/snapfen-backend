import cv2
import numpy as np
from pathlib import Path
import os
import chess

# Import the processor from your existing script
# We assume chessboard_snipper.py is in the same directory
from chessboard_snipper import process_image 

# --- Configuration ---
SOURCE_THEMES_DIR = Path(r"C:\Users\GFG19761\Desktop\img_to_fen\themes-chesscom")
OUTPUT_DATA_DIR = Path(r"C:\Users\GFG19761\Desktop\img_to_fen\new-2") # This is the folder train_model.py reads from

# The standard FEN starting position
STARTING_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR"

# We need to map the FEN character back to our folder names
# This is the REVERSE of the FEN_MAP in your other script
CHAR_TO_DIR_MAP = {
    'r': 'dark_rook', 'n': 'dark_knight', 'b': 'dark_bishop', 'q': 'dark_queen', 'k': 'dark_king', 'p': 'dark_pawn',
    'R': 'light_rook', 'N': 'light_knight', 'B': 'light_bishop', 'Q': 'light_queen', 'K': 'light_king', 'P': 'light_pawn',
}

def create_dirs():
    """Creates the 14 output directories if they don't exist."""
    OUTPUT_DATA_DIR.mkdir(exist_ok=True)
    for dir_name in CHAR_TO_DIR_MAP.values():
        (OUTPUT_DATA_DIR / dir_name).mkdir(exist_ok=True)
    (OUTPUT_DATA_DIR / "empty_dark").mkdir(exist_ok=True)
    (OUTPUT_DATA_DIR / "empty_light").mkdir(exist_ok=True)

def unroll_fen(fen_position: str) -> list:
    """
    Converts a FEN position string (e.g., 'rnbqkbnr/p...') 
    into a 64-item list of class names.
    """
    class_name_list = []
    fen_ranks = fen_position.split('/')
    
    for r, rank_str in enumerate(fen_ranks):
        file_index = 0
        for char in rank_str:
            if char.isdigit():
                num_empty = int(char)
                for i in range(num_empty):
                    # Check square color for empty squares
                    # Standard board: (row + col) % 2 == 0 is a LIGHT square.
                    if (r + file_index) % 2 == 0:
                        class_name_list.append("empty_light")
                    else:
                        class_name_list.append("empty_dark")
                    file_index += 1
            else:
                class_name_list.append(CHAR_TO_DIR_MAP[char])
                file_index += 1
    return class_name_list

def main():
    print("--- Starting Theme Cropping Script ---")
    create_dirs()
    
    # 1. Get the 64 labels from the starting FEN
    try:
        fen_labels = unroll_fen(STARTING_FEN)
        if len(fen_labels) != 64:
            raise Exception("FEN unroll failed.")
    except Exception as e:
        print(f"Error: Could not parse FEN. {e}")
        return

    # 2. Find all images in the theme_boards folder
    theme_images = list(SOURCE_THEMES_DIR.glob("*.png"))
    theme_images.extend(list(SOURCE_THEMES_DIR.glob("*.jpg")))
    theme_images.extend(list(SOURCE_THEMES_DIR.glob("*.jpeg")))

    if not theme_images:
        print(f"Error: No images found in '{SOURCE_THEMES_DIR}'.")
        print("Please add your 13 theme images to that folder.")
        return

    print(f"Found {len(theme_images)} theme images to process.")
    total_cropped = 0

    # 3. Loop through each theme image
    for img_path in theme_images:
        print(f"\nProcessing theme: {img_path.name}...")
        
        # 4. Use your robust 'process_image' function
        # It handles detection, cropping, and gives us the 64 tiles
        processed_data = process_image(str(img_path))
        
        if processed_data is None:
            print(f"  > Skipped: Could not find board in {img_path.name}.")
            continue
            
        model_inputs, _, _ = processed_data
        
        # 5. Save all 64 tiles to the correct folders
        cropped_this_theme = 0
        for i in range(64):
            square_label = fen_labels[i]
            
            # --- OPTIMIZATION LOGIC ---
            is_piece = not square_label.startswith("empty_")
            # We only take a *sample* of empty squares (e.g., from Rank 3, indices 16-23)
            is_sample_empty = square_label.startswith("empty_") and (i >= 16 and i < 24)
            
            if is_piece or is_sample_empty:
                # This is a piece OR one of our sample empty squares
                square_image_data = model_inputs[i] # This is float (0-1) and RGB
                
                # Convert back to OpenCV format (uint8 0-255 and BGR) for saving
                square_image_uint8 = (square_image_data * 255.0).astype(np.uint8)
                square_image_bgr = cv2.cvtColor(square_image_uint8, cv2.COLOR_RGB2BGR)
                
                # --- NEW: File Exists Check ---
                base_name = f"{img_path.stem}_square_{i}"
                extension = ".png"
                save_dir = OUTPUT_DATA_DIR / square_label
                
                save_path = save_dir / f"{base_name}{extension}"
                
                count = 1
                while save_path.exists():
                    # File already exists, append a counter
                    save_name = f"{base_name}_{count}{extension}"
                    save_path = save_dir / save_name
                    count += 1
                # --- END NEW ---
                
                cv2.imwrite(str(save_path), square_image_bgr)
                total_cropped += 1
                cropped_this_theme += 1
            # --- END OPTIMIZATION ---
            
        print(f"  > Success: Cropped and saved {cropped_this_theme} squares.")

    print(f"\n--- Batch Cropping Complete ---")
    print(f"Added {total_cropped} new images to the '{OUTPUT_DATA_DIR}' folder.")
    print("You can now run 'python train_model.py' to retrain your model.")

if __name__ == "__main__":
    main()