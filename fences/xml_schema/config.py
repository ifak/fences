from dataclasses import dataclass, field
from typing import Dict, Callable, Set, Generator, List

from fences.core.node import Node

from xml.etree import ElementTree

TagCallback = Callable[[ElementTree.Element, "Config", Set[str]], Node]

@dataclass
class TypeHandler:
    valid: Callable[["Config"], Generator[any, None, None]]
    invalid: Callable[["Config"], Generator[any, None, None]]

@dataclass
class Config:
    tag_handlers: Dict[str, TagCallback] = field(default_factory=dict)
    buildin_types: Dict[str, TypeHandler] = field(default_factory=dict)
    restriction_handlers: Dict[str, TagCallback] = field(default_factory=dict)
