import pydot

from .exception import GraphException
from .node import Node, Decision, Leaf, Reference, Operation

def _to_text(operation: Operation) -> str:
    if operation == Operation.AND: return 'AND'
    if operation == Operation.OR: return 'OR'
    raise GraphException(f"Unknown operation '{operation}'") # pragma: no cover

def _to_graph_node(node: Node):
    attrs = {}
    lines = []
    if node.id:
        lines.append(node.id)
    d = node.description()
    if d:
        lines.append(d)
    if isinstance(node, Decision):
        attrs['shape'] = 'rect'
        lines.append(_to_text(node.operation))
    elif isinstance(node, Reference):
        attrs['fillcolor'] = 'yellow'
        attrs['style'] = 'filled'
        lines.append(f"-> {node.reference}")
    elif isinstance(node, Leaf):
        attrs['color'] = 'green' if node.is_valid else 'red'
    else:
        raise GraphException(f"Unknown type '{type(node)}'") # pragma: no cover
    return pydot.Node(str(id(node)), label="\n".join(lines), **attrs)

def render(node: Node) -> pydot.Dot:
    graph = pydot.Dot("my_graph", graph_type="digraph")

    for i in node.items():
        graph.add_node(_to_graph_node(i))
        if isinstance(i, Decision):
            for transition in i.outgoing_transitions:
                graph.add_edge(pydot.Edge(str(id(i)), str(id(transition.target))))

    return graph
