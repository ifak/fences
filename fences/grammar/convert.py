from typing import List
from fences.core.node import Node, Leaf, Node, Decision, Reference, NoOpDecision, NoOpLeaf
from .types import Grammar, Terminal, NonTerminal, RightHandSide, Concatenation, CharacterRange, Alternative, Repetition
from .exceptions import GrammarException
import string


class CreateInput(Decision):
    def description(self):
        return "Create Input"

    def apply(self, data: any) -> any:
        return []


class FetchOutput(Leaf):
    def __init__(self) -> None:
        super().__init__(None, True)

    def description(self):
        return "Fetch Output"

    def apply(self, data: list) -> any:
        return "".join(data)


class AppendString(Leaf):
    def __init__(self, is_valid: bool, string: str) -> None:
        super().__init__(None, is_valid)
        self.string = string

    def apply(self, data: list) -> any:
        data.append(self.string)
        return data

    def mask(self, s: str) -> str:
        allowed = string.ascii_letters + string.digits
        return "".join([
            (i if i in allowed else f"chr({ord(i)})") for i in s
        ])

    def description(self) -> str:
        return f"Append {self.mask(self.string)}"


def convert(grammar: Grammar, start='start') -> Node:
    if isinstance(start, NonTerminal):
        start = start.name

    all_nodes: List[Node] = []
    for non_terminal, rhs in grammar.items():
        node = NoOpDecision(non_terminal.name, False)
        node.add_transition(_convert(rhs))
        all_nodes.append(node)

    root = CreateInput(None, True)
    root.add_transition(Reference(None, start))
    root.add_transition(FetchOutput())
    root.resolve(all_nodes)
    root.optimize()

    return root


def _convert_terminal(terminal: Terminal) -> Node:
    return AppendString(True, terminal.value)


def _convert_non_terminal(non_terminal: NonTerminal) -> Node:
    return Reference(None, non_terminal.name)


def _convert_concatenation(concatenation: Concatenation) -> Node:
    sub_root = NoOpDecision(None, True)
    for i in concatenation.elements:
        sub_root.add_transition(_convert(i))
    return sub_root


def _convert_character_range(char_range: CharacterRange) -> Node:
    sub_root = NoOpDecision(None, False)

    # lower bound
    sub_root.add_transition(AppendString(True, chr(char_range.start)))

    # upper bound
    sub_root.add_transition(AppendString(True, chr(char_range.stop)))

    return sub_root


def _convert_alternative(elements: List[RightHandSide]) -> Node:
    root = NoOpDecision(None, False)
    for element in elements:
        root.add_transition(_convert(element))
    return root


def _convert_repetition(repetition: Repetition) -> Node:
    root = NoOpDecision(None, False)
    child = _convert(repetition.element)

    if repetition.start == 0:
        root.add_transition(NoOpLeaf(None, True))
    else:
        lower = NoOpDecision(None, True)
        for _ in range(repetition.start):
            lower.add_transition(child)
        root.add_transition(lower)

    if repetition.start != repetition.stop:
        if repetition.stop is None:
            stop = repetition.start + 3
        else:
            stop = repetition.stop
        upper = NoOpDecision(None, True)
        for _ in range(stop):
            upper.add_transition(child)
        root.add_transition(upper)

    return root


def _convert(rhs: RightHandSide) -> Node:
    if isinstance(rhs, Terminal):
        return _convert_terminal(rhs)
    elif isinstance(rhs, str):  # shorthand version of above
        return _convert_terminal(Terminal(rhs))
    elif isinstance(rhs, NonTerminal):
        return _convert_non_terminal(rhs)
    elif isinstance(rhs, Concatenation):
        return _convert_concatenation(rhs)
    elif isinstance(rhs, CharacterRange):
        return _convert_character_range(rhs)
    elif isinstance(rhs, Alternative):
        return _convert_alternative(rhs.elements)
    elif isinstance(rhs, list):  # shorthand version of above
        return _convert_alternative(rhs)
    elif isinstance(rhs, Repetition):
        return _convert_repetition(rhs)
    else:
        raise GrammarException(f"Unknown type in grammar: {rhs}")
