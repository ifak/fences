from dataclasses import dataclass, field
from typing import Callable, Set, List, Dict

from .json_pointer import JsonPointer
from ..core.random import StringProperties

from fences.core.node import Decision


@dataclass
class KeyHandler:
    key: str
    callback: Callable[[dict, "Config", Set[str], JsonPointer], Decision]


@dataclass
class TypeHandler:
    type: str
    callback: Callable[[dict, "Config", Set[str], JsonPointer], Decision]


@dataclass
class StringGenerators:
    valid: List[ Callable[[StringProperties], str] ] = field(default_factory=list)
    invalid: List[ Callable[[StringProperties], str] ] = field(default_factory=list)

@dataclass
class BoolValues:
    valid: List[ bool ] = field(default_factory=list)
    invalid: List[ bool ] = field(default_factory=list)

@dataclass
class Config:
    key_handlers: List[KeyHandler]
    type_handlers: Dict[str, TypeHandler]
    string_generators: StringGenerators
    bool_values: BoolValues
    invalid_array_values: List[any]
