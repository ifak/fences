from typing import List, Union, Callable
from fences.core.exception import NormalizationException
from fences.json_schema.json_pointer import JsonPointer
import math

SchemaType = Union[dict, bool]


class Resolver:

    def __init__(self, schema: SchemaType):
        self.schema = schema

    def resolve(self, pointer: JsonPointer) -> SchemaType:
        return pointer.lookup(self.schema)


def _merge_type(a: Union[List[str], str], b: Union[List[str], str]) -> List[str]:
    if isinstance(a, str):
        a = [a]
    if isinstance(b, str):
        b = [b]
    return list(set(a) & set(b))


_simple_mergers = {
    'required': lambda a, b: list(set(a) | set(b)),
    'multipleOf': lambda a, b: abs(a*b) // math.gcd(a, b),
    'items': lambda a, b: merge([a, b]),
    'minimum': lambda a, b: max(a, b),
    'maximum': lambda a, b: min(a, b),
    'type': _merge_type,
}


def _merge_properties(result: dict, to_add: dict, resolver: Resolver) -> dict:
    # Must merge properties and additionalProperties together
    # Schema 1: a: 1a,    b: 1b,              ...: 1n
    # Schema 2:           b: 2b,    c: 2c,    ...: 2n
    # Result:   a: 1a+2n, b: 1b+2b, c: 2c+1n, ...: 1n+2n

    props_result = result.get('properties', {})
    props_to_add = to_add.get('properties', {})
    additional_result = result.get('additionalProperties', {})
    additional_to_add = to_add.get('additionalProperties', {})
    for property_name, schema in props_result.items():
        if property_name in to_add:
            props_result[property_name] = merge(
                [schema, props_to_add[property_name]])
        else:
            props_result[property_name] = merge(
                [schema, additional_to_add], resolver)
    for property_name, schema in props_to_add.items():
        if property_name not in props_result:
            props_result[property_name] = merge(
                [schema, additional_result], resolver)
    return props_result


def _merge_prefix_items(result: dict, to_add: dict, resolver: Resolver) -> dict:
    # Must merge items and prefixItems together
    # Schema 1: a,   a,   a,   b...
    # Schema 2: c,   c,   d...
    # Result:   a+c, a+c, a+d, b+d...

    items_a = result.get('items', {})
    prefix_items_a = result.get('prefixItems', [])
    items_b = to_add.get('items', {})
    prefix_items_b = to_add.get('prefixItems', [])
    assert isinstance(items_a, dict)
    assert isinstance(items_b, dict)
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
        result_prefix_items.append(merge([i, j], resolver))

    return result_prefix_items


_complex_mergers = {
    'prefixItems': _merge_prefix_items,
    'properties': _merge_properties,
}


def _merge(result: dict, to_add: dict, resolver: Resolver) -> None:

    for key, merger in _complex_mergers.items():
        if key in result or key in to_add:
            result[key] = merger(result, to_add, resolver)

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


def inline_refs(schema: dict, resolver: Resolver) -> dict:
    try:
        ref = schema['$ref']
    except KeyError:
        return schema
    assert len(schema.keys()) == 1
    pointer = JsonPointer.from_string(ref)
    new_schema = resolver.resolve(pointer)
    return inline_refs(new_schema, resolver)


def merge(schemas: List[SchemaType], resolver: Resolver) -> SchemaType:
    assert len(schemas) > 0
    result = {}
    if any([i is False for i in schemas]):
        return False
    if all([i is True for i in schemas]):
        return True
    for schema in schemas:
        if schema is True:
            continue
        schema = inline_refs(schema, resolver)
        _merge(result, schema, resolver)
    return result


def _normalize_all_of(schema: dict, resolver: Resolver) -> SchemaType:
    if not isinstance(schema, dict) or 'allOf' not in schema:
        return schema
    _iterate_sub_schemas(schema, resolver, _normalize_if_then_else)

    sub_schema = schema.copy()
    del sub_schema['allOf']
    result = merge(schema['allOf'] + [sub_schema], resolver)
    return _normalize_all_of(result, resolver)


def _normalize_one_any_of(kw: str, schema: dict, resolver: Resolver) -> SchemaType:
    if not isinstance(schema, dict) or kw not in schema:
        return schema
    sub_schema = schema.copy()
    del sub_schema[kw]
    result = []
    for i in schema[kw]:
        result.append(merge([i, sub_schema], resolver))
    if all([i is False for i in result]):
        return False
    if len(result) == 0:
        return False
    elif len(result) == 1:
        return _normalize(result[0], resolver)
    else:
        return {kw: result}


def _normalize_if_then_else(schema: dict, resolver: Resolver):
    # This is valid iff:
    # (not(IF) or THEN) and (IF or ELSE)
    # <==>
    #   ( IF and THEN ) or
    #   ( not(IF) and ELSE)

    # See https://json-schema.org/understanding-json-schema/reference/conditionals.html#implication
    if not isinstance(schema, dict) or \
            ('if' not in schema and 'then' not in schema and 'else' not in schema):
        return schema
    sub_schema = schema.copy()
    if_schema = sub_schema.pop('if', None)
    then_schema = sub_schema.pop('then', True)
    else_schema = sub_schema.pop('else', True)
    any_of = []
    if if_schema is not None and else_schema is not None:
        any_of.append(merge([
            sub_schema,
            {'not': if_schema},
            else_schema
        ], resolver))
    if if_schema is not None and then_schema is not None:
        any_of.append(merge([
            sub_schema,
            if_schema,
            then_schema
        ], resolver))
    if not any_of:
        return True
    return {'anyOf': any_of}


def _iterate_sub_schemas(schema: dict, resolver: Resolver, callback):
    for key, sub_schema in schema.get('properties', {}).items():
        schema['properties'][key] = callback(sub_schema, resolver)
    for idx, sub_schema in enumerate(schema.get('prefixItems', [])):
        schema['prefixItems'][idx] = callback(sub_schema, resolver)
    for idx, sub_schema in enumerate(schema.get('oneOf', [])):
        schema['oneOf'][idx] = callback(sub_schema, resolver)
    for idx, sub_schema in enumerate(schema.get('anyOf', [])):
        schema['anyOf'][idx] = callback(sub_schema, resolver)
    for idx, sub_schema in enumerate(schema.get('allOf', [])):
        schema['allOf'][idx] = callback(sub_schema, resolver)
    if 'items' in schema:
        schema['items'] = callback(schema['items'], resolver)
    if 'additionalItems' in schema:
        schema['additionalItems'] = callback(
            schema['additionalItems'], resolver)
    if '$ref' in schema:
        pointer = JsonPointer.from_string(schema["$ref"])
        callback(resolver.resolve(pointer), resolver)


def _normalize(schema: dict, resolver: Resolver) -> SchemaType:
    schema = _normalize_if_then_else(schema, resolver)
    schema = _normalize_all_of(schema, resolver)
    schema = _normalize_one_any_of('anyOf', schema, resolver)
    schema = _normalize_one_any_of('oneOf', schema, resolver)
    if not isinstance(schema, dict):
        return schema
    _iterate_sub_schemas(schema, resolver, _normalize)
    return schema


def normalize(schema: SchemaType) -> any:
    if isinstance(schema, bool):
        return schema
    if not isinstance(schema, dict):
        raise NormalizationException(
            f"Schema must be of type bool or dict, got {type(schema)}")
    new_schema = schema.copy()
    if '$schema' in schema:
        del new_schema['$schema']
    resolver = Resolver(schema)
    new_schema = _normalize(new_schema, resolver)
    if isinstance(new_schema, dict):
        if '$schema' in schema:
            new_schema['$schema'] = schema['$schema']
    return new_schema


def check_normalized(schema: SchemaType) -> None:
    resolver = Resolver(schema)
    _check_normalized(schema, resolver)


def _check_normalized(schema: SchemaType, resolver: Resolver) -> None:
    if isinstance(schema, bool):
        return True
    if not isinstance(schema, dict):
        raise NormalizationException(f"Must be a dict")

    # allOf is never allowed
    if 'allOf' in schema:
        raise NormalizationException("'allOf' not allowed in schema")

    # if oneOf or anyOf is present, they must be the only keys
    unique_keys = ['oneOf', 'anyOf']
    schema_keys = set(schema.keys())
    if '$schema' in schema_keys:
        schema_keys.remove('$schema')
    for key in unique_keys:
        if key in schema_keys:
            if len(schema_keys) != 1:
                raise NormalizationException(
                    f"'{key}' must be the only key, got {list(schema.keys())}")
            value = schema[key]
            # Array must not be trivial
            if not isinstance(value, list):
                raise NormalizationException(f"Expected an array")
            if len(value) <= 1:
                raise NormalizationException(f"Trivial array")

    # Traverse sub-schemas
    def check(schema: dict, resolver: Resolver):
        _check_normalized(schema, resolver)
        return schema
    _iterate_sub_schemas(schema, resolver, check)
