from dataclasses import dataclass
import re

@dataclass
class StringProperties:
    min_length: int
    max_length: int
    pattern: re.Pattern

def generate_random_string(properties: StringProperties) -> str:
    return "x" * properties.min_length
