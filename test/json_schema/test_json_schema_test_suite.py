import os
import yaml
import json

from unittest import TestCase
from jsonschema import validate, exceptions, validators
from fences.json_schema.normlaize import normalize, check_normalized
from fences.core.exception import JsonPointerException, NormalizationException
from fences import parse_json_schema


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


class JsonSchemaTestSuite(TestCase):

    def test_json_schema_test_suite(self):
        script_dir = os.path.dirname(os.path.realpath(__file__))
        root = os.path.join(
            script_dir, '../fixtures/JSON-Schema-Test-Suite/tests/draft2020-12')
        num_skipped = 0
        num_total = 0
        output = False
        for file in sorted(os.listdir(root)):
            if file in [
                'optional',
                'unevaluatedItems.json',
                'unevaluatedProperties.json',
                'multipleOf.json',
                'dynamicRef.json',
            ]:
                num_skipped += 1
                continue
            if output:
                print("-"*20)
                print(file)
            with open(os.path.join(root, file)) as f:
                test_suites = json.load(f)
            for test_suite in test_suites:
                if output:
                    print(test_suite['description'])
                schema_orig = test_suite['schema']
                if output:
                    print("Orig:")
                    print(yaml.safe_dump(schema_orig, indent=4))
                try:
                    schema_norm = normalize(schema_orig)
                except JsonPointerException:
                    # Currently does not support remote pointers
                    num_skipped += 1
                    continue
                if output:
                    print("Norm:")
                    print(yaml.safe_dump(schema_norm, indent=4))
                try:
                    check_normalized(schema_norm)
                except JsonPointerException:
                    num_skipped += 1
                    continue
                for test_case in test_suite['tests']:
                    try:
                        validate(test_case['data'], schema_orig,
                                 resolver=RaisingResolver())
                        valid_by_orig = True
                    except exceptions.ValidationError:
                        valid_by_orig = False
                    except RasingResolverException:
                        num_skipped += 1
                        continue
                    try:
                        validate(test_case['data'], schema_norm,
                                 resolver=RaisingResolver())
                        valid_by_norm = True
                    except exceptions.ValidationError:
                        valid_by_norm = False
                    except RasingResolverException:
                        num_skipped += 1
                        continue
                    if output:
                        print("valid" if valid_by_orig else "invalid")
                        print(yaml.safe_dump(test_case['data'], indent=4))
                    self.assertEqual(valid_by_orig, valid_by_norm)
                    # self.assertEqual(valid_by_orig, test_case['valid'])
                    num_total += 1
        print(f"Num Skipped: {num_skipped}")
        print(f"Num Total:   {num_total}")

    def DISABLED_test_aas(self):
        path = os.path.join(
            script_dir, '../../examples/asset_administration_shell/aas.yaml')
        with open(path) as f:
            schema = yaml.safe_load(f)
        schema = normalize(schema)
        check_normalized(schema)
        yaml.Dumper.ignore_aliases = lambda *args: True
        with open(path + ".yml", "w") as f:
            yaml.dump(schema, f)
