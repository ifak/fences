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
                for transition in node.outgoing_transitions:
                    _resolve(transition.target)
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

        if not isinstance(self, Decision):
            return path_idx, data

        if self.all_transitions:
            result = None
            for transition in self.outgoing_transitions:
                path_idx, result = transition.target._execute(path, path_idx, data)
            # return the result of the last node
            return path_idx, result
        else:
            if path_idx == len(path):
                return path_idx, data
            if not self.outgoing_transitions:
                return path_idx, data
            idx = path[path_idx]
            return self.outgoing_transitions[idx].target._execute(path, path_idx+1, data)

    def _generate(self, result_path: Path, already_reached: Set):
        already_reached.add(id(self))
        self._num_paths += 1
        if not isinstance(self, Decision):
            return
        if not self.outgoing_transitions:
            return

        if self.all_transitions:
            for transition in self.outgoing_transitions:
                transition.target._generate(result_path, already_reached)
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

            result_path.append(selected)
            self.outgoing_transitions[selected].target._generate(result_path, already_reached)

    def _backward(self, path: Path, already_reached: Set) -> "Node":
        already_reached.add(id(self))
        self._num_paths += 1

        if not self.incoming_transitions:
            return self

        predecessor_transition = None
        min_paths = float('inf')
        for transition in self.incoming_transitions:
            if transition.source._num_paths < min_paths:
                min_paths = transition.source._num_paths
                predecessor_transition = transition
        path.append(predecessor_transition.outgoing_idx)
        return predecessor_transition.source._backward(path, already_reached)

    def _forward(self, backward_path: Path, forward_path: Path, visited: Set):
        if len(backward_path) == 0: return
        assert isinstance(self, Decision)
        path_idx = backward_path.pop(-1)
        if self.all_transitions:
            for idx, transition in enumerate(self.outgoing_transitions):
                if idx == path_idx:
                    transition.target._forward(backward_path, forward_path, visited)
                else:
                    transition.target._generate(forward_path, visited)
        else:
            forward_path.append(path_idx)
            self.outgoing_transitions[path_idx].target._forward(backward_path, forward_path, visited)

    @classmethod
    def _generate_paths(self, to_visit: List["Leaf"]) -> Generator[ResultEntry, None, None]:
        while to_visit:
            next = to_visit[0]

            # Generate a path to the root
            backward_path: Path = []
            visited = set()
            root = next._backward(backward_path, visited)

            # Follow path to the target node
            forward_path = []
            root._forward(backward_path, forward_path, visited)

            # Yield
            yield ResultEntry(next, forward_path, next.is_valid)

            # Remove the visited nodes
            path_idx = 0
            while path_idx < len(to_visit):
                if id(to_visit[path_idx]) in visited:
                    del to_visit[path_idx]
                else:
                    path_idx += 1

    def generate_paths(self) -> Generator[ResultEntry, None, None]:

        leafs: List[Leaf] = []

        # Reset counter
        for node in self.items():
            node._num_paths = 0
            if isinstance(node, Leaf):
                leafs.append(node)

        yield from Node._generate_paths(leafs)


class Leaf(Node):
    def __init__(self, id: str, is_valid: bool) -> None:
        super().__init__(id)
        self.is_valid = is_valid


class OutgoingTransition:
    def __init__(self, target: Node, inverting: bool = False) -> None:
        self.target = target
        self.inverting = inverting


class IncomingTransition:
    def __init__(self, source: "Decision", idx: int) -> None:
        self.source = source
        self.outgoing_idx = idx

    def outgoing_transition(self) -> OutgoingTransition:
        return self.source.outgoing_transitions[self.outgoing_idx]


class Decision(Node):
    def __init__(self, id: str, all_transitions: bool = False) -> None:
        super().__init__(id)
        self.all_transitions = all_transitions
        self.outgoing_transitions: List[OutgoingTransition] = []

    def add_transition(self, target: Node, inverting: bool = False):
        target.incoming_transitions.append(
            IncomingTransition(self, len(self.outgoing_transitions))
        )
        self.outgoing_transitions.append(
            OutgoingTransition(target, inverting)
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
