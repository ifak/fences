from typing import Union

class JsonPointer:

    def __init__(self, elements=None) -> None:
        self.elements = elements or []

    def __add__(self, other: Union[str, int]) -> "JsonPointer":
        if isinstance(other, str):
            return JsonPointer(self.elements + [other])
        if isinstance(other, int):
            return JsonPointer(self.elements + [str(other)])
        raise NotImplementedError()

    def __str__(self) -> str:
        return '#/' + '/'.join(self.elements)

    def is_root(self) -> bool:
        return len(self.elements) == 0
