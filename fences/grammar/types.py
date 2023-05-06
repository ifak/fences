from typing import Dict, Union, List

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


Grammar = Dict[NonTerminal, List[RightHandSide]]
