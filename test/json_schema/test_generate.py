from fences.json_schema import parse
from fences.core.debug import check_consistency
from jsonschema import validate, ValidationError
import unittest
import yaml
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class TestGenerate(unittest.TestCase):

    def check(self, schema, debug=False):
        graph = parse.parse(schema)
        check_consistency(graph)
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if debug:
                print("Valid" if i.is_valid else "Invalid")
                print(json.dumps(sample, indent=4))
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

    def test_not_1(self):
        schema = {
            "not": {
                "properties": {
                    "b": {
                        "properties": {
                            "bb": {"not": {"type": "string"}}
                        }
                    }
                }
            }
        }
        self.check(schema)

    def test_not_2(self):
        schema = {
            "not": {
                "properties": {
                    "a": {
                        "type": "string"
                    },
                    "b": {
                        "properties": {
                            "bb": {"type": "string"}
                        }
                    }
                }
            }
        }

        graph = parse.parse(schema)
        for i in graph.generate_paths():
            graph.execute(i.path)
        # TODO: currently fails
        # self.check(schema)

    def test_const(self):
        schema = {
            "properties": {
                "country": {
                    "const": "United States of America"
                }
            }
        }
        self.check(schema)

    def test_all_of_objects(self):
        schema = {
            "allOf": [
                { "$ref": "#/definitions/test" },
                { "$ref": "#/definitions/test2" },
            ],
            "definitions": {
                "test": {
                    "properties": {
                        "abc": { "type": "string" }
                    },
                    "required": [ "abc" ]
                },
                "test2": {
                    "properties": {
                        "xyz": { "type": "string" }
                    },
                    "required": ['xyz']
                }
            }
        }
        self.check(schema)

    def test_all_of_arrays(self):
        schema = {
            "type": "array",
            "items": 
            {
                "allOf": [
                    { "$ref": "#/definitions/test" },
                    { "$ref": "#/definitions/test2" },
                ]
            },
            "definitions": {
                "test": {
                    "properties": {
                        "abc": { "type": "string" }
                    },
                    "required": [ "abc" ]
                },
                "test2": {
                    "properties": {
                        "xyz": { "type": "string" }
                    },
                    "required": ['xyz']
                }
            }
        }
        self.check(schema)

    def test_if(self):
        schema = {
            "if": {
                "properties": {
                    "a": { "const": "x" }
                }
            },
            "then": {
                "properties": {
                    "b": { "const": "y" }
                }
            },
            "else": {
                "properties": {
                    "c": { "const": "z" }
                }
            }
        }
        # self.check(schema)

    def test_aas(self):
        with open(os.path.join(SCRIPT_DIR, '..', '..', 'examples', 'asset_administration_shell', 'aas.yaml')) as file:
            schema = yaml.safe_load(file)
        # TODO: fails because jsonschema crashes
        # self.check(schema)
