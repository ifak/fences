from dataclasses import dataclass, field
from typing import Callable, Set, List, Dict

from .json_pointer import JsonPointer
from ..core.random import StringProperties

from fences.core.node import Decision

Handler = Callable[[dict, "Config", Set[str], JsonPointer], Decision]


@dataclass
class Config:
    key_handlers: Dict[str, Handler]
    type_handlers: Dict[str, Handler]
    default_samples: Dict[str, List[any]]
    normalize: bool
