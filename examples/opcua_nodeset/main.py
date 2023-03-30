#! /usr/bin/env python3

from fences import parse_xml_schema
from fences.core.util import ConfusionMatrix

from asyncua import Server

import asyncio
import os
import traceback

from xml.etree import ElementTree
from xml.dom import minidom

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def dump(e: ElementTree.ElementTree):
    s = ElementTree.tostring(e.getroot(), )
    print(minidom.parseString(s).toprettyxml(indent="   "))


def get_tag(el: ElementTree.Element) -> str:
    _, _, tag_wo_namespace = el.tag.rpartition('}')
    return tag_wo_namespace


def mark_as_valid_child_node(tree: ElementTree.ElementTree):

    for node in tree.getroot():
        tag = get_tag(node)
        if tag in [
            'UAObject',
            'UAVariable',
            'UAMethod',
            'UAView',
            'UAObjectType',
            'UAVariableType',
            'UADataType',
            'UAReferenceType',
        ]:
            refs = ElementTree.Element('References')
            ref = ElementTree.Element('Reference')
            ref.set('ReferenceType', 'HasComponent')
            ref.set('IsForward', 'false')
            ref.text = 'i=1'
            refs.append(ref)
            node.append(refs)


class NodeIdGenerator:

    def __init__(self) -> None:
        self.last_node_id = 1000

    def __call__(self, element, path):
        self.last_node_id += 1
        yield f"i={self.last_node_id}"


async def main():

    with open(os.path.join(SCRIPT_DIR, 'UANodeSet.xsd')) as file:
        schema = file.read()
    et = ElementTree.fromstring(schema)
    graph = parse_xml_schema(et, config={
        'type_generators': {
            'NodeId': {
                'valid': NodeIdGenerator()
            },
        }
    })
    confusion_mat = ConfusionMatrix()
    for idx, i in enumerate(graph.generate_paths()):
        print("############# {}".format(idx))

        # Generate sample
        sample = graph.execute(i.path)
        mark_as_valid_child_node(sample)
        dump(sample)

        # Create new server instance
        server = Server()
        await server.init()

        # Invoke
        try:
            await server.import_xml(xmlstring=ElementTree.tostring(sample.getroot()))
            if i.is_valid:
                print("Valid and accepted")
                confusion_mat.valid_accepted += 1
            else:
                print("!!! Invalid BUT accepted!")
                confusion_mat.invalid_accepted += 1
        except Exception as e:
            if i.is_valid:
                print(traceback.format_exc())
                print("!!! valid BUT rejected!")
                confusion_mat.valid_rejected += 1
            else:
                print("Invalid and rejected")
                confusion_mat.invalid_rejected += 1

        print()

    confusion_mat.print()

if __name__ == "__main__":
    asyncio.run(main())
