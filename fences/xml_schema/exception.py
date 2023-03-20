from fences.core.exception import ParseException
from .xpath import NormalizedXPath

class XmlSchemaException(ParseException):

    def __init__(self, message: str, path: NormalizedXPath) -> None:
        super().__init__(f"{message} at {path}")
        self.path = path
