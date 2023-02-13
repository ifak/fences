from enum import Enum
from .exception import GraphException, ResolveReferenceException
from typing import List, Optional, Generator, Set, Dict, Tuple
from dataclasses import dataclass, field

Path = List[int]


@dataclass
class ResultEntry:
    target: "Leaf"
    path: Path
    is_valid: bool


class Node:

    def __init__(self, id: Optional[str] = None) -> None:
        self.id = id
        self.incoming_transitions: List["IncomingTransition"] = []
        self._num_paths: int = 0

    def apply(self, data: any) -> any:
        """
        Applies to node's operation to the given data
        (Meant to be overridden)
        """
        raise NotImplemented()  # pragma: no cover

    def description(self) -> Optional[str]:
        """
        Returns a human readable description of the node' apply() function
        (Meant to be overridden)
        """
        return None

    def items(self) -> Generator["Node", None, None]:
        """
        Iterates over the node and all it's children recursively
        """
        already_visited: Set[Node] = set()
        yield from self._items(already_visited)

    def _items(self, already_visited: Set["Node"]) -> Generator["Node", None, None]:
        if id(self) in already_visited:
            return
        already_visited.add(id(self))
        yield self

    def target(self, nodes_by_id: Dict[str, "Node"]) -> "Node":
        """
        Returns the node's target, which is the referred node in case of a Reference or the node itself, otherwise
        """
        return self

    def resolve(self, nodes: List["Node"]) -> "Node":
        """
        Replace all Reference instances with the actual nodes they are pointing to.
        Returns the root - this is a new value if the root itself was a ReferenceNode.
        """

        # Collect references
        nodes_by_id: Dict[str, Node] = {}

        def insert(node: Node):
            if node.id and node.id in nodes_by_id:
                raise ResolveReferenceException(f"id '{node.id}' already exists")
            nodes_by_id[node.id] = node
        for node in nodes:
            for n in node.items():
                insert(n)
        for n in self.items():
            insert(n)

        # Get actual root
        root = self.target(nodes_by_id)

        # Resolve references
        visited = set()

        def _resolve(node: Node):
            if id(node) in visited:
                return
            visited.add(id(node))
            if isinstance(node, Decision):
                for idx, transition in enumerate(node.outgoing_transitions):
                    next_node = transition.target
                    if isinstance(next_node, Reference):
                        target_node = next_node.target(nodes_by_id)
                        transition.target = target_node
                        target_node.incoming_transitions.append(
                            IncomingTransition(node, idx)
                        )
                        next_node = target_node
                    _resolve(next_node)
        _resolve(root)
        return root

    def execute(self, path: Path, data = None) -> any:
        """
        Executes a path on the node
        """
        idx, result = self._execute(path, 0, data)
        if idx != len(path):
            raise GraphException("Path not fully consumed")
        return result

    def _execute(self, path: Path, path_idx: int, data: any) -> Tuple[int, any]:
        if path_idx > len(path):
            raise GraphException(f"path_idx ({path_idx}) > len(path) ({len(path)})")

        data = self.apply(data)

        if path_idx == len(path):
            return path_idx, data

        if not isinstance(self, Decision):
            return path_idx, data

        if self.operation == Operation.AND:
            result = None
            for transition in self.outgoing_transitions:
                path_idx, result = transition.target._execute(path, path_idx, data)
            # return the result of the last node
            return path_idx, result
        else:
            if not self.outgoing_transitions:
                return path_idx, data
            idx = path[path_idx]
            return self.outgoing_transitions[idx].target._execute(path, path_idx+1, data)

    def _forward(self, path: Path, already_reached: Set):
        already_reached.add(id(self))
        self._num_paths += 1
        if not isinstance(self, Decision):
            return
        if not self.outgoing_transitions:
            return

        if self.operation == Operation.AND:
            for transition in self.outgoing_transitions:
                transition.target._forward(path, already_reached)
        else:
            selected = None
            min_paths = float('inf')
            for idx, transition in enumerate(self.outgoing_transitions):
                target = transition.target
                if target._num_paths < min_paths:
                    if isinstance(target, Leaf) and not target.is_valid:
                        continue
                    selected = idx
                    min_paths = target._num_paths
            if selected is None:
                raise Exception("LOOP detected!")

            path.append(selected)
            self.outgoing_transitions[selected].target._forward(
                path, already_reached)

    def _backward(self, reverse_path: Path, already_reached: Set):
        already_reached.add(id(self))
        self._num_paths += 1
        if not self.incoming_transitions:
            return

        selected = None
        predecessor = None
        min_paths = float('inf')
        for transition in self.incoming_transitions:
            if transition.source._num_paths < min_paths:
                selected = transition.outgoing_idx
                min_paths = transition.source._num_paths
                predecessor = transition.source
        if predecessor.operation == Operation.AND:
            sub_reverse_path = []
            for transition in reversed(predecessor.outgoing_transitions):
                if transition.target != self:
                    sub_visited = set()
                    sub_path = []
                    transition.target._forward(sub_path, already_reached)
                    for i in sub_visited:
                        already_reached.add(i)
                    # sub_reverse_path.insert(sub_reverse_path.end(), sub_path.rbegin(), sub_path.rend());
                    sub_reverse_path.extend(reversed(sub_path))
                else:
                    # sub_reverse_path.insert(sub_reverse_path.end(), reverse_path.begin(), reverse_path.end());
                    sub_reverse_path.extend(reverse_path)
            # TODO: this does not seem very efficient
            reverse_path.clear()
            reverse_path.extend(sub_reverse_path)
        else:
            reverse_path.append(selected)
        predecessor._backward(reverse_path, already_reached)

    @classmethod
    def _generate_paths(self, to_visit: List["Node"], is_valid: bool) -> Generator[ResultEntry, None, None]:
        while to_visit:
            next = to_visit[0]

            # Generate a path to the to start node
            path: Path = []
            visited = set()
            next._forward(path, visited)
            path.reverse()
            next._backward(path, visited)
            path.reverse()
            yield ResultEntry(next, path, is_valid)

            # Remove the visited nodes
            idx = 0
            while idx < len(to_visit):
                if id(to_visit[idx]) in visited:
                    del to_visit[idx]
                else:
                    idx += 1

    def generate_paths(self) -> Generator[ResultEntry, None, None]:

        invalid_to_visit: List[Node] = []
        valid_to_visit: List[Node] = []

        # Reset counter
        for node in self.items():
            node._num_paths = 0
            if isinstance(node, Leaf):
                if node.is_valid:
                    valid_to_visit.append(node)
                else:
                    invalid_to_visit.append(node)

        # valid_to_visit.sort(by_reachability);
        yield from Node._generate_paths(valid_to_visit, True)

        # invalid_to_visit.sort(by_reachability);
        yield from Node._generate_paths(invalid_to_visit, False)


class Leaf(Node):
    def __init__(self, id: str, is_valid: bool) -> None:
        super().__init__(id)
        self.is_valid = is_valid


class Operation(Enum):
    OR = 1
    AND = 2


class OutgoingTransition:
    def __init__(self, target: Node) -> None:
        self.target = target


class IncomingTransition:
    def __init__(self, source: "Decision", idx: int) -> None:
        self.source = source
        self.outgoing_idx = idx

    def outgoing_transition(self) -> OutgoingTransition:
        return self.source.outgoing_transitions[self.outgoing_idx]


class Decision(Node):
    def __init__(self, id: str, operation=Operation.OR) -> None:
        super().__init__(id)
        self.operation = operation
        self.outgoing_transitions: List[OutgoingTransition] = []

    def add_transition(self, target: Node):
        target.incoming_transitions.append(
            IncomingTransition(self, len(self.outgoing_transitions))
        )
        self.outgoing_transitions.append(
            OutgoingTransition(target)
        )

    def _items(self, already_visited: Set["Node"]) -> Generator["Node", None, None]:
        if id(self) in already_visited:
            return
        already_visited.add(id(self))
        yield self
        for transition in self.outgoing_transitions:
            yield from transition.target._items(already_visited)


class Reference(Node):
    def __init__(self, id: str, reference: str) -> None:
        super().__init__(id)
        self.reference = reference

    def target(self, nodes_by_id: Dict[str, "Node"]) -> Node:
        try:
            return nodes_by_id[self.reference].target(nodes_by_id)
        except KeyError as e:
            raise ResolveReferenceException(f"Unknown reference '{e}'")


class NoOpDecision(Decision):
    def apply(self, data: any) -> any:
        return data

    def description(self) -> Optional[str]:
        return "(Do nothing)"

class NoOpLeaf(Leaf):
    def apply(self, data: any) -> any:
        return data

    def description(self) -> Optional[str]:
        return "(do nothing)"
