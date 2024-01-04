from typing import Union
from fences.core.exception import JsonPointerException


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

    @classmethod
    def from_string(self, value: str) -> "JsonPointer":
        if value == '#/' or value == '#':
            return JsonPointer()

        if not value.startswith('#/'):
            raise JsonPointerException(f"Only local pointers are supported, got {value}")
        value = value[2:]
        return JsonPointer(value.split("/"))

    def is_root(self) -> bool:
        return len(self.elements) == 0

    def lookup(self, data: any, index: int = 0) -> any:
        if index > len(self.elements):
            raise JsonPointerException("Out of range")
        if index == len(self.elements):
            return data
        if isinstance(data, dict):
            key = self.elements[index]
            try:
                value = data[key]
            except KeyError:
                raise JsonPointerException(f"{key} not in data")
            return self.lookup(value, index+1)
        elif isinstance(data, list):
            try:
                i = int(self.elements[index])
            except ValueError:
                raise JsonPointerException(
                    f"{self.elements[index]} is not an integer for array lookup")
            try:
                value = data[i]
            except IndexError:
                raise JsonPointerException(f"Index not in array")
            return self.lookup(data[i], index+1)
        else:
            raise JsonPointerException(f"Cannot lookup in {data}")
