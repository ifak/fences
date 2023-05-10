from typing import Dict, List, Optional, Tuple
from .exceptions import CharacterRangeException


class RightHandSide:
    def __add__(self, other: "RightHandSide") -> "Concatenation":
        return Concatenation([self, other])

    def __radd__(self, other: "RightHandSide") -> "Concatenation":
        return Concatenation([other, self])

    def __or__(self, other: "RightHandSide") -> "Alternative":
        return Alternative([self, other])

    def __ror__(self, other: "RightHandSide") -> "Alternative":
        return Alternative([other, self])

    def __mul__(self, other: Tuple[int, Optional[int]]) -> "Repetition":
        assert len(other) == 2
        return Repetition(self, other[0], other[1])

# Support for +


class Concatenation(RightHandSide):

    def __init__(self, elements: List[RightHandSide]) -> None:
        self.elements = elements

    def __add__(self, other: RightHandSide) -> "Concatenation":
        if isinstance(other, Concatenation):
            return Concatenation(self.elements + other.elements)
        else:
            return Concatenation(self.elements + [other])


# Support for * (start, stop)


class Repetition(RightHandSide):
    def __init__(self, element: RightHandSide, start: int, stop: Optional[int]):
        self.element = element
        self.start = start
        self.stop = stop


# Support for |

class Alternative(RightHandSide):
    def __init__(self, elements: List[RightHandSide]):
        self.elements = elements

    def __or__(self, other: RightHandSide) -> "Alternative":
        if isinstance(other, Alternative):
            return Alternative(self.elements + other.elements)
        else:
            return Alternative(self.elements + [other])


# Other

class NonTerminal(RightHandSide):
    def __init__(self, name: str):
        self.name = name


class Terminal(RightHandSide):
    def __init__(self, value: str):
        self.value = value


class CharacterRange(RightHandSide):

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


Grammar = Dict[NonTerminal, RightHandSide]
