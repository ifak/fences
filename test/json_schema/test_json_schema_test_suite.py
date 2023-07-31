import os
import yaml
import json

from unittest import TestCase
from jsonschema import validate, exceptions, validators, _utils
from fences.json_schema.normlaize import normalize, check_normalized
from fences.core.exception import JsonPointerException, NormalizationException
from fences import parse_json_schema
from fences.json_schema.exceptions import JsonSchemaException
from dataclasses import dataclass


@dataclass
class Stats:
    num_skipped = 0
    num_failed = 0
    num_succeeded = 0


class RasingResolverException(Exception):
    pass


class RaisingResolver(validators.RefResolver):
    def __init__(self):
        pass

    def resolve(self, ref):
        raise RasingResolverException()

    def push_scope(self, scope):
        raise RasingResolverException()

    def pop_scope(self):
        raise RasingResolverException()

    def resolve_from_url(self, url):
        raise RasingResolverException()

    def resolve_fragment(self, document, fragment):
        raise RasingResolverException()

    def resolve_remote(self, uri):
        raise RasingResolverException()

script_dir = os.path.dirname(os.path.realpath(__file__))


def invert(validator):
    """
    Returns a validator with inverted semantic
    """
    def impl(validator, local_schema, instance, schema):
        if validator.evolve(schema=local_schema).is_valid(instance):
            message = f"{instance!r} should not be valid under {local_schema!r}"
            yield exceptions.ValidationError(message)
    return impl

def validated_type(validator, types, instance, schema):
    """
    A type validator which is able to handle empty type list
    For the original types validator, the following schema accepts everything
      {"type": []}
    This validator, *rejects* everything
    """
    if not isinstance(types, list):
        types = [types]
    if not types:
        yield exceptions.ValidationError(f"{instance!r} is alway invalid")
    if not any(validator.is_type(instance, type) for type in types):
        reprs = ", ".join(repr(type) for type in types)
        yield exceptions.ValidationError(f"{instance!r} is not of type {reprs}")

class JsonSchemaTestSuite(TestCase):

    def skip(self, schema_orig):
        blacklist = [
            'patternProperties',
            'unevaluatedItems',
            'unevaluatedProperties',
            'multipleOf',
            'dynamicRef',
            '$id',
        ]
        as_text = json.dumps(schema_orig)
        for i in blacklist:
            if i in as_text:
                return True
        return False

    def test_json_schema_test_suite(self):
        root = os.path.join(
            script_dir, '../fixtures/JSON-Schema-Test-Suite/tests/draft2020-12')
        stats = Stats()
        output = False
        for file in sorted(os.listdir(root)):
            if file == 'optional':
                continue
            if output:
                print("-"*20)
                print(file)
            with open(os.path.join(root, file)) as f:
                test_suites = json.load(f)
            for test_suite in test_suites:
                self.run_suite(test_suite, output, stats)
        print(f"Num Skipped:    {stats.num_skipped}")
        print(f"Num Failed:     {stats.num_failed}")
        print(f"Num Succeeded:  {stats.num_succeeded}")

    def run_suite(self, suite: dict, output: bool, stats: Stats):

        if output:
            print(suite['description'])

        schema_orig = suite['schema']
        if self.skip(schema_orig):
            stats.num_skipped += 1
            return

        # Normalize
        if output:
            print("Orig:")
            print(yaml.safe_dump(schema_orig, indent=4))
        try:
            schema_norm = normalize(schema_orig)
        except JsonPointerException:
            # Currently does not support remote pointers
            stats.num_skipped += 1
            return

        # Check if normalized
        if output:
            print("Norm:")
            print(yaml.safe_dump(schema_norm, indent=4))
        try:
            check_normalized(schema_norm)
        except JsonPointerException:
            stats.num_skipped += 1
            return

        # Check if schemas are equal
        validator_orig = validators.validator_for(schema_orig)(
            schema_orig, resolver=RaisingResolver())
        validator_norm = validators.validator_for(schema_norm)(
            schema_norm, resolver=RaisingResolver())
        validator_norm = validators.extend(validator_norm, {
            'NOT_const': invert(validator_norm.VALIDATORS["const"]),
            'NOT_enum': invert(validator_norm.VALIDATORS["enum"]),
            'NOT_multipleOf': invert(validator_norm.VALIDATORS["multipleOf"]),
            'type': validated_type,
        })

        for test_case in suite['tests']:
            data = test_case['data']
            valid_by_def = test_case['valid']
            try:
                validator_orig.validate(data)
                valid_by_orig = True
            except (exceptions.ValidationError, exceptions.SchemaError):
                valid_by_orig = False
            except RasingResolverException:
                # Ignore this sample, try next one
                continue
            try:
                validate(data, schema_norm, resolver=RaisingResolver())
                valid_by_norm = True
            except (exceptions.ValidationError, exceptions.SchemaError) as e:
                valid_by_norm = False
            except RasingResolverException:
                # Ignore this sample, try next one
                continue
            if output:
                print("Is valid" if valid_by_orig else "invalid")
                print(yaml.safe_dump(test_case['data'], indent=4))

            if valid_by_norm != valid_by_def:
                if valid_by_orig != valid_by_def:
                    # print("jsonschema bug!!!")
                    stats.num_skipped += 1
                    continue
                stats.num_failed += 1

        # success!
        stats.num_succeeded += 1

    def DISABLED_test_aas(self):
        path = os.path.join(
            script_dir, '../../examples/asset_administration_shell/aas.yaml')
        with open(path) as f:
            schema = yaml.safe_load(f)
        print(f"NUM KEYS: {count_keys(schema)}")
        counts = {}
        key_counts(schema, counts)
        counts = sorted([(value, key) for key, value in counts.items()])
        for count, key in counts:
            print(f"{count}: {key}")
        print(f"ALL KEYS: {counts}")
        schema = normalize(schema, False)
        yaml.Dumper.ignore_aliases = lambda *args: True
        with open(path + ".yml", "w") as f:
            yaml.dump(schema, f)
        check_normalized(schema)


def count_keys(schema: any) -> int:
    num_keys = 0
    if isinstance(schema, dict):
        for value in schema.values():
            num_keys += 1
            num_keys += count_keys(value)
    elif isinstance(schema, list):
        for value in schema:
            num_keys += count_keys(value)
    return num_keys


def key_counts(schema: any, counts: dict):
    if isinstance(schema, dict):
        for key, value in schema.items():
            if key in counts:
                counts[key] += 1
            else:
                counts[key] = 1
            key_counts(value, counts)
    elif isinstance(schema, list):
        for value in schema:
            key_counts(value, counts)
