from dataclasses import dataclass, field
from typing import Callable, Set, List, Dict, Optional

from .json_pointer import JsonPointer
from fences.core.node import Decision, Node

Handler = Callable[[dict, "Config", Set[str], JsonPointer], Decision]
PostProcessor = Callable[[dict, Node], Node]


@dataclass
class FormatSamples:
    valid: List[str] = field(default_factory=list)
    invalid: List[str] = field(default_factory=list)


@dataclass
class Config:
    key_handlers: Dict[str, Handler]
    type_handlers: Dict[str, Handler]
    default_samples: Dict[str, List[any]]
    normalize: bool
    format_samples: Dict[str, FormatSamples]
    post_processor: Optional[PostProcessor]
