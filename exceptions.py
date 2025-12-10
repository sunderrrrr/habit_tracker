class InternalError(Exception):
    pass

class DBError(InternalError):
    pass

class TGBotError(InternalError):
    pass