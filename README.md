# Fences

Fences is a python tool which lets you create test data based on schemas.

For this, it generates a set of *valid samples* which fullfil your schema.
Additionally, it generates a set of *invalid samples* which intentionally violate your schema.
You can then feed these samples into your software to test.
If your software is implemented correctly, it must accept all valid samples and reject all invalid ones.

Unlike other similar tools, fences generate samples systematically instead of randomly.
This way, the valid / invalid samples systematically cover all boundaries of your input schema (like placing *fences*, hence the name).

## Usage

Generate samples for regular expressions:

```python
from fences import parse_regex

graph = parse_regex("a+(c+)b{3,7}")

for i in graph.generate_paths():
    sample = graph.execute(i.path)
    print("Valid:" if i.is_valid else "Invalid:")
    print(sample)
```

Generate samples for json schema:

```python
from fences import parse_json_schema
import json

graph = parse_json_schema({
    'properties': {
        'foo': {
            'type': 'string'
        },
        'bar': {
            'type': 'boolean'
        }
    }
})

for i in graph.generate_paths():
    sample = graph.execute(i.path)
    print("Valid:" if i.is_valid else "Invalid:")
    print(json.dumps(sample, indent=4))
```