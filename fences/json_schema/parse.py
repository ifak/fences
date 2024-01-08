from typing import Set, Dict, List, Optional, Union

from .exceptions import JsonSchemaException
from .config import Config
from .json_pointer import JsonPointer
from ..core.random import generate_random_string, StringProperties, generate_random_format
from .normalize import normalize

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
        default_samples={
            'string': ["string"],
            'number': [42],
            'null': [None],
            'boolean': [True, False],
            'object': [{}],
            'array': [[]]
        },
        normalize=True,
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
        raise JsonSchemaException(f"{value} is not a {typename} at {pointer}", None)
    unparsed_keys.remove(key)
    return value


def _read_float(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=_NO_DEFAULT) -> str:
    return _read_typesafe(data, key, unparsed_keys, (int, float), 'float', pointer, default)


def _read_int(data: dict, key: str, unparsed_keys: Set[str], pointer: JsonPointer, default=_NO_DEFAULT) -> str:
    v = _read_typesafe(data, key, unparsed_keys, (int, float), 'int', pointer, default)
    if v is default:
        return v
    if isinstance(v, float):
        if int(v) != v:
            raise JsonSchemaException(f"{v} is not a 'int' at {pointer}", None)
        v = int(v)
    return v


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

    additional_props = _read_dict(data, 'additionalProperties', unparsed_keys, path, {})
    min_properties = _read_int(data, 'minProperties', unparsed_keys, path, 0)
    max_properties = _read_int(data, 'maxProperties', unparsed_keys, path, 0)
    pattern_properties = _read_dict(data, 'patternProperties', unparsed_keys, path, {})
    property_names = _read_dict(data, 'propertyNames', unparsed_keys, path, {})
    unevaluated_properties = _read_dict(data, 'unevaluatedProperties', unparsed_keys, path, {})
    depended_required = _read_dict(data, 'dependentRequired', unparsed_keys, path, [])
    dependent_schema = _read_dict(data, 'dependentSchemas', unparsed_keys, path, {})
    required = _read_list(data, 'required', unparsed_keys, path, [])

    required_props: Set[str] = set()
    for idx, token in enumerate(required):
        sub_path = path + 'required' + idx
        if not isinstance(token, str):
            raise JsonSchemaException(f"'{token}' is not a string at ${sub_path}", sub_path)
        if token in required_props:
            raise JsonSchemaException(f"Duplicate token '{token}' in ${sub_path}", sub_path)
        required_props.add(token)

    super_root = NoOpDecision(f"{path}_OBJECT")

    # Properties
    root = CreateObjectNode(None, True)
    super_root.add_transition(root)
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
        if key in required_props:
            property_root.add_transition(NoOpLeaf(None, is_valid=False))
            required_props.remove(key)
        else:
            property_root.add_transition(NoOpLeaf(None, is_valid=True))

    # All remaining properties only mentioned in 'required'
    for key in required_props:
        sub_path = path + 'required' + key
        property_root = NoOpDecision(f"{sub_path}__PROP", False)
        root.add_transition(property_root)
        key_node = InsertKeyNode(f"{sub_path}__KEY", key)
        property_root.add_transition(key_node)
        value_node = generate_default_samples(config)
        key_node.add_transition(value_node)

    if not root.outgoing_transitions:
        root.add_transition(NoOpLeaf(None, True))

    return super_root


def parse_string(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision()
    pattern = _read_string(data, 'pattern', unparsed_keys, path, '')
    content_media_type = _read_string(data, 'contentMediaType', unparsed_keys, path, '')
    content_encoding = _read_string(data, 'contentEncoding', unparsed_keys, path, '')
    content_schema = _read_dict(data, 'contentSchema', unparsed_keys, path, {})
    if pattern:
        regex = pattern
    else:
        regex = None
    # TODO: use format
    format = _read_string(data, 'format', unparsed_keys, path, None)
    if format is None:
        properties = StringProperties(
            min_length=_read_int(data, 'minLength', unparsed_keys, path, 0),
            max_length=_read_int(data, 'maxLength', unparsed_keys, path, float("inf")),
            # pattern=regex,
        )
        value = generate_random_string(properties)
    else:
        value = generate_random_format(format)
    root.add_transition(SetValueLeaf(None, True, value))
    return root

def generate_default_samples(config: Config) -> Node:
    items_node = NoOpDecision(None, False)
    for samples in config.default_samples.values():
        for sample in samples:
            items_node.add_transition(SetValueLeaf(None, True, sample))
    return items_node


def parse_array(data: dict, config: Config, unparsed_keys: Set[str], pointer: JsonPointer) -> Node:
    min_items = _read_int(data, 'minItems', unparsed_keys, pointer, 1)
    max_items = _read_int(data, 'maxItems', unparsed_keys, pointer, None)
    prefix_items = _read_list(data, 'prefixItems', unparsed_keys, pointer, {})
    unique_items = _read_dict(data, 'uniqueItems', unparsed_keys, pointer, {})
    contains = _read_dict(data, 'contains', unparsed_keys, pointer, None)
    min_contains = _read_int(data, 'minContains', unparsed_keys, pointer, 1)
    max_contains = _read_int(data, 'maxContains', unparsed_keys, pointer, None)

    items = _read_dict(data, 'items', unparsed_keys, pointer, None)

    root_node = CreateArrayNode(f"{pointer}_ARRAY", True)

    # Prefix items
    if prefix_items:
        prefix_items_node = NoOpDecision(f"{pointer}_PREFIX", True)
        root_node.add_transition(prefix_items_node)
        for idx, item in enumerate(prefix_items):
            node = parse_dict(item, config, pointer + 'prefixItems' + idx)
            append_node = AppendArrayItemNode(None)
            append_node.add_transition(node)
            prefix_items_node.add_transition(append_node)

    # Contained items
    if min_contains and contains is not None:
        contains_items_node = NoOpDecision(f"{pointer}_CONTAINS", True)
        root_node.add_transition(contains_items_node)
        node = parse_dict(contains, config, pointer + 'contains')
        append_node = AppendArrayItemNode(None)
        append_node.add_transition(node)
        for _ in range(min_contains):
            contains_items_node.add_transition(append_node)
        min_items = max(0, min_items - min_contains)

    # Items
    if min_items:
        all_items_node = NoOpDecision(f"{pointer}_ITEMS", True)
        root_node.add_transition(all_items_node)
        if items is None:
            items_node = generate_default_samples(config)
        else:
            items_node = parse_dict(items, config, pointer + 'items')

        for _ in range(min_items):
            append_node = AppendArrayItemNode(None)
            append_node.add_transition(items_node)
            all_items_node.add_transition(append_node)

    return root_node


def parse_boolean(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    root = NoOpDecision(f"{path}_BOOLEAN")
    root.add_transition(SetValueLeaf(None, True, value=True))
    root.add_transition(SetValueLeaf(None, True, value=False))
    return root

def parse_number(data: dict, config: Config, unparsed_keys: Set[str], path: JsonPointer) -> Node:
    minimum = _read_float(data, 'minimum', unparsed_keys, path, None)
    minimum_exclusive = _read_float(data, 'exclusiveMinimum', unparsed_keys, path, None)
    maximum = _read_float(data, 'maximum', unparsed_keys, path, None)
    maximum_exclusive = _read_float(data, 'exclusiveMaximum', unparsed_keys, path, None)
    multiple_of = _read_float(data, 'multipleOf', unparsed_keys, path, None)

    if minimum_exclusive is not None:
        minimum = minimum_exclusive + 1  # TODO: actually just add one bit (https://docs.python.org/3/tutorial/floatingpoint.html)
    if maximum_exclusive is not None:
        maximum = maximum_exclusive - 1  # TODO: actually just subtract one bit

    invalid_values = []
    if minimum is not None:
        invalid_values.append(minimum - 1)
    if maximum is not None:
        invalid_values.append(maximum + 1)

    valid_value = minimum or maximum or 0
    if multiple_of is not None and abs(multiple_of) > 1e-5:
        valid_value = (int(valid_value / multiple_of)) * multiple_of
        if minimum is not None and valid_value < minimum:
            valid_value += multiple_of

    root = NoOpDecision(f"{path}_NUMBER")
    root.add_transition(SetValueLeaf(None, True, valid_value))
    for value in invalid_values:
        root.add_transition(SetValueLeaf(None, False, value))

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
    any_of = _read_list(data, 'anyOf', unparsed_keys, pointer)

    for idx, entry in enumerate(any_of):
        root.add_transition(parse_any_of_entry(
            entry, config, pointer + 'anyOf' + idx
        ))

    return root


def parse(data: dict, config=None) -> Node:
    if config is None:
        config = default_config()

    if config.normalize:
        data = normalize(data)

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

    root.optimize()

    # prepend input / output nodes
    create_input = CreateInputNode()
    super_root = NoOpDecision(None, True)
    create_input.add_transition(super_root)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutputNode())

    return create_input
