from typing import Dict, Union, List, Optional
from .exceptions import CharacterRangeException

RightHandSide = Union["NonTerminal", "Terminal"]


class Concatenation:

    def __init__(self) -> None:
        self.elements: List[RightHandSide] = []

    def __add__(self, other) -> "Concatenation":
        result = Concatenation()
        result.elements = self.elements.copy()
        result.elements.append(other)
        return result


class NonTerminal():
    def __init__(self, name: str):
        self.name = name

    def __add__(self, other: RightHandSide) -> Concatenation:
        return Concatenation() + self + other


class Terminal():
    def __init__(self, value: str):
        self.value = value

    def __add__(self, other: RightHandSide) -> Concatenation:
        return Concatenation() + self + other


class CharacterRange():

    UNICODE_MAX = 0x10FFF

    def __init__(self, start: Optional[str], stop: Optional[str]):
        if start is None:
            self.start = 0
        else:
            if len(start) != 1:
                raise CharacterRangeException(
                    f"start of range must have len 1, has {len(start)}")
            self.start = ord(start)

        if stop is None:
            self.stop = CharacterRange.UNICODE_MAX
        else:
            if len(stop) != 1:
                raise CharacterRangeException(
                    f"stop of range must have len 1, has {len(stop)}")
            self.stop = ord(stop)

        if self.start > self.stop:
            raise CharacterRangeException(
                f"stop must be after start")


Grammar = Dict[NonTerminal, List[RightHandSide]]
