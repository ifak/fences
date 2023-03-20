from typing import Union, Generator, Tuple, List
from xml.etree.ElementTree import Element


def _get_tag(el: Element) -> str:
    _, _, tag_wo_namespace = el.tag.rpartition('}')
    return tag_wo_namespace


NormalizedXPathElement = Tuple[str, int]

class NormalizedXPath:
    """
    A simple xpath implementation, of the form
        /foo[0]/bar[0]/x[0]
    It always selects exactly one element.
    """

    def __init__(self, elements: List[NormalizedXPathElement] = None) -> None:
        self.elements = elements or []

    def __add__(self, other: NormalizedXPathElement) -> "NormalizedXPath":
        return NormalizedXPath(self.elements + [other])

    def __str__(self) -> str:
        return '/' + '/'.join([f"{i[0]}[{i[1]}]" for i in self.elements])

    def enumerate(self, element: Element) -> Generator[Tuple["NormalizedXPath", Element], None, None]:
        visited = {}
        for child in element:
            tag = _get_tag(child)
            if tag in visited:
                visited[tag] += 1
            else:
                visited[tag] = 0
            yield self + (tag, visited[tag]), child
