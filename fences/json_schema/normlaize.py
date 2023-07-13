from typing import List, Union, Set, Dict
from fences.core.exception import NormalizationException
from fences.json_schema.json_pointer import JsonPointer
import math

SchemaType = Union[dict, bool]

NORM_FALSE = {'anyOf': [{'type': []}]}
NORM_TRUE = {'anyOf': [{}]}


class Resolver:

    def __init__(self, schema: SchemaType):
        self.schema = schema
        self.cache = {}

    def resolve(self, pointer: JsonPointer) -> SchemaType:
        return pointer.lookup(self.schema)

    def add_normalized_schema(self, pointer: JsonPointer):
        key = str(pointer)
        assert key not in self.cache


def invert(schema: dict) -> dict:
    return schema


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


def _merge_properties(result: dict, to_add: dict, resolver: Resolver, new_refs: Dict[str, dict]) -> dict:
    # Must merge properties and additionalProperties together
    # Schema 1: a: 1a,    b: 1b,              ...: 1n
    # Schema 2:           b: 2b,    c: 2c,    ...: 2n
    # Result:   a: 1a+2n, b: 1b+2b, c: 2c+1n, ...: 1n+2n

    props_result = result.get('properties', {})
    props_to_add = to_add.get('properties', {})
    additional_result = result.get('additionalProperties', NORM_TRUE)
    additional_to_add = to_add.get('additionalProperties', NORM_TRUE)
    for property_name, schema in props_result.items():
        if property_name in props_to_add:
            props_result[property_name] = merge(
                [schema, props_to_add[property_name]], resolver, new_refs)
        else:
            props_result[property_name] = merge(
                [schema, additional_to_add], resolver, new_refs)
    for property_name, schema in props_to_add.items():
        if property_name not in props_result:
            props_result[property_name] = merge(
                [schema, additional_result], resolver, new_refs)
    return props_result


def _merge_prefix_items(result: dict, to_add: dict, resolver: Resolver) -> dict:
    # Must merge items and prefixItems together
    # Schema 1: a,   a,   a,   b...
    # Schema 2: c,   c,   d...
    # Result:   a+c, a+c, a+d, b+d...

    items_a = result.get('items', NORM_TRUE)
    prefix_items_a = result.get('prefixItems', [])
    items_b = to_add.get('items', NORM_TRUE)
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
        result_prefix_items.append(merge([i, j], resolver))

    return result_prefix_items


_complex_mergers = {
    'prefixItems': _merge_prefix_items,
    'properties': _merge_properties,
}


def _merge(result: dict, to_add: dict, resolver: Resolver, new_refs: Dict[str, dict]) -> None:

    for key, merger in _complex_mergers.items():
        if key in result or key in to_add:
            result[key] = merger(result, to_add, resolver, new_refs)

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


def inline_refs(schema: dict, resolver: Resolver, new_refs: Dict[str, dict]) -> dict:
    try:
        ref = schema['$ref']
    except KeyError:
        return schema
    assert len(schema.keys()) == 1
    pointer = JsonPointer.from_string(ref)
    new_schema = resolver.resolve(pointer)
    return inline_refs(new_schema, resolver, new_refs)


def merge(schemas: List[SchemaType], resolver: Resolver, new_refs: Dict[str, dict]) -> SchemaType:
    assert len(schemas) > 0
    result = [{}]
    for schema in schemas:
        new_result = []
        for option in schema['anyOf']:
            option = inline_refs(option, resolver, new_refs)
            for i in result:
                ii = i.copy()
                _merge(ii, option, resolver, new_refs)
                new_result.append(ii)
        result = new_result
    return {'anyOf': result}


def _simplify_if_then_else(schema: dict, resolver: Resolver):
    # This is valid iff:
    # (not(IF) or THEN) and (IF or ELSE)
    # <==>
    #   ( IF and THEN ) or
    #   ( not(IF) and ELSE)

    # See https://json-schema.org/understanding-json-schema/reference/conditionals.html#implication
    if 'if' not in schema and 'then' not in schema and 'else' not in schema:
        return schema
    sub_schema = schema.copy()
    if_schema = sub_schema.pop('if', None)
    then_schema = sub_schema.pop('then', True)
    else_schema = sub_schema.pop('else', True)
    any_of = []
    if if_schema is not None and else_schema is not None:
        any_of.append({'allOf': [
            sub_schema,
            {'not': if_schema},
            else_schema
        ]})
    if if_schema is not None and then_schema is not None:
        any_of.append({'allOf': [
            sub_schema,
            if_schema,
            then_schema
        ]})
    if not any_of:
        return {'anyOf': [{}]}
    return {'anyOf': any_of}


def _normalize(schema: dict, resolver: Resolver, new_refs: Dict[str, dict]) -> dict:

    if schema is False:
        return NORM_FALSE

    if schema is True:
        return NORM_TRUE

    # Iterate sub-schemas
    schema = schema.copy()
    for kw in ['additionalProperties', 'items', 'additionalItems']:
        if kw in schema:
            schema[kw] = _normalize(schema[kw], resolver, new_refs)

    for name, sub_schema in schema.get('properties', {}).items():
        schema['properties'][name] = _normalize(sub_schema, resolver, new_refs)

    prefix_items = schema.get('prefixItems', [])
    for idx, sub_schema in enumerate(prefix_items):
        prefix_items[idx] = _normalize(prefix_items[idx], resolver)

    if '$ref' in schema:
        ref = schema['$ref']
        if ref not in new_refs:
            pointer = JsonPointer.from_string(ref)
            new_refs[ref] = None
            new_refs[ref] = _normalize(resolver.resolve(pointer), resolver, new_refs)

    # Simplify
    schema = _simplify_if_then_else(schema, resolver)

    # Shortcut for trivial schemas
    has_logical_applicators = False
    for i in ['not', 'allOf', 'oneOf', 'anyOf']:
        if i in schema:
            has_logical_applicators = True
    if not has_logical_applicators:
        return {'anyOf': [schema]}

    # anyOf
    if 'anyOf' in schema:
        any_ofs = []
        for sub_schema in schema['anyOf']:
            normalized_sub_schema = _normalize(sub_schema, resolver, new_refs)
            any_ofs.extend(normalized_sub_schema['anyOf'])
    else:
        any_ofs = [{}]

    # oneOf
    if 'oneOf' in schema:
        one_ofs = []
        normalized_sub_schemas = [
            _normalize(sub_schema, resolver, new_refs)
            for sub_schema in schema['oneOf']
        ]
        for idx, _ in enumerate(normalized_sub_schemas):
            options = merge([
                invert(i) if i == idx else i
                for i in normalized_sub_schemas
            ], resolver, new_refs)
            one_ofs.extend(options['anyOf'])
    else:
        one_ofs = [{}]

    # allOf
    all_ofs = []
    side_schema = schema.copy()
    for i in ['allOf', 'anyOf', 'oneOf', 'not']:
        if i in side_schema:
            del side_schema[i]
    all_ofs.append(_normalize(side_schema, resolver, new_refs))
    for sub_schema in schema.get('allOf', []):
        all_ofs.append(_normalize(sub_schema, resolver, new_refs))
    s = merge(all_ofs, resolver, new_refs)

    return merge([
        {'anyOf': any_ofs},
        {'anyOf': one_ofs},
        s
    ], resolver, new_refs)


def normalize(schema: SchemaType) -> any:
    if schema is False:
        return {'type': []}

    if schema is True:
        return {}

    if not isinstance(schema, dict):
        raise NormalizationException(
            f"Schema must be of type bool or dict, got {type(schema)}")
    new_schema = schema.copy()
    if '$schema' in schema:
        del new_schema['$schema']
    resolver = Resolver(schema)
    new_refs: Dict[str, dict] = {}
    new_schema = _normalize(new_schema, resolver, new_refs)
    if isinstance(new_schema, dict):
        if '$schema' in schema:
            new_schema['$schema'] = schema['$schema']
    return new_schema


def check_normalized(schema: SchemaType) -> None:
    resolver = Resolver(schema)
    checked_refs = set()
    _check_normalized(schema, resolver, checked_refs)


def _check_normalized(schema: SchemaType, resolver: Resolver, checked_refs: Set[str]) -> None:
    if not isinstance(schema, dict):
        raise NormalizationException(f"Must be a dict, got {schema}")

    keys = set(schema.keys())
    for i in ['$schema']:
        if i in keys:
            keys.remove(i)
    if 'anyOf' not in keys or len(keys) != 1:
        raise NormalizationException(f"anyOf must be the only key, got {keys}")

    any_of = schema['anyOf']
    if not isinstance(any_of, list):
        raise NormalizationException(f"anyOf must be a list, is '{any_of}'")

    for idx, sub_schema in enumerate(any_of):

        # Disallowed keywords in any-of elements
        for i in ['anyOf', 'allOf', 'oneOf', 'not', 'if', 'then', 'else']:
            if i in sub_schema:
                raise NormalizationException(
                    f"'{i}' not allowed in normalized sub_schema {idx}")

        # Traverse sub-schemas
        for kw in ['additionalProperties', 'items', 'additionalItems']:
            if kw in schema:
                _check_normalized(schema[kw], resolver)

        for sub_schema in schema.get('properties', {}).values():
            _check_normalized(sub_schema, resolver)

        for sub_schema in schema.get('prefixItems', []):
            _check_normalized(sub_schema, resolver)

        if '$ref' in sub_schema:
            ref = sub_schema['$ref']
            if ref not in checked_refs:
                checked_refs.add(ref)
                pointer = JsonPointer.from_string(ref)
                _check_normalized(resolver.resolve(pointer), resolver)
