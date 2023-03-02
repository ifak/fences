from dataclasses import dataclass, field
from typing import Dict, Callable, Set, Generator, List

from fences.core.node import Node

from xml.etree import ElementTree

TagCallback = Callable[[ElementTree.Element, "Config", Set[str]], Node]
TypeCallback = Callable[["Config"], Generator[any, None, None]]

@dataclass
class Config:
    tag_handlers: Dict[str, TagCallback] = field(default_factory=dict)
    buildin_types: Dict[str, TypeCallback] = field(default_factory=dict)
    restriction_handlers: Dict[str, TagCallback] = field(default_factory=dict)
