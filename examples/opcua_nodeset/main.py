#! /usr/bin/env python3

from fences import parse_xml_schema
from fences.core.node import Leaf
from fences.core.render import render

from asyncua import Server

import asyncio
import os
import traceback
import sys

from xml.etree import ElementTree
from xml.dom import minidom

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


def dump(e: ElementTree.ElementTree):
    s = ElementTree.tostring(e.getroot(), )
    print(minidom.parseString(s).toprettyxml(indent="   "))


def addParentNode(element: ElementTree.Element):
    dummy = ElementTree.Element('UAObject')
    dummy.set('NodeId', "ns=1;i=1")
    dummy.set('BrowseName', "parent_node")
    refs = ElementTree.Element('References')
    dummy.append(refs)
    ref = ElementTree.Element('Reference')
    ref.set('ReferenceType', 'Organizes')
    ref.set('IsForward', 'false')
    ref.text = 'i=85'
    refs.append(ref)
    element.insert(0, dummy)


last_idx = 1


def make_nodeid(element, path):
    global last_idx
    if element.get('name', '') == 'ParentNodeId':
        yield "ns=1;i=1"
    else:
        last_idx += 1
        yield f"ns=1;i={last_idx}"


async def main():

    # with open('/home/bot/Projects/Promotion/fences/sample_nodeset.xml') as file:
    #     schema = file.read()
    # et = ElementTree.fromstring(schema)
    # server = Server()
    # sample = ElementTree.tostring(et)
    # await server.init()
    # await server.import_xml(xmlstring=sample)
    # return

    with open(os.path.join(SCRIPT_DIR, 'UANodeSet.xsd')) as file:
        schema = file.read()
    et = ElementTree.fromstring(schema)
    graph = parse_xml_schema(et, config={
        'type_generators': {
            'NodeId': {
                'valid': make_nodeid
            },
        }
    })
    # schema_root = graph.get_by_id('/schema[0]/element[0]')
    # schema_root.add_transition(InsertDummyNode())
    render(graph).write_svg('graph.svg')
    valid_accepted = 0
    valid_rejected = 0
    invalid_accepted = 0
    invalid_rejected = 0
    for idx, i in enumerate(graph.generate_paths()):
        print("############# {}".format(idx))
        server = Server()
        await server.init()
        s = graph.execute(i.path)
        addParentNode(s.getroot())
        sample = ElementTree.tostring(s.getroot())
        try:
            await server.import_xml(xmlstring=sample)
            if i.is_valid:
                dump(s)
                print("Valid and accepted")
                valid_accepted += 1
            else:
                print("!!! Invalid BUT accepted!")
                invalid_accepted += 1
        except Exception as e:
            if i.is_valid:
                dump(s)
                print(traceback.format_exc())
                print("!!! valid BUT rejected!")
                valid_rejected += 1
            else:
                print("Invalid and rejected")
                invalid_rejected += 1

    print(f"         | Accepted   | Rejected")
    print(f"--------------------------------------")
    print(f"Valid    | {valid_accepted:10} | {valid_rejected:10}")
    print(f"Invalid  | {invalid_accepted:10} | {invalid_rejected:10}")

if __name__ == "__main__":
    asyncio.run(main())
