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
        if result is None:  # pragma: no cover
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


def generate_random_format(format: str) -> str:
    # From https://json-schema.org/understanding-json-schema/reference/string#built-in-formats
    samples = {
        "date-time": "2018-11-13T20:20:39+00:00",
        "time": "20:20:39+00:00",
        "date": "2018-11-13",
        "duration": "P3D",
        "email": "test@example.com",
        "hostname": "example.com",
        "ipv4": "127.0.0.1",
        "ipv6": "2001:db8::8a2e:370:7334",
        "uuid": "3e4666bf-d5e5-4aa7-b8ce-cefe41c7568a",
    }
    return samples.get(format, "")
