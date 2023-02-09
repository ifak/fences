from fences.core.node import Node, Path

from .parse import KeyReference

def execute(graph: Node, path: Path) -> any:
    data = KeyReference({}, '')
    graph.execute(path, data)
    return data.ref[data.key]
