import chess
from rest_framework import serializers

from accounts.models import CustomUser
from games.models import Game, Move


def process_move(game: Game, user: CustomUser, move_uci: str) -> Move:
    """
    Checks if provided move is valid at current chess position
    (based on current fen) if yes create it.
    Also checks which player has turn right now
    """
    ply_number = game.moves.count() + 1

    # If it is the first move we take initial chess position
    if ply_number == 1:
        board = chess.Board()

    # If it is not the first move we take position from the last move at provided game
    else:
        last_move = game.moves.order_by("-ply_number").first()
        fen = last_move.resulting_fen
        board = chess.Board(fen)

    # if ply_number is odd it means that it is white player turn, and only they can make the move
    if ply_number % 2 == 1:
        if game.white_player != user:
            raise serializers.ValidationError("Now is white_player turn")

    # if ply_number is even it means that it is black player turn, and only they can make the move
    if ply_number % 2 == 0:
        if game.black_player != user:
            raise serializers.ValidationError("Now is black_player turn")

    try:
        move = chess.Move.from_uci(move_uci)
    except (ValueError, chess.InvalidMoveError):
        raise serializers.ValidationError("Invalid move format")

    # Checks if the move is illegal
    if move not in board.legal_moves:
        raise serializers.ValidationError("Illegal chess move")

    from_square = chess.square_name(move.from_square)
    to_square = chess.square_name(move.to_square)
    piece = (board.piece_at(move.from_square)).symbol().upper()
    promotion = chess.piece_symbol(move.promotion).upper() if move.promotion else None
    board.push(move)
    resulting_fen = board.fen()

    return Move.objects.create(
        game=game,
        player=user,
        ply_number=ply_number,
        from_square=from_square,
        to_square=to_square,
        piece=piece,
        promotion=promotion,
        resulting_fen=resulting_fen,
    )
