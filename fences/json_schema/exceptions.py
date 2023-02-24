from fences.core.exception import ParseException
from .json_pointer import JsonPointer

class JsonSchemaException(ParseException):
    def __init__(self, message: str, json_pointer: JsonPointer) -> None:
        super().__init__(message)
        self.json_pointer = json_pointer
