from typing import List, Union, Set, Dict, Tuple
from fences.core.exception import NormalizationException
from fences.json_schema.json_pointer import JsonPointer
import math
import hashlib
import json
import copy


SchemaType = Union[dict, bool]

NORM_FALSE = {'anyOf': [{'enum': []}]}
NORM_TRUE = {'anyOf': [{}]}

# This list does not contain 'integer' on purpose, see _simplify_type
ALL_TYPES = [
    'number',
    'boolean',
    'string',
    'null',
    'object',
    'array'
]


class Resolver:

    def __init__(self, schema: SchemaType):
        self.schema = schema
        self.cache = {}

    def resolve(self, pointer: JsonPointer) -> SchemaType:
        return pointer.lookup(self.schema)

    def add_normalized_schema(self, pointer: JsonPointer):
        key = str(pointer)
        assert key not in self.cache


def _invert_type(t: Union[str, List[str]]):
    return {'type': list(set(ALL_TYPES) - set(t))}


def _invert_properties(props: dict):
    new_props = {name: {'not': prop} for name, prop in props.items()}
    return {
        'type': 'object',
        'properties': new_props,
        'required': list(props.keys())
    }

def _invert_items(items: dict):
    return {
        'type': 'array',
        'items': {'not': items}
    }

_inverters = {
    'minimum': lambda x: {'type': ['number'], 'exclusiveMaximum': x},
    'maximum': lambda x: {'type': ['number'], 'exclusiveMinimum': x},
    'exclusiveMinimum': lambda x: {'type': ['number'], 'maximum': x},
    'exclusiveMaximum': lambda x: {'type': ['number'], 'minimum': x},
    'type': _invert_type,
    'enum': lambda x: {'NOT_enum': x},
    'NOT_enum': lambda x: {'enum': x},
    'maxLength': lambda x: {'type': ['string'], 'minLength': x},
    'minLength': lambda x: {'type': ['string'], 'maxLength': x},
    'properties': _invert_properties,
    'multipleOf': lambda x: {'type': ['number'], 'NOT_multipleOf': x},
    'required': lambda x: {'type': ['object'], 'properties': {i: False for i in x}},
    #'required': lambda x: {'type': ['object']},
    'items': _invert_items,
    'minItems': lambda x: {'type': 'array', 'maxItems': x},
    'pattern': lambda x: {'type': 'string', 'pattern': f"!({x})"}
}


def _invert(trivial_schema: dict) -> dict:
    # NOT(a and b and c)
    # = NOT(a) or NOT(b) or NOT(c)
    result = []
    if len(trivial_schema) == 0:
        return NORM_FALSE.copy()
    for key, value in trivial_schema.items():
        if key in _inverters:
            result.append(_inverters[key](value))
        else:
            raise NormalizationException(f"Cannot invert {key}")
    return {'anyOf': result}


def invert(norm_schema: dict, full_merge: bool) -> dict:
    return merge([
        _invert(i)
        for i in norm_schema['anyOf']
    ], full_merge)


def _merge_type(a: Union[List[str], str], b: Union[List[str], str]) -> List[str]:
    if isinstance(a, str):
        a = [a]
    if isinstance(b, str):
        b = [b]
    return list(set(a) & set(b))

def _merge_enums(a: List[any], b: List[any]) -> List[any]:
    # TODO: we assume string lists, we is not generic
    a = set(a)
    b = set(b)
    return list(a & b)

def _float_gcd(a, b, rtol = 1e-05, atol = 1e-08):
    t = min(abs(a), abs(b))
    while abs(b) > rtol * t + atol:
        a, b = b, a % b
    return a

_simple_mergers = {
    'required': lambda a, b: list(set(a) | set(b)),
    'multipleOf': lambda a, b: abs(a*b) // _float_gcd(a, b),
    'items': lambda a, b: {'allOf': [a, b]},
    'minimum': lambda a, b: max(a, b),
    'maximum': lambda a, b: min(a, b),
    'type': _merge_type,
    'minItems': lambda a, b: max(a, b),
    'maxItems': lambda a, b: min(a, b),
    'pattern': lambda a, b: f"({a})&({b})",
    'minLength': lambda a, b: max(a, b),
    'maxLength': lambda a, b: min(a, b),
    'enum': lambda a, b: a + b,
    'format': lambda a, b: a,  # todo
    'deprecated': lambda a, b: a or b,
    'NOT_enum': lambda a, b: a + b,
    'enum': _merge_enums,
}


def _merge_properties(result: dict, to_add: dict) -> dict:
    # Must merge properties and additionalProperties together
    # Schema 1: a: 1a,    b: 1b,              ...: 1n
    # Schema 2:           b: 2b,    c: 2c,    ...: 2n
    # Result:   a: 1a+2n, b: 1b+2b, c: 2c+1n, ...: 1n+2n

    props_result = result.get('properties', {})
    props_result = copy.deepcopy(props_result) # TODO: why?
    props_to_add = to_add.get('properties', {})
    additional_result = result.get('additionalProperties')
    additional_to_add = to_add.get('additionalProperties')
    for property_name, schema in props_result.items():
        if property_name in props_to_add:
            props_result[property_name] = {'allOf': [
                schema, props_to_add[property_name]
            ]}
        else:
            if additional_to_add is None:
                props_result[property_name] = schema
            else:
                props_result[property_name] = {'allOf': [
                    schema, additional_to_add
                ]}
    for property_name, schema in props_to_add.items():
        if property_name not in props_result:
            if additional_result is None:
                props_result[property_name] = schema
            else:
                props_result[property_name] = {'allOf': [
                    schema, additional_result
                ]}
    return props_result


def _merge_prefix_items(result: dict, to_add: dict) -> dict:
    # Must merge items and prefixItems together
    # Schema 1: a,   a,   a,   b...
    # Schema 2: c,   c,   d...
    # Result:   a+c, a+c, a+d, b+d...

    items_a = result.get('items', NORM_TRUE.copy())
    prefix_items_a = result.get('prefixItems', [])
    items_b = to_add.get('items', NORM_TRUE.copy())
    prefix_items_b = to_add.get('prefixItems', [])
    assert isinstance(prefix_items_a, list)
    assert isinstance(prefix_items_b, list)
    result_prefix_items = []

    if len(prefix_items_a) > len(prefix_items_b):
        prefix_items_b += [items_b] * \
            (len(prefix_items_a) - len(prefix_items_b))
    else:
        prefix_items_a += [items_a] * \
            (len(prefix_items_b) - len(prefix_items_a))

    assert len(prefix_items_a) == len(prefix_items_b)
    for i, j in zip(prefix_items_a, prefix_items_b):
        result_prefix_items.append({'allOf': [i, j]})

    return result_prefix_items


_complex_mergers = {
    'prefixItems': _merge_prefix_items,
    'properties': _merge_properties,
}


def _merge(result: dict, to_add: dict) -> None:

    for key, merger in _complex_mergers.items():
        if key in result or key in to_add:
            result[key] = merger(result, to_add)

    for key, value in result.items():
        if key not in to_add:
            # nothing to merge
            continue
        if key in _simple_mergers:
            merger = _simple_mergers[key]
            result[key] = merger(value, to_add[key])
        elif key in _complex_mergers:
            continue
        else:
            raise NormalizationException(f"Do not know how to merge '{key}'")

    # Copy all remaining keys
    for key, value in to_add.items():
        if key not in result and key not in _complex_mergers:
            result[key] = value


def merge(schemas: List[SchemaType], full_merge: bool) -> SchemaType:
    if full_merge:
        return merge_full(schemas)
    else:
        return merge_simple(schemas)


def merge_simple(schemas: List[SchemaType]) -> SchemaType:
    assert len(schemas) > 0
    results = []
    num = max([len(s['anyOf']) for s in schemas])
    for idx in range(num):
        result = {}
        for schema in schemas:
            ao = schema['anyOf']
            if len(ao) == 0:
                continue
            option = ao[idx % len(ao)]
            _merge(result, option)
        results.append(result)
    return {'anyOf': results}


def merge_full(schemas: List[SchemaType]) -> SchemaType:
    assert len(schemas) > 0
    result = [{}]
    for schema in schemas:
        new_result = []
        for option in schema['anyOf']:
            for i in result:
                ii = i.copy()
                _merge(ii, option)
                new_result.append(ii)
        result = new_result
    return {'anyOf': result}


def _simplify_type(schema: dict):
    if 'type' not in schema:
        return schema
    side_schema = schema.copy()
    types = schema.pop('type')
    if not isinstance(types, list):
        types = [types]
    types: Set[str] = set(types)

    # number contains integer
    if 'number' in types:
        if 'integer' in types:
            types.remove('integer')
    else:
        if 'integer' in types:
            types.remove('integer')
            types.add('number')
            side_schema['type'] = list(types)
            return {'allOf': [
                {'multipleOf': 1},
                side_schema
            ]}
    side_schema['type'] = list(types)
    return side_schema


def _simplify_if_then_else(schema: dict):
    # This is valid iff:
    # (not(IF) or THEN) and (IF or ELSE)
    # <==>
    #   ( IF and THEN ) or
    #   ( not(IF) and ELSE)

    # See https://json-schema.org/understanding-json-schema/reference/conditionals.html#implication
    if 'if' not in schema and 'then' not in schema and 'else' not in schema:
        return schema
    side_schema = schema.copy()
    if_schema = side_schema.pop('if', None)
    then_schema = side_schema.pop('then', None)
    else_schema = side_schema.pop('else', None)

    if if_schema is None:
        return side_schema

    if then_schema is None and else_schema is None:
        return {}

    any_of = []

    if then_schema is None:
        then_schema = {}
    any_of.append({'allOf': [
        if_schema,
        then_schema
    ]})

    if else_schema is None:
        else_schema = {}
    any_of.append({'allOf': [
        {'not': if_schema},
        else_schema
    ]})

    result = {'allOf': [
        side_schema,
        {'anyOf': any_of}
    ]}
    return result

def _simplify_const(schema: dict) -> dict:
    if 'const' not in schema:
        return schema
    schema = schema.copy()
    const = schema.pop('const')
    if 'enum' in schema:
        schema['enum'] += [const]
    else:
        schema['enum'] = [const]
    return schema

def _simplify_dependent_required(schema: dict) -> dict:
    if 'dependentRequired' not in schema:
        return schema
    # dependentRequired:
    #   a: ["b"]
    #
    # a exists | b exists | valid
    # no       | no       | yes
    # yes      | no       | no
    # no       | yes      | yes
    # yes      | yes      | yes
    # 
    # anyOf:
    # - { "properties": {"a": False, "b": True }, "required": [] }
    # - { "properties": {"a": True,  "b": True }, "required": ["a", "b"]}

    schema = schema.copy()
    dependent_required = schema.pop('dependentRequired')
    options = []
    for property, requires in dependent_required.items():
        props1 = {name: True for name in requires}
        props1[property] = False

        props2 = {name: True for name in requires}
        props2[property] = True
        options.append({"anyOf": [
            {"properties": props1},
            {"properties": props2, "required": requires + [property]}
        ]})
    return {"allOf": [schema] + options }

def _inline_refs(schema: dict, resolver: Resolver) -> Tuple[dict, bool]:
    if schema is False:
        return NORM_FALSE.copy(), False

    if schema is True:
        return NORM_TRUE.copy(), False

    contains_refs = False

    if '$ref' in schema:
        side_schema = schema.copy()
        del side_schema['$ref']
        pointer = JsonPointer.from_string(schema['$ref'])
        ref_schema = resolver.resolve(pointer)
        # We need a deepcopy here, otherwise we cannot stringify it due to circular references
        ref_schema = copy.deepcopy(ref_schema)
        schema = {'allOf': [side_schema, ref_schema]}
        contains_refs = True

    for kw in ['anyOf', 'allOf', 'oneOf']:
        for idx, sub_schema in enumerate(schema.get(kw, [])):
            (new_schema, new_contains_refs) = _inline_refs(sub_schema, resolver)
            schema[kw][idx] = new_schema
            contains_refs = contains_refs or new_contains_refs
    for kw in ['not', 'if', 'then', 'else']:
        if kw in schema:
            (new_schema, new_contains_refs) = _inline_refs(
                schema[kw], resolver)
            schema[kw] = new_schema
            contains_refs = contains_refs or new_contains_refs

    return schema, contains_refs


def _to_dnf(schema: dict, full_merge: bool) -> dict:

    if schema is False:
        return NORM_FALSE.copy()

    if schema is True:
        return NORM_TRUE.copy()

    schema = copy.deepcopy(schema)
    schema = _simplify_const(schema)
    schema = _simplify_if_then_else(schema)
    schema = _simplify_type(schema)
    schema = _simplify_dependent_required(schema)

    # anyOf
    if 'anyOf' in schema:
        any_ofs = []
        for sub_schema in schema['anyOf']:
            normalized_sub_schema = _to_dnf(
                sub_schema, full_merge)
            any_ofs.extend(normalized_sub_schema['anyOf'])
    else:
        any_ofs = [{}]

    # oneOf
    if 'oneOf' in schema:
        one_ofs = []
        normalized_sub_schemas = [
            _to_dnf(sub_schema, full_merge)
            for sub_schema in schema['oneOf']
        ]
        for idx, _ in enumerate(normalized_sub_schemas):
            options = merge([
                invert(i, full_merge) if sub_idx == idx else i
                for sub_idx, i in enumerate(normalized_sub_schemas)
            ], full_merge)
            one_ofs.extend(options['anyOf'])
    else:
        one_ofs = [{}]

    # allOf
    all_ofs = []
    side_schema = schema.copy()
    for sub_schema in ['allOf', 'anyOf', 'oneOf', 'not']:
        if sub_schema in side_schema:
            del side_schema[sub_schema]
    all_ofs.append({'anyOf': [side_schema]})
    for sub_schema in schema.get('allOf', []):
        all_ofs.append(_to_dnf(sub_schema, full_merge))

    # not
    if 'not' in schema:
        norm_schema = _to_dnf(schema['not'], full_merge)
        all_ofs.append(invert(norm_schema, full_merge))

    s = merge(all_ofs, full_merge)

    result = merge([
        {'anyOf': any_ofs},
        {'anyOf': one_ofs},
        s
    ], full_merge)
    return result


def _normalize(schema: dict, resolver: Resolver, new_refs: Dict[str, dict], full_merge: bool) -> dict:
    if schema is False:
        return NORM_FALSE.copy()

    if schema is True:
        return NORM_TRUE.copy()

    if len(schema) == 0:
        return NORM_TRUE.copy()

    # Check cache (to avoid stack overflows due to recursive schemas)
    new_ref_name = hashlib.sha1(json.dumps(schema).encode()).hexdigest()
    if new_ref_name in new_refs:
        return {'anyOf': [{'$ref': f"#/$defs/{new_ref_name}"}]}

    # Inline all references (if any)
    (schema, contains_refs) = _inline_refs(schema, resolver)

    result = _to_dnf(schema, full_merge)

    # Store new schema if sub-schemas later try to reference it
    if contains_refs:
        new_refs[new_ref_name] = result

    # Iterate sub-schemas
    for sub_schema in result['anyOf']:
        for kw in ['additionalProperties', 'items', 'additionalItems', 'contains']:
            if kw in sub_schema:
                sub_schema[kw] = _normalize(
                    sub_schema[kw], resolver, new_refs, full_merge)

        props: dict = sub_schema.get('properties', {})
        for name, sub_sub_schema in props.items():
            props[name] = _normalize(
                sub_sub_schema, resolver, new_refs, full_merge)

        prefix_items: list = sub_schema.get('prefixItems', [])
        for idx, sub_sub_schema in enumerate(prefix_items):
            prefix_items[idx] = _normalize(
                sub_sub_schema, resolver, new_refs, full_merge)

    # Return
    if contains_refs:
        return {'anyOf': [{'$ref': f"#/$defs/{new_ref_name}"}]}
    else:
        return result


def normalize(schema: SchemaType, full_merge: bool = True) -> any:
    if schema is False:
        return NORM_FALSE.copy()

    if schema is True:
        return NORM_TRUE.copy()

    if not isinstance(schema, dict):
        raise NormalizationException(
            f"Schema must be of type bool or dict, got {type(schema)}")

    # TODO: deepcopy really needed?
    new_schema = copy.deepcopy(schema)
    for kw in ['$schema', '$defs']:
        if kw in schema:
            del new_schema[kw]
    resolver = Resolver(schema)
    new_refs: Dict[str, dict] = {}
    new_schema = _normalize(new_schema, resolver, new_refs, full_merge)
    if '$schema' in schema:
        new_schema['$schema'] = schema['$schema']
    new_schema['$defs'] = new_refs
    return new_schema


def check_normalized(schema: SchemaType) -> None:
    resolver = Resolver(schema)
    checked_refs = set()
    _check_normalized(schema, resolver, checked_refs)


def _check_normalized(schema: SchemaType, resolver: Resolver, checked_refs: Set[str]) -> None:
    if not isinstance(schema, dict):
        raise NormalizationException(f"Must be a dict, got {schema}")

    keys = set(schema.keys())
    for i in ['$schema', '$defs']:
        if i in keys:
            keys.remove(i)
    if len(keys) != 1 or 'anyOf' not in keys:
        raise NormalizationException(
            f"Schema has one key not being anyOf, got {keys}")

    any_of = schema['anyOf']
    if not isinstance(any_of, list):
        raise NormalizationException(f"anyOf must be a list, is '{any_of}'")

    for idx, sub_schema in enumerate(any_of):

        # Disallowed keywords in any-of elements
        for i in ['anyOf', 'allOf', 'oneOf', 'not', 'if', 'then', 'else', 'const']:
            if i in sub_schema:
                raise NormalizationException(
                    f"'{i}' not allowed in normalized sub_schema {idx}")

        if '$ref' in sub_schema:
            if len(sub_schema.keys()) != 1:
                raise NormalizationException(
                    f"Sub-schema {idx} has other keys beside $ref")
            ref = sub_schema['$ref']
            if ref not in checked_refs:
                checked_refs.add(ref)
                pointer = JsonPointer.from_string(ref)
                _check_normalized(resolver.resolve(
                    pointer), resolver, checked_refs)

        # Traverse sub-schemas
        for kw in ['additionalProperties', 'items', 'additionalItems', 'contains']:
            if kw in schema:
                _check_normalized(schema[kw], resolver, checked_refs)

        for i in sub_schema.get('properties', {}).values():
            _check_normalized(i, resolver, checked_refs)

        for i in sub_schema.get('prefixItems', []):
            _check_normalized(i, resolver, checked_refs)
