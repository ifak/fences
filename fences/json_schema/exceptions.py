
class ParseException(Exception):
    def __init__(self, path: str) -> None:
        self.path = path
