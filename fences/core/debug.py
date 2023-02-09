from .node import Node, Decision
from .exception import GraphException

class CheckGraphException(GraphException):
    pass

def check(self: Node):
    """
    Checks, if the node is consistent
    (for debugging purpose)
    """
    for node in self.items():
        for transition in node.incoming_transitions:
            idx = transition.outgoing_idx
            if not isinstance(transition.source, Decision):
                raise CheckGraphException(f"Source of incoming transition must be a Decision")
            if idx >= len(transition.source.outgoing_transitions):
                raise CheckGraphException(f"Outgoing index out of range")
            actual = transition.source.outgoing_transitions[idx].target
            if node is not actual:
                raise CheckGraphException(f"Invalid transition at ${node.id}: != {actual.id}")
        if isinstance(node, Decision):
            for idx, transition in enumerate(node.outgoing_transitions):
                for t in transition.target.incoming_transitions:
                    if t.source is node:
                        if t.outgoing_idx != idx:
                            raise CheckGraphException(f"Invalid transition")
                        return
            raise CheckGraphException(f"No incoming transition")
