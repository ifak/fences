#! /usr/bin/env python3

from fences import parse_json_schema
from fences.json_schema.parse import default_config
from fences.json_schema.normalize import normalize
from fences.core.util import ConfusionMatrix
import json_schema_tool

import os
import yaml
import json
import shutil
import time

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, 'test-data')
TEST_DATA_DIR_VALID = os.path.join(TEST_DATA_DIR, 'valid')
TEST_DATA_DIR_INVALID = os.path.join(TEST_DATA_DIR, 'invalid')
def main():
    # Setting these to true will interfere with the time measurement
    save_to_file = False
    validate = False
    if save_to_file:
        # Remove old data if any
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
        os.mkdir(TEST_DATA_DIR)
        os.mkdir(TEST_DATA_DIR_VALID)
        os.mkdir(TEST_DATA_DIR_INVALID)

    # Generate test data
    with open(os.path.join(SCRIPT_DIR, 'aas.yml')) as file:
        schema = yaml.safe_load(file)
    jst_conf = json_schema_tool.schema.ParseConfig()
    jst_conf.raise_on_unknown_format = False
    validator = json_schema_tool.parse_schema(schema, jst_conf)
    start = time.perf_counter()

    print("Normalize...")
    schema = normalize(schema, False)
    with open(os.path.join(SCRIPT_DIR, 'aas_norm.yml'), 'w') as file:
        yaml.safe_dump(schema, file)

    print("Generate...")
    config = default_config()
    config.normalize = False
    graph = parse_json_schema(schema, config)

    mat = ConfusionMatrix()
    for idx, i in enumerate(graph.generate_paths()):
        sample = graph.execute(i.path)
        if validate:
            ok = validator.validate(sample).ok
        else:
            ok = True
        if i.is_valid:
            path = os.path.join(TEST_DATA_DIR, "valid", f"{idx}.json")
            if ok:
                mat.valid_accepted += 1
            else:
                mat.valid_rejected += 1
        else:
            path = os.path.join(TEST_DATA_DIR, "invalid", f"{idx}.json")
            if ok:
                mat.invalid_accepted += 1
            else:
                mat.invalid_rejected += 1

        if save_to_file:
            json.dump(sample, open(path, "w"), indent=2)

    elapsed = int(time.perf_counter() - start)
    print(f"Took {elapsed} seconds")
    mat.print()

if __name__ == "__main__":
    main()
