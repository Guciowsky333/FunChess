class InvalidBody(Exception):
    pass


class TimeControlNotExist(Exception):
    pass


class AlreadySearching(Exception):
    pass


class YouAlreadyHaveGameInProgress(Exception):
    pass


class YouAreTemporaryBanned(Exception):
    def __init__(self, expires_at):
        self.expires_at = expires_at
        super().__init__(f"You are temporary banned until {expires_at}")
