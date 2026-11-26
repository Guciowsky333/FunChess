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


class TheGameIsFinished(Exception):
    pass


class TooLongMessage(Exception):
    pass


class TheGameIsNotOver(Exception):
    pass


class PlayersAlreadyInGame(Exception):
    pass


class TheRematchAlreadyAccepted(Exception):
    pass


class TheRematchOfferNotSent(Exception):
    pass


class TheRematchOfferAlreadySent(Exception):
    pass


class NotOpponentRematchOffer(Exception):
    pass


class TheRematchOfferAlreadyRejected(Exception):
    pass
