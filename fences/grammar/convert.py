from typing import List, Optional
from fences.core.node import Node, Leaf, Node, Decision, Reference, NoOpDecision
from .types import Grammar, Terminal, NonTerminal, RightHandSide, Concatenation
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
    for nt, productions in grammar.items():
        node = NoOpDecision(nt.name, False)
        _convert(node, productions)
        all_nodes.append(node)

    root = CreateInput(None, True)
    root.add_transition(Reference(None, start))
    root.add_transition(FetchOutput())
    root.resolve(all_nodes)

    return root


def _convert(root: Decision, productions: List[RightHandSide]):
    for production in productions:
        if isinstance(production, Terminal):
            root.add_transition(AppendString(True, production.value))
        elif isinstance(production, str):
            root.add_transition(AppendString(True, production))
        elif isinstance(production, NonTerminal):
            root.add_transition(Reference(None, production.name))
        elif isinstance(production, Concatenation):
            sub_root = NoOpDecision(None, True)
            _convert(sub_root, production.elements)
            root.add_transition(sub_root)
        else:
            raise GrammarException(f"Unknown type in grammar: {production}")
