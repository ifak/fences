# Fences
[![Tests](https://github.com/ifak/fences/actions/workflows/check.yml/badge.svg)](https://github.com/ifak/fences/actions/workflows/check.yml)

Fences is a python tool which lets you create test data based on schemas.

For this, it generates a set of *valid samples* which fullfil your schema.
Additionally, it generates a set of *invalid samples* which intentionally violate your schema.
You can then feed these samples into your software to test.
If your software is implemented correctly, it must accept all valid samples and reject all invalid ones.

Unlike other similar tools, fences generate samples systematically instead of randomly.
This way, the valid / invalid samples systematically cover all boundaries of your input schema (like placing *fences*, hence the name).

## Installation

Use pip to install Fences:

```
python -m pip install fences
```

Fences is a self contained library without any external dependencies.
It uses [Lark](https://github.com/lark-parser/lark) for regex parsing, but in the standalone version where a python file is generated from the grammar beforehand (Mozilla Public License, v. 2.0).

## Usage

Generate samples for regular expressions:

```python
from fences import parse_regex

graph = parse_regex("a+(c+)b{3,7}")

for i in graph.generate_paths():
    sample = graph.execute(i.path)
    print("Valid:" if i.is_valid else "Invalid:")
    print(sample)
```

Generate samples for json schema:

```python
from fences import parse_json_schema
import json

graph = parse_json_schema({
    'properties': {
        'foo': {
            'type': 'string'
        },
        'bar': {
            'type': 'boolean'
        }
    }
})

for i in graph.generate_paths():
    sample = graph.execute(i.path)
    print("Valid:" if i.is_valid else "Invalid:")
    print(json.dumps(sample, indent=4))
```

Generate samples for XML schema:

```python
from fences import parse_xml_schema
from xml.etree import ElementTree
from xml.dom import minidom

et = ElementTree.fromstring("""<?xml version="1.0" encoding="UTF-8" ?>
    <xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
        <xs:element name = 'class'>
            <xs:complexType>
                <xs:sequence>
                    <xs:element name = 'student' type = 'StudentType' minOccurs = '0' maxOccurs = 'unbounded' />
                </xs:sequence>
            </xs:complexType>
        </xs:element>
        <xs:complexType name = "StudentType">
            <xs:sequence>
                <xs:element name = "firstname" type = "xs:string"/>
                <xs:element name = "lastname" type = "xs:string"/>
                <xs:element name = "nickname" type = "xs:string"/>
                <xs:element name = "marks" type = "xs:positiveInteger"/>
            </xs:sequence>
            <xs:attribute name = 'rollno' type = 'xs:positiveInteger'/>
        </xs:complexType>
    </xs:schema>""")

graph = parse_xml_schema(et)
for i in graph.generate_paths():
    sample = graph.execute(i.path)
    s = ElementTree.tostring(sample.getroot())
    print("Valid:" if i.is_valid else "Invalid:")
    print(minidom.parseString(s).toprettyxml(indent="   "))
```

## Real-World Examples

Find some real-world examples in the `examples` folder.

## Limitations

General:

Fences does not check if your schema is syntactically correct.
Fences is designed to be as permissive as possible when parsing a schema but will complain if there is an aspect it does not understand.

For XML:

Python's default XML implementation `xml.etree.ElementTree` has a very poor support for namespaces (https://docs.python.org/3/library/xml.etree.elementtree.html#parsing-xml-with-namespaces).
This might lead to problems when using the `targetNamespace` attribute in your XML schema.