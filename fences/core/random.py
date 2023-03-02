from dataclasses import dataclass
import random

from fences.regex.parse import parse
from fences.core.exception import InternalException

from typing import Optional


@dataclass
class StringProperties:
    min_length: int = 0
    max_length: int = None
    pattern: Optional[str] = None


def generate_random_string(properties: StringProperties) -> str:
    if properties.max_length is not None:
        assert properties.min_length <= properties.max_length
    if properties.pattern is None:
        return "x" * properties.min_length
    else:
        graph = parse(str(properties.pattern))
        result = None
        for i in graph.generate_paths():
            if i.is_valid:
                result = graph.execute(i.path)
                break
        if result is None:
            raise InternalException(
                f"Failed to generate string for '{properties.pattern}'")
        if properties.max_length is not None and len(result) > properties.max_length:
            raise InternalException(
                f"Cannot generate a string for {properties.pattern} with is not longer than {properties.max_length}")
        padding = max(properties.min_length - len(result), 0)
        return "x" * padding + result


def generate_random_number(min_value: Optional[int] = None, max_value: Optional[int] = None):
    if min_value is None:
        min_value = -1000
    if max_value is None:
        max_value = +1000
    assert min_value <= max_value
    return random.randint(min_value, max_value)
