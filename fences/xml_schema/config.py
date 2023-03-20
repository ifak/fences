from dataclasses import dataclass, field
from typing import Dict, Callable, Set, Generator
from .xpath import NormalizedXPath

from fences.core.node import Node
from fences.core.exception import ConfigException

from xml.etree.ElementTree import Element

TagCallback = Callable[[Element,
                        "Config", Set[str], NormalizedXPath], Node]


def empty_iter(*args):
    return
    yield


@dataclass
class TypeGenerator:
    valid: Callable[[Element, NormalizedXPath], Generator[any, None, None]]
    invalid: Callable[[Element, NormalizedXPath], Generator[any, None, None]]


@dataclass
class Config:
    tag_handlers: Dict[str, TagCallback] = field(default_factory=dict)
    type_generators: Dict[str, TypeGenerator] = field(default_factory=dict)
    restriction_handlers: Dict[str, TagCallback] = field(default_factory=dict)

    def merge(self, data: dict):

        if not isinstance(data, dict):
            raise ConfigException("config must be a dict")

        # parse type_generators
        type_generators = data.get('type_generators', {})
        if not isinstance(type_generators, dict):
            raise ConfigException("type_generators must be a dict")
        for type_name, entry in type_generators.items():
            if not isinstance(entry, dict):
                raise ConfigException(
                    "type_generators entries must be dicts")
            if type_name not in self.type_generators:
                self.type_generators[type_name] = TypeGenerator(
                    empty_iter, empty_iter)
            if 'valid' in entry:
                valid = entry['valid']
                if not isinstance(valid, Callable):
                    raise ConfigException(
                        "type_generators.valid must be callable")
                self.type_generators[type_name].valid = valid
            if 'invalid' in entry:
                invalid = entry['valid']
                if not isinstance(invalid, Callable):
                    raise ConfigException(
                        "type_generators.invalid must be callable")
                self.type_generators[type_name].invalid = invalid
        # TODO parse tag_handlers
        # TODO parse restriction_handlers
