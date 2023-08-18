from fences.json_schema import parse
from fences.core.debug import check_consistency
from jsonschema import Draft202012Validator, ValidationError
import unittest
import yaml
import os
import json
from fences.core.render import render
from fences.json_schema.normalize import normalize

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class TestGenerate(unittest.TestCase):

    def check(self, schema, debug=False, strict_invalid=True):
        if debug:
            print("Input schema:")
            yaml.SafeDumper.ignore_aliases = lambda *args: True
            print(yaml.safe_dump(schema))
        validator = Draft202012Validator(schema)
        schema = normalize(schema)
        if debug:
            print("Normalized schema:")
            print(yaml.safe_dump(schema))
        graph = parse.parse(schema)
        if debug:
            render(graph).write_svg('graph.svg')
        check_consistency(graph)
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if debug:
                print("Valid" if i.is_valid else "Invalid")
                print(json.dumps(sample, indent=4))
            if i.is_valid:
                validator.validate(sample)
            else:
                if strict_invalid:
                    with self.assertRaises(ValidationError):
                        validator.validate(sample)

    def test_empty(self):
        self.check({})

    def test_simple(self):
        schema = {
            "type": "object",
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
            "$defs": {
                "mydef": {
                    "$ref": "#/$defs/foo"
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
                                                    "$ref": "#/$defs/SpecificAssetId"
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
            "$defs": {
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
        self.check(schema, strict_invalid=False)

    def test_const(self):
        schema = {
            "type": "object",
            "properties": {
                "country": {
                    "const": "United States of America"
                }
            }
        }
        self.check(schema)

    def test_boolean(self):
        schema = {'allOf': [ True, True]}
        self.check(schema)

    def test_all_of_objects(self):
        schema = {
            "allOf": [
                { "$ref": "#/$defs/test" },
                { "$ref": "#/$defs/test2" },
            ],
            "$defs": {
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
                    { "$ref": "#/$defs/test" },
                    { "$ref": "#/$defs/test2" },
                ]
            },
            "$defs": {
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

    def test_only_invalid_leafs(self):
        schema = {
            "type": "object",
            "anyOf": [{
                "properties": {
                    "a": {
                        "type": "object",
                        "properties": {
                            "b": False
                        },
                        "required": ["b"]
                    },
                },
                "required": ["a"]
            }, {
                "type": "object",
                "properties": {
                    "c": {"type": "string"}
                }
            }]
        }
        self.check(schema, strict_invalid=False)

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
                    "b": { "const": "z" }
                }
            }
        }
        self.check(schema, strict_invalid=False)

    def test_dependent_required(self):
        schema = {
            "dependentRequired": {
                "a": ["b", "c"]
            },
            "properties": {
                "a": {"type": "string"},
                "b": {"type": "boolean"},
                "c": {"type": "number"},
            }
        }
        self.check(schema, strict_invalid=False)

    def test_constraint_aasd_014(self):
        schema = {
            "properties": {
                "globalAssetId": {"type": "string"},
                "specificAssetIds": {"type": "array"},
            },
            "if": {
                "properties": {
                    "entityType": {
                        "const": "SelfManagedEntity"
                    }
                },
                "required": ["entityType"]
            },
            "then": {
                "anyOf": [
                {
                    "required": ["globalAssetId"],
                    "not": {
                        "required": ["specificAssetIds"]
                    }
                },
                {
                    "required": ["specificAssetIds"],
                    "not": {
                        "required": ["globalAssetId"]
                    }
                }
                ]
            },
            "else": {
                "not": {
                "required": ["globalAssetId", "specificAssetId"]
                }
            }
        }
        self.check(schema, strict_invalid=False)

    def test_aas(self):
        with open(os.path.join(SCRIPT_DIR, '..', 'fixtures', 'json', 'aas_small.yaml')) as file:
            schema = yaml.safe_load(file)
        schema = normalize(schema, False)
        schema['$schema'] = 'https://json-schema.org/draft/2020-12/schema'
        graph = parse.parse(schema)
        check_consistency(graph)
        num_samples = 0
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            num_samples += 1
        print(f"Generated {num_samples} samples")
