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

    def apply(self, data: any) -> any:
        """
        Applies to node's operation to the given data
        (Meant to be overridden)
        """
        raise NotImplementedError()  # pragma: no cover

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

    def _generate(self, result_path: Path, already_reached: Set) -> bool:
        already_reached.add(id(self))

        if not isinstance(self, Decision):
            return True
        if not self.outgoing_transitions:
            return True

        satisfiable = True

        if self.all_transitions:
            for transition in self.outgoing_transitions:
                sub_satisfiable = transition.target._generate(result_path, already_reached)
                satisfiable = satisfiable and sub_satisfiable
        else:
            selected = None
            min_len = float('inf')
            for idx, transition in enumerate(self.outgoing_transitions):
                if min_len > transition._len_to_valid_node:
                    selected = idx
                    min_len = transition._len_to_valid_node
            # No satisfiable transition found, fallback to an un-satisfiable one
            if selected is None:
                # print("No valid leaf detected, falling back to invalid one")
                satisfiable = False
                selected = 0

            result_path.append(selected)
            transition: OutgoingTransition = self.outgoing_transitions[selected]
            sub_satisfiable = transition.target._generate(result_path, already_reached)
            satisfiable = satisfiable and sub_satisfiable
        return satisfiable

    def _backward(self, path: Path, already_reached: Set) -> "Node":
        already_reached.add(id(self))

        if not self.incoming_transitions:
            return self

        predecessor_transition = None
        min_len = float('inf')
        for transition in self.incoming_transitions:
            if transition._len_to_root < min_len:
                min_len = transition._len_to_root
                predecessor_transition = transition
        path.append(predecessor_transition.outgoing_idx)
        root = predecessor_transition.source._backward(path, already_reached)
        return root

    def _forward(self, backward_path: Path, forward_path: Path, visited: Set) -> bool:
        if len(backward_path) == 0:
            return True
        assert isinstance(self, Decision)
        path_idx = backward_path.pop(-1)
        if self.all_transitions:
            satisfiable = True
            for idx, transition in enumerate(self.outgoing_transitions):
                if idx == path_idx:
                    s = transition.target._forward(backward_path, forward_path, visited)
                else:
                    s = transition.target._generate(forward_path, visited)
                satisfiable = satisfiable and s
        else:
            transition = self.outgoing_transitions[path_idx]
            forward_path.append(path_idx)
            satisfiable = transition.target._forward(backward_path, forward_path, visited)

        return satisfiable

    def _analyze_forwards(self, length: int):
        if isinstance(self, Decision):
            for idx, t in enumerate(self.outgoing_transitions):
                # TODO: this is not efficient
                incoming = [i for i in t.target.incoming_transitions if i.outgoing_idx == idx][0]
                if incoming._len_to_root > length:
                    incoming._len_to_root = length
                    t.target._analyze_forwards(length+1)

    def _analyze_backwards(self, length):

        if isinstance(self, Decision):
            if self.all_transitions:
                length = max(i._len_to_valid_node for i in self.outgoing_transitions)
                if length == float('inf'):
                    return

        for i in self.incoming_transitions:
            out = i.outgoing_transition()
            if out._len_to_valid_node > length:
                out._len_to_valid_node = length
                i.source._analyze_backwards(length+1)

    def generate_paths(self) -> Generator[ResultEntry, None, None]:
        """
        Generates as many paths until all nodes in the graph are reached.
        Execute a path using execute().
        """

        # Reset counter, collect leafs
        valid_nodes: List[Leaf] = []
        invalid_nodes: List[Leaf] = []
        for i in self.items():
            if isinstance(i, Leaf):
                if i.is_valid:
                    valid_nodes.append(i)
                else:
                    invalid_nodes.append(i)
        self._analyze_forwards(0)
        for leaf in valid_nodes:
            leaf._analyze_backwards(0)

        # Visit valid nodes first
        to_visit = valid_nodes + invalid_nodes

        while to_visit:
            # print(f"{len(to_visit)} nodes remaining")
            next = to_visit[0]

            # Generate a path to the root
            backward_path: Path = []
            visited = set()
            root = next._backward(backward_path, visited)

            # Follow path to the target node
            forward_path = []
            satisfiable = root._forward(backward_path, forward_path, visited)

            # Yield
            yield ResultEntry(next, forward_path, next.is_valid and satisfiable)

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
    def __init__(self, target: Node) -> None:
        self.target = target
        self._len_to_valid_node: int = float('inf')


class IncomingTransition:
    def __init__(self, source: "Decision", idx: int) -> None:
        self.source = source
        self.outgoing_idx = idx
        self._len_to_root: int = float('inf')

    def outgoing_transition(self) -> OutgoingTransition:
        return self.source.outgoing_transitions[self.outgoing_idx]


class Decision(Node):
    def __init__(self, id: str = None, all_transitions: bool = False) -> None:
        super().__init__(id)
        self.all_transitions = all_transitions
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

    def optimize(self):
        visited = set()
        self._optimize(visited)

    def _optimize(self, visited: Set):
        if id(self) in visited:
            return
        visited.add(id(self))

        merge_with = self
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
            merge_with = successor

        if merge_with is not self:
            self.outgoing_transitions = merge_with.outgoing_transitions
            self.all_transitions = merge_with.all_transitions
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
