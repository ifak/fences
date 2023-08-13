from .exception import ResolveReferenceException, InternalException
from typing import List, Optional, Generator, Set, Dict, Tuple
from dataclasses import dataclass

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
        self._has_valid_successors: False
        self._has_invalid_successors: False

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
                raise ResolveReferenceException(
                    f"id '{node.id}' exists multiple times", node.id)
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

    def execute(self, path: Path, data=None) -> any:
        """
        Executes a path on the node
        """
        idx, result = self._execute(path, 0, data)
        if idx != len(path):  # pragma: no cover
            raise InternalException("Path not fully consumed")
        return result

    def _execute(self, path: Path, path_idx: int, data: any) -> Tuple[int, any]:
        if path_idx > len(path):  # pragma: no cover
            raise InternalException(
                f"path_idx ({path_idx}) > len(path) ({len(path)})")

        data = self.apply(data)

        if not isinstance(self, Decision):
            return path_idx, data

        if self.all_transitions:
            result = None
            for transition in self.outgoing_transitions:
                path_idx, result = transition.target._execute(
                    path, path_idx, data)
            # return the result of the last node
            return path_idx, result
        else:
            idx = path[path_idx]
            return self.outgoing_transitions[idx].target._execute(path, path_idx+1, data)

    def _generate(self, result_path: Path, already_reached: Set, on_valid_path: bool):
        already_reached.add(id(self))

        if isinstance(self, Leaf) and self.is_valid != on_valid_path:
            v = 'valid' if on_valid_path else 'invalid'
            raise InternalException(
                f"Decision without {v} leaf detected! {self.description()}")

        if not isinstance(self, Decision):
            return
        if not self.outgoing_transitions:
            return

        if self.all_transitions:
            for transition in self.outgoing_transitions:
                v = not on_valid_path if transition.is_inverting else on_valid_path
                transition._num_paths += 1
                transition.target._generate(result_path, already_reached, v)
        else:
            selected = None
            min_paths = float('inf')
            for idx, transition in enumerate(self.outgoing_transitions):
                target = transition.target
                if transition._num_paths < min_paths:
                    if on_valid_path and not target._has_valid_successors:
                        continue
                    if not on_valid_path and not target._has_invalid_successors:
                        continue
                    selected = idx
                    min_paths = transition._num_paths
            if selected is None:
                v = 'valid' if on_valid_path else 'invalid'
                raise InternalException(
                    f"Decision without {v} leaf detected ' (id={self.id})")

            result_path.append(selected)
            transition = self.outgoing_transitions[selected]
            transition._num_paths += 1
            v = not on_valid_path if transition.is_inverting else on_valid_path
            transition.target._generate(result_path, already_reached, v)

    def _backward(self, path: Path, already_reached: Set) -> Tuple[bool, "Node"]:
        already_reached.add(id(self))

        if not self.incoming_transitions:
            return False, self

        predecessor_transition = None
        min_paths = float('inf')
        for transition in self.incoming_transitions:
            n = transition.outgoing_transition()._num_paths
            if n < min_paths:
                min_paths = n
                predecessor_transition = transition
        path.append(predecessor_transition.outgoing_idx)
        predecessor_transition.outgoing_transition()._num_paths += 1
        is_inverting, root = predecessor_transition.source._backward(
            path, already_reached)
        if predecessor_transition.outgoing_transition().is_inverting:
            return not is_inverting, root
        else:
            return is_inverting, root

    def _forward(self, backward_path: Path, forward_path: Path, visited: Set, on_valid_path: bool):
        if len(backward_path) == 0:
            return
        assert isinstance(self, Decision)
        path_idx = backward_path.pop(-1)
        if self.all_transitions:
            for idx, transition in enumerate(self.outgoing_transitions):
                v = not on_valid_path if transition.is_inverting else on_valid_path
                if idx == path_idx:
                    transition.target._forward(
                        backward_path, forward_path, visited, v)
                else:
                    transition._num_paths += 1
                    transition.target._generate(forward_path, visited, v)
        else:
            transition = self.outgoing_transitions[path_idx]
            v = not on_valid_path if transition.is_inverting else on_valid_path
            forward_path.append(path_idx)
            transition._num_paths += 1
            transition.target._forward(backward_path, forward_path, visited, v)

    def _reset_stats(self, visited: Set[str]):
        if id(self) in visited:
            return
        visited.add(id(self))

        if isinstance(self, Leaf):
            self._has_valid_successors = self.is_valid
            self._has_invalid_successors = not self.is_valid
        else:
            assert isinstance(self, Decision)

            self._has_valid_successors = False
            self._has_invalid_successors = False
            for i in self.outgoing_transitions:
                i.target._reset_stats(visited)
                self._has_valid_successors = self._has_valid_successors or i.target._has_valid_successors
                self._has_invalid_successors = self._has_invalid_successors or i.target._has_invalid_successors

    def generate_paths(self) -> Generator[ResultEntry, None, None]:
        """
        Generates as many paths until all nodes in the graph are reached.
        Execute a path using execute().
        """

        valid_nodes: List[Leaf] = []
        invalid_nodes: List[Leaf] = []

        # Reset counter, collect leafs
        for node in self.items():
            if isinstance(node, Leaf):
                if node.is_valid:
                    valid_nodes.append(node)
                else:
                    invalid_nodes.append(node)
            if isinstance(node, Decision):
                for i in node.outgoing_transitions:
                    i._num_paths = 0

        to_visit = valid_nodes + invalid_nodes

        visited = set()
        self._reset_stats(visited)

        while to_visit:
            # print(f"{len(to_visit)} nodes remaining")
            next = to_visit[0]

            # Generate a path to the root
            backward_path: Path = []
            visited = set()
            is_inverting, root = next._backward(backward_path, visited)

            # Follow path to the target node
            forward_path = []
            root._forward(backward_path, forward_path, visited, True)

            # Yield
            is_valid = not next.is_valid if is_inverting else next.is_valid
            yield ResultEntry(next, forward_path, is_valid)

            # Remove the visited nodes
            path_idx = 0
            while path_idx < len(to_visit):
                if id(to_visit[path_idx]) in visited:
                    del to_visit[path_idx]
                else:
                    path_idx += 1

    def optimize(self):
        """
        Reduces the number of nodes in this graph while keeping the meaning the same.
        This helps to speed up subsequent operations.
        """
        pass

    def get_by_id(self, id: str) -> "Node":
        """
        Gets a specific node in the graph by it's id.
        Raises a KeyError if the id does not exist.
        """
        for i in self.items():
            if i.id == id:
                return i
        raise KeyError("No such id '{id}'")


class Leaf(Node):
    def __init__(self, id: str = None, is_valid: bool = True) -> None:
        super().__init__(id)
        self.is_valid = is_valid


class OutgoingTransition:
    def __init__(self, target: Node, is_inverting: bool) -> None:
        self.target = target
        self.is_inverting = is_inverting
        self._num_paths: int = 0


class IncomingTransition:
    def __init__(self, source: "Decision", idx: int) -> None:
        self.source = source
        self.outgoing_idx = idx

    def outgoing_transition(self) -> OutgoingTransition:
        return self.source.outgoing_transitions[self.outgoing_idx]


class Decision(Node):
    def __init__(self, id: str = None, all_transitions: bool = False) -> None:
        super().__init__(id)
        self.all_transitions = all_transitions
        self.outgoing_transitions: List[OutgoingTransition] = []

    def add_transition(self, target: Node, is_inverting: bool = False):
        target.incoming_transitions.append(
            IncomingTransition(self, len(self.outgoing_transitions))
        )
        self.outgoing_transitions.append(
            OutgoingTransition(target, is_inverting)
        )

    def _items(self, already_visited: Set["Node"]) -> Generator["Node", None, None]:
        if id(self) in already_visited:
            return
        already_visited.add(id(self))
        yield self
        for transition in self.outgoing_transitions:
            yield from transition.target._items(already_visited)

    def optimize(self):
        visited = set()
        self._optimize(visited)

    def _optimize(self, visited: Set):
        if id(self) in visited:
            return
        visited.add(id(self))

        merge_with = self
        is_inverting = False
        while True:
            if len(merge_with.outgoing_transitions) != 1:
                break
            successor = merge_with.outgoing_transitions[0].target
            if len(successor.incoming_transitions) != 1:
                break
            if not isinstance(successor, NoOpDecision):
                break
            if id(successor) in visited:
                break
            if merge_with.outgoing_transitions[0].is_inverting:
                is_inverting = not is_inverting
            merge_with = successor

        if merge_with is not self:
            self.outgoing_transitions = merge_with.outgoing_transitions
            self.all_transitions = merge_with.all_transitions
            if is_inverting:
                for i in self.outgoing_transitions:
                    i.is_inverting = not i.is_inverting
            for i in self.outgoing_transitions:
                for j in i.target.incoming_transitions:
                    if j.source is merge_with:
                        j.source = self

        for i in self.outgoing_transitions:
            if isinstance(i.target, Decision):
                i.target._optimize(visited)


class Reference(Node):
    def __init__(self, id: str, reference: str) -> None:
        super().__init__(id)
        self.reference = reference

    def target(self, nodes_by_id: Dict[str, "Node"]) -> Node:
        try:
            return nodes_by_id[self.reference].target(nodes_by_id)
        except KeyError as e:
            raise ResolveReferenceException(
                f"Unknown reference '{self.reference}'", self.reference)


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
