import re
from typing import Set, Dict, List, Optional, Union

from .exceptions import JsonSchemaException
from .config import Config, KeyHandler, StringGenerators, BoolValues
from .json_pointer import JsonPointer
from ..core.random import generate_random_string, StringProperties

from fences.core.node import Decision, Leaf, Node, Reference, NoOpLeaf, NoOpDecision

from dataclasses import dataclass


@dataclass
class KeyReference:
    ref: Union[dict, list]
    key: Optional[str] = None
    has_value: bool = False

    def set(self, value):
        self.ref[self.key] = value
        self.has_value = True


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
        return f"Insert key '{self.key}'"


class CreateArrayNode(Decision):
    def apply(self, data: KeyReference) -> any:
        # Needed to handle allOf properly
        if data.has_value:
            return data.ref[data.key]
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
        # Needed to handle allOf properly
        if data.has_value:
            return data.ref[data.key]
        value = {}
        data.set(value)
        return value

    def description(self) -> str:
        return "Create empty dict"

class CreateInputNode(Decision):
    def __init__(self) -> None:
        super().__init__(None, False)

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
            KeyHandler('if', parse_if),
            KeyHandler('allOf', parse_all_of),
            KeyHandler('oneOf', parse_one_of),
            KeyHandler('$ref', parse_reference),
            KeyHandler('enum', parse_enum),
            KeyHandler('type', parse_type),
            KeyHandler('properties', parse_object),
            KeyHandler('not', parse_not),
            KeyHandler('const', parse_const),
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


def _read_typesafe(data: dict, key: str, unparsed_keys: Set[str], type, typename, pointer: JsonPointer, default: any):
    if key not in data:
        if default is None:
            raise JsonSchemaException(f"'{key}' is missing at {pointer}", None)
        else:
            return default
    value = data[key]
    if not isinstance(value, type):
        raise JsonSchemaException(f"{value} is not a {typename} at {pointer}", None)
    unparsed_keys.remove(key)
    return value


def _read_int(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=None) -> str:
    return _read_typesafe(data, key, unparsed_keys, int, 'int', pointer, default)


def _read_string(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=None) -> str:
    return _read_typesafe(data, key, unparsed_keys, str, 'string', pointer, default)


def _read_dict(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=None) -> dict:
    return _read_typesafe(data, key, unparsed_keys, dict, 'dict', pointer, default)


def _read_list(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=None) -> list:
    return _read_typesafe(data, key, unparsed_keys, list, 'list', pointer, default)

def parse_if(data, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    if_data = _read_dict(data, 'if', unparsed_keys, path)
    if_node = parse_dict(if_data, config, path + 'if')
    then_data = _read_dict(data, 'then', unparsed_keys, path)
    then_node = parse_dict(then_data, config, path + 'then')
    if 'else' in data:
        else_data = _read_dict(data, 'else', unparsed_keys, path)
        else_node = parse_dict(else_data, config, path + 'else')
    else:
        else_node = None
    root = NoOpDecision(str(path), False)

    # IF: valid, THEN: valid
    sub_root_0 = NoOpDecision(None, True)
    sub_root_0.add_transition(if_node)
    sub_root_0.add_transition(then_node)
    root.add_transition(sub_root_0)

    # IF: invalid, THEN: invalid
    sub_root_1 = NoOpDecision(None, True)
    sub_root_1.add_transition(if_node, True)
    sub_root_1.add_transition(then_node, True)
    root.add_transition(sub_root_1)

    if else_node:
        # IF: valid ELSE: invalid
        sub_root_2 = NoOpDecision(None, True)
        sub_root_2.add_transition(if_node)
        sub_root_2.add_transition(else_node, True)
        root.add_transition(sub_root_2)

        # IF: invalid ELSE: valid
        sub_root_3 = NoOpDecision(None, True)
        sub_root_3.add_transition(if_node, True)
        sub_root_3.add_transition(else_node)
        root.add_transition(sub_root_3)

    return root

def parse_const(data, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    value = data['const']
    unparsed_keys.remove('const')

    root = NoOpDecision(str(path), False)
    root.add_transition(SetValueLeaf(None, True, value))
    root.add_transition(SetValueLeaf(None, False, f"{value}_INvALID"))
    return root

def _parse_aggregation(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer, key: str,  all_transitions: bool) -> Node:
    root = NoOpDecision(str(path))
    root.all_transitions = all_transitions
    items = _read_list(data, key, unparsed_keys, path)
    # TODO: although 'type' does not make sense here, we need to skip it since many schemas use it
    _read_string(data, 'type', unparsed_keys, path, '')
    for idx, item in enumerate(items):
        target = parse_dict(item, config, path + 'allOf' + idx)
        root.add_transition(target)
    return root


def parse_one_of(data, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    return _parse_aggregation(data, config, unparsed_keys, path, 'oneOf', False)


def parse_all_of(data, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    # TODO: this works for objects, but not for strings etc.
    return _parse_aggregation(data, config, unparsed_keys, path, 'allOf', True)


def parse_enum(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    # TODO: use type for something?
    _read_string(data, 'type', unparsed_keys, path, '')
    values = _read_list(data, 'enum', unparsed_keys, path)
    root = NoOpDecision(str(path), False)
    max_length = 0
    for value in values:
        root.add_transition(SetValueLeaf(None, True, value))
        max_length = max(max_length, len(str(value)))
    root.add_transition(SetValueLeaf(
        None, False, "#" * (max_length+1)))
    return root

def parse_not(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    d = _read_dict(data, 'not', unparsed_keys, path)
    subroot = parse_dict(d, config, path + 'not')
    root = NoOpDecision(str(path), False)
    root.add_transition(subroot, True)
    return root

def parse_reference(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    ref = _read_string(data, '$ref', unparsed_keys, path)
    return Reference(str(path), ref)


def parse_object(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    props = _read_dict(data, 'properties', unparsed_keys, path, {})

    required: Set[str] = set()
    for idx, token in enumerate(_read_list(data, 'required', unparsed_keys, path, [])):
        sub_path = path + 'required' + idx
        if not isinstance(token, str):
            raise JsonSchemaException(f"'{token}' is not a string at ${sub_path}", sub_path)
        if token in required:
            raise JsonSchemaException(f"Duplicate token '{token}' in ${sub_path}", sub_path)
        if token not in props:
            raise JsonSchemaException(f"Token '{token}' is not a property at ${sub_path}", sub_path)
        required.add(token)

    root = CreateObjectNode(str(path))
    root.all_transitions = True

    for key, value in props.items():
        property_root = NoOpDecision(None, False)
        root.add_transition(property_root)

        # Insert property (always valid)
        sub_path = path + 'properties' + key
        key_node = InsertKeyNode(None, key)
        property_root.add_transition(key_node)
        value_node = parse_dict(value, config, sub_path)
        key_node.add_transition(value_node)

        # Omit property (valid if not required)
        property_root.add_transition(NoOpLeaf(None, is_valid=key not in required))

    return root


def parse_string(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(str(path))
    pattern = _read_string(data, 'pattern', unparsed_keys, path, '')
    if pattern:
        regex = pattern
    else:
        regex = None
    # TODO: use format
    format = _read_string(data, 'format', unparsed_keys, path, '')
    properties = StringProperties(
        min_length=_read_int(data, 'minLength', unparsed_keys, path, 0),
        max_length=_read_int(data, 'maxLength', unparsed_keys, path, float("inf")),
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
    min_items = _read_int(data, 'minItems', unparsed_keys, path, 0)
    items = _read_dict(data, 'items', unparsed_keys, path)
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
    type = _read_string(data, 'type', unparsed_keys, path)
    if type not in config.type_handlers:
        raise JsonSchemaException(f"Invalid type '{type}' at {path}", path)
    return config.type_handlers[type](data, config, unparsed_keys, path)


def parse_dict(data: dict, config: Config, path: JsonPointer):
    if not isinstance(data, dict):
        raise JsonSchemaException(f"Expected dict, got {(data)} at {path}", path)
    unparsed_keys = set(data.keys())
    for handler in config.key_handlers:
        if handler.key in data:
            result = handler.callback(data, config, unparsed_keys, path)
            if unparsed_keys:
                raise JsonSchemaException(f"Unknown keys {unparsed_keys} at '{path}'", path)
            return result
    raise JsonSchemaException(f"Cannot parse {data} at {path}", path)


def parse(data: dict, config=None) -> Node:
    if config is None:
        config = default_config()

    if not isinstance(data, dict):
        raise JsonSchemaException(f"Expected dict, got {type(data)}", path)

    path = JsonPointer()

    # Skip meta data
    unparsed_keys = set(data.keys())
    _read_string(data, '$schema', unparsed_keys, path, '')
    _read_string(data, 'title', unparsed_keys, path, '')
    _read_string(data, '$id', unparsed_keys, path, '')

    # Read definitions
    all_nodes: List[Node] = []
    definitions = _read_dict(data, 'definitions', unparsed_keys, path, {})
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
                raise JsonSchemaException(f"Unknown keys {unparsed_keys} at '{path}'", path)
            root = result
            break
    if not root:
        raise JsonSchemaException(f"Cannot parse {data} at {path}", path)

    root = root.resolve(all_nodes)

    # root.optimize()

    # prepend input / output nodes
    create_input = CreateInputNode()
    super_root = NoOpDecision(None, True)
    create_input.add_transition(super_root)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutputNode())
    
    return create_input
