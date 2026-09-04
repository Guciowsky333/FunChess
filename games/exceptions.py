class InvalidAction(Exception):
    pass


class DrawOfferAlreadyExists(Exception):
    pass


class DrawOfferNotFound(Exception):
    pass


class NotOpponentDrawOffer(Exception):
    pass


class ExceededTimeError(Exception):
    pass


class PlayerDoesNotBelongToGameError(Exception):
    pass


class GameDoesNotExist(Exception):
    pass


class InvalidMoveFormat(Exception):
    pass


class IllegalChessMove(Exception):
    pass
