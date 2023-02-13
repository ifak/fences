import re
from typing import Set, Dict, List, Optional, Union

from .exceptions import ParseException
from .config import Config, KeyHandler, StringGenerators, BoolValues
from .json_pointer import JsonPointer
from .string import generate_random_string, StringProperties

from fences.core.node import Decision, Leaf, Node, Reference, Operation, NoOpLeaf, NoOpDecision

from dataclasses import dataclass


@dataclass
class KeyReference:
    ref: Union[dict, list]
    key: Optional[str] = None

    def set(self, value):
        self.ref[self.key] = value


class SetValueLeaf(Leaf):

    def __init__(self, id: str, is_valid: bool, value: any) -> None:
        super().__init__(id, is_valid)
        self.value = value

    def apply(self, data: KeyReference) -> any:
        data.set(self.value)
        return self.value

    def description(self) -> str:
        return f"Set to value '{self.value}'"


class InsertKeyNode(Decision):
    def __init__(self, id: str, key: str) -> None:
        super().__init__(id)
        self.key = key

    def apply(self, data: any) -> KeyReference:
        return KeyReference(data, self.key)

    def description(self) -> str:
        return f"Create key '{self.key}'"


class CreateArrayNode(Decision):
    def apply(self, data: any) -> any:
        value = []
        data.set(value)
        return value

    def description(self) -> str:
        return "Create empty array"


class AppendArrayItemNode(Decision):
    def apply(self, data: any) -> KeyReference:
        data.append(None)
        return KeyReference(data, len(data)-1)

    def description(self) -> str:
        return "Append item"


class CreateObjectNode(Decision):
    def apply(self, data: KeyReference) -> KeyReference:
        value = {}
        data.set(value)
        return value

    def description(self) -> str:
        return "Create empty dict"

class CreateInputNode(Decision):
    def __init__(self) -> None:
        super().__init__(None, Operation.OR)

    def apply(self, data: any) -> any:
        return KeyReference({}, '')

    def description(self) -> Optional[str]:
        return "Create input"

class FetchOutputNode(Leaf):
    def __init__(self) -> None:
        super().__init__(None, True)

    def apply(self, data: KeyReference) -> any:
        return data.ref[data.key]

    def description(self) -> Optional[str]:
        return "Fetch output"

def default_config():
    return Config(
        key_handlers=[
            KeyHandler('allOf', parse_all_of),
            KeyHandler('$ref', parse_reference),
            KeyHandler('enum', parse_enum),
            KeyHandler('type', parse_type),
            KeyHandler('properties', parse_object),
        ],
        type_handlers={
            'object': parse_object,
            'string': parse_string,
            'array': parse_array,
            'boolean': parse_boolean,
        },
        string_generators=StringGenerators(
            valid=[
                generate_random_string,
            ],
            invalid=[
                lambda _: None,
            ]
        ),
        bool_values=BoolValues(
            valid=[
                True,
                False,
            ],
            invalid=[
                42,
                None,
                'INVALID',
            ]
        ),
        invalid_array_values=[
            True,
            False,
            None,
            {},
            'INVALID'
        ]
    )


def _read_typesafe(data: dict, key: str, unparsed_keys: Set[str], type, typename, default: any):
    if key not in data:
        if default is None:
            raise ParseException(f"'{key}' is missing")
        else:
            return default
    value = data[key]
    if not isinstance(value, type):
        raise ParseException(f"{value} is not a {typename}")
    unparsed_keys.remove(key)
    return value


def _read_int(data: dict, key: str, unparsed_keys: Set[str], default=None) -> str:
    return _read_typesafe(data, key, unparsed_keys, int, 'int', default)


def _read_string(data: dict, key: str, unparsed_keys: Set[str], default=None) -> str:
    return _read_typesafe(data, key, unparsed_keys, str, 'string', default)


def _read_dict(data: dict, key: str, unparsed_keys: Set[str], default=None) -> dict:
    return _read_typesafe(data, key, unparsed_keys, dict, 'dict', default)


def _read_list(data: dict, key: str, unparsed_keys: Set[str], default=None) -> list:
    return _read_typesafe(data, key, unparsed_keys, list, 'list', default)


def parse_all_of(data, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(str(path))
    root.operation = Operation.AND
    items = _read_list(data, 'allOf', unparsed_keys)
    # TODO: although 'type' does not make sense here, we need to skip it since many schemas use it
    _read_string(data, 'type', unparsed_keys, '')
    for idx, item in enumerate(items):
        target = parse_dict(item, config, path + 'allOf' + idx)
        root.add_transition(target)
    return root


def parse_enum(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    # TODO: use type for something?
    _read_string(data, 'type', unparsed_keys)
    values = _read_list(data, 'enum', unparsed_keys)
    root = NoOpDecision(str(path))
    max_length = 0
    for value in values:
        root.add_transition(SetValueLeaf(None, True, value))
        max_length = max(max_length, len(str(value)))
    root.add_transition(SetValueLeaf(
        None, False, "#" * (max_length+1)))
    return root


def parse_reference(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    ref = _read_string(data, '$ref', unparsed_keys)
    return Reference(str(path + '$ref'), ref)


def parse_object(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    props = _read_dict(data, 'properties', unparsed_keys)

    required: Set[str] = set()
    for idx, token in enumerate(_read_list(data, 'required', unparsed_keys, [])):
        sub_path = path + 'required' + idx
        if not isinstance(token, str):
            raise ParseException(f"'{token}' is not a string at ${sub_path}")
        if token in required:
            raise ParseException(f"Duplicate token '{token}' in ${sub_path}")
        if token not in props:
            raise ParseException(f"Token '{token}' is not a property at ${sub_path}")
        required.add(token)

    root = CreateObjectNode(str(path))
    root.operation = Operation.AND
    # Create Keys (always valid)
    for key, value in props.items():
        sub_path = path + 'properties' + key
        key_node = InsertKeyNode(None, key)
        root.add_transition(key_node)
        value_node = parse_dict(value, config, sub_path)
        key_node.add_transition(value_node)
        root.add_transition(NoOpLeaf(None, is_valid=key not in required))
    return root


def parse_string(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(str(path))
    pattern = _read_string(data, 'pattern', unparsed_keys, '')
    if pattern:
        try:
            regex = re.compile(pattern)
        except re.error:
            raise ParseException(f"Invalid pattern '{pattern}' at {path}")
    else:
        regex = None
    # TODO: use format
    format = _read_string(data, 'format', unparsed_keys, '')
    properties = StringProperties(
        min_length=_read_int(data, 'minLength', unparsed_keys, 0),
        max_length=_read_int(data, 'maxLength', unparsed_keys, float("inf")),
        pattern=regex,
    )
    for generator in config.string_generators.valid:
        value = generator(properties)
        root.add_transition(SetValueLeaf(None, True, value))
    for generator in config.string_generators.invalid:
        value = generator(properties)
        root.add_transition(SetValueLeaf(None, False, value))
    return root


def parse_array(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    # TODO: use min items
    min_items = _read_int(data, 'minItems', unparsed_keys, 0)
    items = _read_dict(data, 'items', unparsed_keys)
    items_path = path + 'items'
    root_node = NoOpDecision(str(path))

    # Valid
    create_node = CreateArrayNode(None)
    append_node = AppendArrayItemNode(None)
    root_node.add_transition(create_node)
    create_node.add_transition(append_node)
    append_node.add_transition(parse_dict(items, config, items_path))

    # Invalid
    for value in config.invalid_array_values:
        root_node.add_transition(SetValueLeaf(None, False, value))

    return root_node


def parse_boolean(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(str(path))
    for value in config.bool_values.valid:
        root.add_transition(SetValueLeaf(None, True, value))
    for value in config.bool_values.invalid:
        root.add_transition(SetValueLeaf(None, False, value))
    return root


def parse_type(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    type = _read_string(data, 'type', unparsed_keys)
    if type not in config.type_handlers:
        raise ParseException(f"Invalid type '{type}' at {path}")
    return config.type_handlers[type](data, config, unparsed_keys, path)


def parse_dict(data: dict, config: Config, path: JsonPointer):
    if not isinstance(data, dict):
        raise ParseException(f"Expected dict, got {type(data)}")
    unparsed_keys = set(data.keys())
    for handler in config.key_handlers:
        if handler.key in data:
            result = handler.callback(data, config, unparsed_keys, path)
            if unparsed_keys:
                raise ParseException(
                    f"Unknown keys {unparsed_keys} at '{path}'")
            return result
    raise ParseException(f"Cannot parse {data} at {path}")


def parse(data: dict, config=None) -> Node:
    if config is None:
        config = default_config()

    if not isinstance(data, dict):
        raise ParseException(f"Expected dict, got {type(data)}")

    # Skip meta data
    unparsed_keys = set(data.keys())
    _read_string(data, '$schema', unparsed_keys, '')
    _read_string(data, 'title', unparsed_keys, '')
    _read_string(data, '$id', unparsed_keys, '')

    # Read definitions
    path = JsonPointer()
    all_nodes: List[Node] = []
    definitions = _read_dict(data, 'definitions', unparsed_keys, {})
    for key, definition in definitions.items():
        sub_path = path + 'definitions' + key
        node = parse_dict(definition, config, sub_path)
        all_nodes.append(node)

    # Read root
    root = None
    for handler in config.key_handlers:
        if handler.key in data:
            result = handler.callback(data, config, unparsed_keys, path)
            if unparsed_keys:
                raise ParseException(
                    f"Unknown keys {unparsed_keys} at '{path}'")
            root = result
            break
    if not root:
        raise ParseException(f"Cannot parse {data} at {path}")

    root = root.resolve(all_nodes)

    # prepend input / output nodes
    create_input = CreateInputNode()
    super_root = NoOpDecision(None, Operation.AND)
    create_input.add_transition(super_root)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutputNode())
    
    return create_input
