#! /usr/bin/env python3

from basyx.aas.adapter.json.json_deserialization import read_aas_json_file
from fences import parse_json_schema

import os
import yaml
import json

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

def main():
    with open(os.path.join(SCRIPT_DIR, 'aas.yaml')) as file:
        schema = yaml.safe_load(file)
    graph = parse_json_schema(schema)
    valid_accepted = 0
    valid_rejected = 0
    invalid_accepted = 0
    invalid_rejected = 0
    for i in graph.generate_paths():
        sample = graph.execute(i.path)
        json.dump(sample, open("tmp.json", "w"))
        try:
            read_aas_json_file(open("tmp.json"), failsafe=False)
            if i.is_valid:
                valid_accepted += 1
            else:
                invalid_accepted += 1
        except:
            if i.is_valid:
                valid_rejected += 1
            else:
                invalid_rejected += 1

    print(f"         | Accepted   | Rejected")
    print(f"--------------------------------------")
    print(f"Valid    | {valid_accepted:10} | {valid_rejected:10}")
    print(f"Invalid  | {invalid_accepted:10} | {invalid_rejected:10}")

if __name__ == "__main__":
    main()
