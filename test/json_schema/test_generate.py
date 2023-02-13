from fences.json_schema import parse
from jsonschema import validate, ValidationError
import unittest
import yaml
import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class TestGenerate(unittest.TestCase):

    def check(self, schema):
        graph = parse.parse(schema)
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if i.is_valid:
                validate(instance=sample, schema=schema)
            else:
                with self.assertRaises(ValidationError):
                    validate(instance=sample, schema=schema)

    def test_simple(self):
        schema = {
            "properties": {
                "x": {
                    "type": "string"
                }
            }
        }
        self.check(schema)

    def test_schema1(self):
        schema = {
            "type": "object",
            "properties": {
                "test": {
                    "properties": {
                        "first": {
                            "type": "string"
                        },
                        "second": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            }
                        }
                    }
                },
            },
            "definitions": {
                "mydef": {
                    "$ref": "#/definitions/foo"
                },
                "foo": {
                    "properties": {
                        "first": {
                            "type": "boolean"
                        },
                    }
                }
            }
        }
        self.check(schema)

    def test_schema2(self):
        schema = {
            "type": "array",
            "items": {
                "properties": {
                    "second": {
                        "$ref": "#/"
                    }
                }
            }
        }
        self.check(schema)

    def test_schema3(self):
        schema = {
            "allOf": [
                {
                    "type": "object",
                    "properties": {
                        "assetAdministrationShells": {
                            "type": "array",
                            "items": {
                                "properties": {
                                    "assetInformation": {
                                        "type": "object",
                                        "properties": {
                                            "specificAssetIds": {
                                                "type": "array",
                                                "items": {
                                                    "$ref": "#/definitions/SpecificAssetId"
                                                },
                                                "minItems": 1
                                            }
                                        }
                                    }
                                },
                                "required": [
                                    "assetInformation"
                                ]
                            },
                            "minItems": 1
                        }
                    }
                }
            ],
            "definitions": {
                "SpecificAssetId": {
                    "allOf": [
                        {
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "minLength": 1
                                },
                                "value": {
                                    "type": "string",
                                    "minLength": 1
                                }
                            },
                            "required": [
                                "name",
                                "value"
                            ]
                        }
                    ]
                }
            }
        }
        self.check(schema)

    def test_aas(self):
        with open(os.path.join(SCRIPT_DIR, 'fixtures', 'aas.yaml')) as f:
            schema = yaml.safe_load(f)
        # TODO: json schema - stack overflow
        graph = parse.parse(schema)
        for result in graph.generate_paths():
            graph.execute(result.path)
