import os
import yaml
import json

from unittest import TestCase
from jsonschema import validate, exceptions, validators, _utils
from fences.json_schema.normalize import normalize, check_normalized
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


def invert(orig_validator):
    """
    Returns a validator with inverted semantic
    """
    def impl(validator, local_schema, instance, schema):
        try:
            orig_validator(validator, local_schema, instance, schema)
        except exceptions.ValidationError:
            return
        yield exceptions.ValidationError(f"Should be rejected")
    return impl


def validate_type(validator, types, instance, schema):
    """
    A type validator which is able to handle empty type list
    For the original types validator, the following schema accepts everything
      {"type": []}
    This validator, *rejects* everything
    """
    if not isinstance(types, list):
        types = [types]
    if not types:
        yield exceptions.ValidationError(f"{instance!r} is always invalid")
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
        validator_orig = validators.Draft202012Validator(
            schema_orig, resolver=RaisingResolver())
        base = validators.Draft202012Validator
        validator_norm = validators.extend(base, {
            'NOT_const': invert(base.VALIDATORS["const"]),
            'NOT_enum': invert(base.VALIDATORS["enum"]),
            'NOT_multipleOf': invert(base.VALIDATORS["multipleOf"]),
            'type': validate_type,
        })(schema_norm, resolver=RaisingResolver())

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
                validator_norm.validate(data)
                valid_by_norm = True
            except (exceptions.ValidationError, exceptions.SchemaError) as e:
                valid_by_norm = False
            except RasingResolverException:
                # Ignore this sample, try next one
                continue
            if output:
                print("Is valid" if valid_by_orig else "is invalid")
                print(yaml.safe_dump(test_case['data'], indent=4))

            if valid_by_norm != valid_by_def:
                if valid_by_orig != valid_by_def:
                    # print("jsonschema bug!!!")
                    stats.num_skipped += 1
                    continue
                stats.num_failed += 1

        # success!
        stats.num_succeeded += 1
