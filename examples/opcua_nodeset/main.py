#! /usr/bin/env python3

from fences import parse_xml_schema
from asyncua import Server
from xml.etree import ElementTree

import asyncio
import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

async def main():
    with open(os.path.join(SCRIPT_DIR, 'UANodeSet.xsd')) as file:
        schema = file.read()
    et = ElementTree.fromstring(schema)
    graph = parse_xml_schema(et)
    valid_accepted = 0
    valid_rejected = 0
    invalid_accepted = 0
    invalid_rejected = 0
    for i in graph.generate_paths():
        server = Server()
        await server.init()
        sample = graph.execute(i.path)
        sample = ElementTree.tostring(sample.getroot())
        try:
            await server.import_xml(xmlstring=sample)
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
    asyncio.run(main())
