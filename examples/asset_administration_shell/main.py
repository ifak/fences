#! /usr/bin/env python3

from fences import parse_json_schema
from fences.json_schema.normalize import normalize
from fences.core.util import ConfusionMatrix

import os
import yaml
import json
import shutil

from aas_core3 import jsonization


SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, 'test-data')
TEST_DATA_DIR_VALID = os.path.join(TEST_DATA_DIR, 'valid')
TEST_DATA_DIR_INVALID = os.path.join(TEST_DATA_DIR, 'invalid')
def main():
    regenerate = True
    if regenerate:
        # Remove old data if any
        if os.path.exists(TEST_DATA_DIR):
            shutil.rmtree(TEST_DATA_DIR)
        os.mkdir(TEST_DATA_DIR)
        os.mkdir(TEST_DATA_DIR_VALID)
        os.mkdir(TEST_DATA_DIR_INVALID)

        # Generate test data
        with open(os.path.join(SCRIPT_DIR, 'aas.yaml')) as file:
            schema = yaml.safe_load(file)
        print("Normalize...")
        schema = normalize(schema, False)
        with open(os.path.join(SCRIPT_DIR, 'aas_norm.yaml'), "w") as file:
            yaml.safe_dump(schema, file)
        graph = parse_json_schema(schema)
        confusion_mat = ConfusionMatrix()
        valid_files = 0
        invalid_files = 0
        print("Generate...")
        for idx, i in enumerate(graph.generate_paths()):
            sample = graph.execute(i.path)
            if i.is_valid:
                path = os.path.join(TEST_DATA_DIR, "valid", f"{idx}.json")
                valid_files += 1
            else:
                path = os.path.join(TEST_DATA_DIR, "invalid", f"{idx}.json")
                invalid_files += 1
            json.dump(sample, open(path, "w"), indent=2)

    print("Evaluate...")

    # Collect results
    for file in os.listdir(TEST_DATA_DIR_VALID):
        path = os.path.join(TEST_DATA_DIR_VALID, file)
        print(path)
        with open(path, "r") as f:
            jsonable = json.load(f)
        try:
            environment = jsonization.environment_from_jsonable(jsonable)
            confusion_mat.valid_accepted += 1
        except jsonization.DeserializationException as e:
            confusion_mat.valid_rejected += 1
            print(e)

    for file in os.listdir(TEST_DATA_DIR_INVALID):
        path = os.path.join(TEST_DATA_DIR_INVALID, file)
        with open(path, "r") as f:
            jsonable = json.load(f)
        try:
            environment = jsonization.environment_from_jsonable(jsonable)
            confusion_mat.invalid_accepted += 1
        except jsonization.DeserializationException as e:
            confusion_mat.invalid_rejected += 1
            # raise e
    confusion_mat.print()

    # assert confusion_mat.valid_accepted + confusion_mat.valid_rejected == valid_files
    # assert confusion_mat.invalid_accepted + confusion_mat.invalid_rejected == invalid_files
    print("...done.")
if __name__ == "__main__":
    main()
