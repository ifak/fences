#! /usr/bin/env python3

from fences import parse_json_schema
from fences.core.util import ConfusionMatrix

import os
import yaml
import json
import shutil

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
AAS4J_JAR = os.path.join(SCRIPT_DIR, 'aas4j', 'target', 'aastest-1.0-SNAPSHOT.jar')
TEST_DATA_DIR = os.path.join(SCRIPT_DIR, 'test-data')

def main():
    # Remove old data if any
    if os.path.exists(TEST_DATA_DIR):
        shutil.rmtree(TEST_DATA_DIR)
    os.mkdir(TEST_DATA_DIR)
    os.mkdir(TEST_DATA_DIR + '/valid')
    os.mkdir(TEST_DATA_DIR + '/invalid')

    # Build AAS4J if not available
    if not os.path.exists(AAS4J_JAR):
        os.system(f"cd {SCRIPT_DIR}/aas4j && docker-compose run app mvn package")

    # Generate test data
    with open(os.path.join(SCRIPT_DIR, 'aas.yaml')) as path:
        schema = yaml.safe_load(path)
    graph = parse_json_schema(schema)
    confusion_mat = ConfusionMatrix()
    valid_files = 0
    invalid_files = 0
    for idx, i in enumerate(graph.generate_paths()):
        sample = graph.execute(i.path)
        if i.is_valid:
            path = os.path.join(TEST_DATA_DIR, "valid", f"{idx}.json")
            valid_files += 1
        else:
            path = os.path.join(TEST_DATA_DIR, "invalid", f"{idx}.json")
            invalid_files += 1
        json.dump(sample, open(path, "w"), indent=4)

    # Execute SUT
    os.system(f"java -jar '{AAS4J_JAR}' '{TEST_DATA_DIR}'")

    # Collect results
    with open(os.path.join(TEST_DATA_DIR, "results.json")) as file:
        results = json.load(file)['results']
    for path, result in results.items():
        if '/invalid' in path:
            if result['error_code'] == 0:
                confusion_mat.invalid_accepted += 1
            else:
                confusion_mat.invalid_rejected += 1
        if '/valid' in path:
            if result['error_code'] == 0:
                confusion_mat.valid_accepted += 1
            else:
                confusion_mat.valid_rejected +=1

    confusion_mat.print()

    assert confusion_mat.valid_accepted + confusion_mat.valid_rejected == valid_files
    assert confusion_mat.invalid_accepted + confusion_mat.invalid_rejected == invalid_files

if __name__ == "__main__":
    main()
