import chess

# This dictionary maps your *exact* folder names to FEN characters.
# This is CRITICAL. '1' represents any empty square.
FEN_MAP = {
    'dark_rook': 'r',
    'dark_knight': 'n',
    'dark_bishop': 'b',
    'dark_queen': 'q',
    'dark_king': 'k',
    'dark_pawn': 'p',
    'light_rook': 'R',
    'light_knight': 'N',
    'light_bishop': 'B',
    'light_queen': 'Q',
    'light_king': 'K',
    'light_pawn': 'P',
    'empty_dark': '1',  # <-- Both empty types map to '1'
    'empty_light': '1'  # <-- Both empty types map to '1'
}

def assemble_fen_from_predictions(predictions: list) -> str:
    """
    Converts a list of 64 predicted class names into a FEN *position string*.
    ASSUMES the list is in the correct FEN order (Rank 8 -> Rank 1).
    """
    fen_ranks = []
    for i in range(0, 64, 8):
        rank_predictions = predictions[i : i+8]
        fen_rank = ""
        empty_count = 0
        for pred_name in rank_predictions:
            # Get FEN char, or '?' if not found (for debugging)
            fen_char = FEN_MAP.get(pred_name, '?') 
            
            if fen_char == '1':
                # It's an empty square, increment the counter
                empty_count += 1
            else:
                # It's a piece.
                # First, if we have a count of empty squares, add it.
                if empty_count > 0:
                    fen_rank += str(empty_count)
                    empty_count = 0
                # Now, add the piece character
                fen_rank += fen_char
        
        # After finishing a rank, add any remaining empty_count
        if empty_count > 0:
            fen_rank += str(empty_count)
            
        fen_ranks.append(fen_rank)
        
    # Return *only* the position part of the FEN
    return "/".join(fen_ranks)

def reverse_rank(rank_str: str) -> str:
    """Reverse files in a single rank string (mirrors horizontally)."""
    # Use python-chess to expand (e.g., '8' -> '11111111')
    expanded = ""
    for char in rank_str:
        if char.isdigit():
            expanded += '1' * int(char)
        else:
            expanded += char
    # Reverse the expanded string and then re-compress
    reversed_expanded = expanded[::-1]
    
    # Re-compress
    new_rank_str = ""
    empty_count = 0
    for char in reversed_expanded:
        if char == '1':
            empty_count += 1
        else:
            if empty_count > 0:
                new_rank_str += str(empty_count)
                empty_count = 0
            new_rank_str += char
    if empty_count > 0:
        new_rank_str += str(empty_count)
        
    return new_rank_str

def black_perspective_fen(position_string: str) -> str:
    """
    Performs a full 180-degree flip on a FEN position string
    by reversing ranks (vertical) and reversing files (horizontal).
    """
    # Normalize the FEN string first (e.g., 111p4 -> 3p4)
    try:
        board = chess.Board(position_string + " w KQkq - 0 1")
        position = board.fen().split(' ')[0] 
    except Exception:
        # Fallback if python-chess fails (e.g., on '?' chars)
        position = position_string

    ranks = position.split('/')
    
    # Vertical flip: reverse rank order
    ranks = ranks[::-1] 
    
    # Horizontal flip: reverse files in each
    reversed_ranks = [reverse_rank(r) for r in ranks]
    
    return '/'.join(reversed_ranks)
