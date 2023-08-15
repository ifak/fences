import re
from typing import Set, Dict, List, Optional, Union

from .exceptions import JsonSchemaException
from .config import Config, StringGenerators
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
        key_handlers={
            'enum': parse_enum,
            'NOT_enum': parse_not_enum,
            '$ref': parse_reference,
        },
        type_handlers={
            'object': parse_object,
            'string': parse_string,
            'array': parse_array,
            'boolean': parse_boolean,
            'number': parse_number,
            'null': parse_null,
        },
        string_generators=StringGenerators(
            valid=[
                generate_random_string,
            ],
        ),
        default_samples={
            'string': ["string"],
            'number': [42],
        }
    )


_NO_DEFAULT = object()


def _read_typesafe(data: dict, key: str, unparsed_keys: Set[str], type, typename, pointer: JsonPointer, default: any):
    if key not in data:
        if default is _NO_DEFAULT:
            raise JsonSchemaException(f"'{key}' is missing at {pointer}", None)
        else:
            return default
    value = data[key]
    if not isinstance(value, type):
        raise JsonSchemaException(
            f"{value} is not a {typename} at {pointer}", None)
    unparsed_keys.remove(key)
    return value


def _read_int(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=_NO_DEFAULT) -> str:
    return _read_typesafe(data, key, unparsed_keys, int, 'int', pointer, default)


def _read_string(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=_NO_DEFAULT) -> str:
    return _read_typesafe(data, key, unparsed_keys, str, 'string', pointer, default)


def _read_dict(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=_NO_DEFAULT) -> dict:
    return _read_typesafe(data, key, unparsed_keys, dict, 'dict', pointer, default)


def _read_list(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=_NO_DEFAULT) -> list:
    return _read_typesafe(data, key, unparsed_keys, list, 'list', pointer, default)


def parse_const(data, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    value = data['const']
    unparsed_keys.remove('const')

    root = NoOpDecision(str(path), False)
    root.add_transition(SetValueLeaf(None, True, value))
    root.add_transition(SetValueLeaf(None, False, f"{value}_INvALID"))
    return root


def parse_not_enum(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    values = _read_list(data, 'NOT_enum', unparsed_keys, path)
    return _parse_enum(values, path, True)


def parse_enum(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    values = _read_list(data, 'enum', unparsed_keys, path)
    return _parse_enum(values, path, False)


def _parse_enum(values: list, path: JsonPointer, invert: bool) -> Node:
    root = NoOpDecision(str(path), False)
    max_length = 0
    for value in values:
        root.add_transition(SetValueLeaf(None, not invert, value))
        max_length = max(max_length, len(str(value)))
    root.add_transition(SetValueLeaf(
        None, invert, "#" * (max_length+1)))
    return root


def parse_reference(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    ref = _read_string(data, '$ref', unparsed_keys, path)
    return Reference(str(path), ref)


def parse_object(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    props = _read_dict(data, 'properties', unparsed_keys, path, {})

    additional_props = _read_dict(
        data, 'additionalProperties', unparsed_keys, path, {})
    min_properties = _read_int(data, 'minProperties', unparsed_keys, path, 0)
    max_properties = _read_int(data, 'maxProperties', unparsed_keys, path, 0)
    pattern_properties = _read_dict(
        data, 'patternProperties', unparsed_keys, path, {})
    property_names = _read_dict(data, 'propertyNames', unparsed_keys, path, {})
    unevaluated_properties = _read_dict(
        data, 'unevaluatedProperties', unparsed_keys, path, {})
    depended_required = _read_dict(
        data, 'dependentRequired', unparsed_keys, path, [])
    dependent_schema = _read_dict(
        data, 'dependentSchemas', unparsed_keys, path, {})

    required: Set[str] = set()
    for idx, token in enumerate(_read_list(data, 'required', unparsed_keys, path, [])):
        sub_path = path + 'required' + idx
        if not isinstance(token, str):
            raise JsonSchemaException(
                f"'{token}' is not a string at ${sub_path}", sub_path)
        if token in required:
            raise JsonSchemaException(
                f"Duplicate token '{token}' in ${sub_path}", sub_path)
        # TODO: this is actually ok, but it really simplifies debugging
        if token not in props:
            raise JsonSchemaException(
                f"Token '{token}' is not a property at ${sub_path}", sub_path)
        required.add(token)

    super_root = NoOpDecision(f"{path}_OBJECT")

    root = CreateObjectNode(None, True)
    all_optional = True
    for key, value in props.items():
        sub_path = path + 'properties' + key

        property_root = NoOpDecision(f"{sub_path}__PROP", False)
        root.add_transition(property_root)

        # Insert property (always valid)
        key_node = InsertKeyNode(f"{sub_path}__KEY", key)
        property_root.add_transition(key_node)
        value_node = parse_dict(value, config, sub_path)
        key_node.add_transition(value_node)

        # Omit property (valid if not required)
        if key in required:
            property_root.add_transition(NoOpLeaf(None, is_valid=False))
            all_optional = False
        else:
            property_root.add_transition(NoOpLeaf(None, is_valid=True))

    super_root.add_transition(root)

    # TODO:
    # super_root.add_transition(SetValueLeaf(None, all_optional, {}))

    return super_root


def parse_string(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision()
    pattern = _read_string(data, 'pattern', unparsed_keys, path, '')
    content_media_type = _read_string(
        data, 'contentMediaType', unparsed_keys, path, '')
    content_encoding = _read_string(
        data, 'contentEncoding', unparsed_keys, path, '')
    content_schema = _read_dict(data, 'contentSchema', unparsed_keys, path, {})
    if pattern:
        regex = pattern
    else:
        regex = None
    # TODO: use format
    format = _read_string(data, 'format', unparsed_keys, path, '')
    properties = StringProperties(
        min_length=_read_int(data, 'minLength', unparsed_keys, path, 0),
        max_length=_read_int(
            data, 'maxLength', unparsed_keys, path, float("inf")),
        # pattern=regex,
    )
    for generator in config.string_generators.valid:
        value = generator(properties)
        root.add_transition(SetValueLeaf(None, True, value))
    return root


def parse_array(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    min_items = _read_int(data, 'minItems', unparsed_keys, path, 0)
    max_items = _read_int(data, 'maxItems', unparsed_keys, path, 0)
    prefix_items = _read_dict(data, 'prefixItems', unparsed_keys, path, {})
    unique_items = _read_dict(data, 'uniqueItems', unparsed_keys, path, {})
    contains = _read_dict(data, 'contains', unparsed_keys, path, {})
    min_contains = _read_int(data, 'minContains', unparsed_keys, path, 0)
    max_contains = _read_int(data, 'maxContains', unparsed_keys, path, 0)

    items = _read_dict(data, 'items', unparsed_keys, path, None)
    items_path = path + 'items'
    root_node = NoOpDecision(f"{path}_ARRAY")

    # Valid
    create_node = CreateArrayNode(None)
    append_node = AppendArrayItemNode(None)
    root_node.add_transition(create_node)
    create_node.add_transition(append_node)
    if items is None:
        for samples in config.default_samples.values():
            for sample in samples:
                append_node.add_transition(
                    SetValueLeaf(None, True, sample)
                )
    else:
        append_node.add_transition(
            parse_dict(items, config, items_path))

    return root_node


def parse_boolean(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(f"{path}_BOOLEAN")
    root.add_transition(SetValueLeaf(None, True, value=True))
    root.add_transition(SetValueLeaf(None, True, value=False))
    return root


def parse_number(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    minimum = _read_int(data, 'minimum', unparsed_keys, path, float('-inf'))
    minimum_exclusive = _read_int(
        data, 'exclusiveMinimum', unparsed_keys, path, float('-inf'))
    maximum = _read_int(data, 'maximum', unparsed_keys, path, float('+inf'))
    maximumExclusive = _read_int(
        data, 'exclusiveMaximum', unparsed_keys, path, float('+inf'))
    multipleOf = _read_int(data, 'multipleOf', unparsed_keys, path, 1)
    root = NoOpDecision(f"{path}_NUMBER")
    root.add_transition(SetValueLeaf(None, True, 42))
    return root


def parse_null(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(f"{path}_NULL")
    root.add_transition(SetValueLeaf(None, True, value=None))
    return root


def parse_any_of_entry(entry: dict, config: Config, pointer: JsonPointer) -> Node:
    unparsed_keys = set(entry.keys())

    # try special keys first
    for key, handler in config.key_handlers.items():
        if key in entry:
            return handler(entry, config, unparsed_keys, pointer)

    root = NoOpDecision(None, False)
    if 'type' in entry:
        types = entry['type']
        if isinstance(types, str):
            types = [types]
        types = set(types)
    else:
        # Omitting 'type' basically allows all types
        types = config.type_handlers.keys()

    # Generate samples for all allowed types (valid + invalid)
    for t in types:
        try:
            handler = config.type_handlers[t]
        except KeyError:
            raise JsonSchemaException(f"Unknown type '{t}'", pointer)
        root.add_transition(handler(entry, config, unparsed_keys, pointer))

    # Generate counter-examples for all forbidden types
    for type, samples in config.default_samples.items():
        if type not in types:
            for sample in samples:
                root.add_transition(SetValueLeaf(None, False, sample))

    # if unparsed_keys:
    #     raise JsonSchemaException(f"Unknown keys {unparsed_keys} at '{path}'", path)
    return root


def parse_dict(data: dict, config: Config, pointer: JsonPointer) -> Node:
    root = NoOpDecision(str(pointer), False)
    unparsed_keys = set(data.keys())
    any_of = _read_list(data, 'anyOf', unparsed_keys, pointer, [])

    for idx, entry in enumerate(any_of):
        root.add_transition(parse_any_of_entry(
            entry, config, pointer + 'anyOf' + idx
        ))

    return root


def parse(data: dict, config=None) -> Node:
    if config is None:
        config = default_config()

    pointer = JsonPointer()
    unparsed_keys = set(data.keys())

    # Read definitions
    all_nodes: List[Node] = []
    definitions = _read_dict(data, '$defs', unparsed_keys, pointer, {})
    for key, definition in definitions.items():
        sub_path = pointer + '$defs' + key
        node = parse_dict(definition, config, sub_path)
        all_nodes.append(node)

    # Read root
    root = parse_dict(data, config, pointer)
    root = root.resolve(all_nodes)

    # root.optimize()

    # prepend input / output nodes
    create_input = CreateInputNode()
    super_root = NoOpDecision(None, True)
    create_input.add_transition(super_root)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutputNode())

    return create_input
