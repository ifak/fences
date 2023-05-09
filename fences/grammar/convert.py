from typing import List
from fences.core.node import Node, Leaf, Node, Decision, Reference, NoOpDecision
from .types import Grammar, Terminal, NonTerminal, RightHandSide, Concatenation, CharacterRange
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
    for non_terminal, productions in grammar.items():
        node = NoOpDecision(non_terminal.name, False)
        for production in productions:
            node.add_transition(_convert(production))
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

def _convert(production: RightHandSide) -> Node:
    if isinstance(production, Terminal):
        return _convert_terminal(production)
    elif isinstance(production, str):  # shorthand version of above
        return _convert_terminal(Terminal(production))
    elif isinstance(production, NonTerminal):
        return _convert_non_terminal(production)
    elif isinstance(production, Concatenation):
        return _convert_concatenation(production)
    elif isinstance(production, CharacterRange):
        return _convert_character_range(production)
    else:
        raise GrammarException(f"Unknown type in grammar: {production}")
