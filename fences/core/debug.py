from .node import Node, Decision
from .exception import FencesException

class ConsistencyException(FencesException):
    pass

def check_consistency(root: Node):
    """
    Checks, if the node is consistent
    (for debugging purpose)
    """
    # check if all transitions are wired up correctly
    for node in root.items():

        # check incoming transitions
        for transition in node.incoming_transitions:
            idx = transition.outgoing_idx
            if not isinstance(transition.source, Decision):
                raise ConsistencyException(f"Source of incoming transition must be a Decision")
            if idx >= len(transition.source.outgoing_transitions):
                raise ConsistencyException(f"Outgoing index out of range")
            actual = transition.source.outgoing_transitions[idx].target
            if node is not actual:
                raise ConsistencyException(f"Invalid transition at ${node.id}: != {actual.id}")

        # check outgoing transitions
        if isinstance(node, Decision):
            for idx, transition in enumerate(node.outgoing_transitions):
                found = None
                for t in transition.target.incoming_transitions:
                    if t.outgoing_idx == idx and t.source is node:
                        found = True
                        break
                if not found:
                    raise ConsistencyException(f"No corresponding incoming transition")

    # check if all ids are unique
    all_ids = set()
    for node in root.items():
        if node.id is not None:
            if node.id in all_ids:
                raise ConsistencyException(f"Duplicate id '{node.id}'")
            all_ids.add(node.id)

    # check that each node has at least one valid leaf
    # The path generation would fail otherwise
    # TODO
