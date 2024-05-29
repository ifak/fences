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

### Regular Expressions

Generate samples for regular expressions:

```python
from fences import parse_regex

graph = parse_regex("a?(c+)b{3,7}")

for i in graph.generate_paths():
    sample = graph.execute(i.path)
    print("Valid:" if i.is_valid else "Invalid:")
    print(sample)
```

<details>
<summary>Output</summary>

```
Valid:
cbbb
Valid:
acccbbbbbbb
```
</details>

### JSON schema

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

<details>
<summary>Output</summary>

```json
Valid:
{
    "foo": "",
    "bar": true
}

Valid:
{}

Valid:
{
    "foo": "",
    "bar": false
}

Invalid:
{
    "foo": null
}

Invalid:
{
    "bar": 42
}

Invalid:
{
    "bar": null
}

Invalid:
{
    "foo": "",
    "bar": "INVALID"
}
```
</details>

### XML Schema

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

<details>
<summary>Output</summary>

```xml
Valid:
<?xml version="1.0" ?>
<class/>

Valid:
<?xml version="1.0" ?>
<class>
   <student>
      <firstname>foo</firstname>
      <lastname>foo</lastname>
      <nickname>foo</nickname>
      <marks>780</marks>
   </student>
</class>

Valid:
<?xml version="1.0" ?>
<class>
   <student rollno="533">
      <firstname>x</firstname>
      <lastname>x</lastname>
      <nickname>x</nickname>
      <marks>780</marks>
   </student>
</class>

Invalid:
<?xml version="1.0" ?>
<class>
   <student>
      <firstname>foo</firstname>
      <lastname>foo</lastname>
      <nickname>foo</nickname>
      <marks>-10</marks>
   </student>
</class>

Invalid:
<?xml version="1.0" ?>
<class>
   <student rollno="533">
      <firstname>x</firstname>
      <lastname>x</lastname>
      <nickname>x</nickname>
      <marks>foo</marks>
   </student>
</class>

Invalid:
<?xml version="1.0" ?>
<class>
   <student rollno="-10">
      <firstname>foo</firstname>
      <lastname>foo</lastname>
      <nickname>foo</nickname>
      <marks>780</marks>
   </student>
</class>

Invalid:
<?xml version="1.0" ?>
<class>
   <student rollno="foo">
      <firstname>x</firstname>
      <lastname>x</lastname>
      <nickname>x</nickname>
      <marks>780</marks>
   </student>
</class>
```

</details>

### Grammar

Generate samples for a grammar:

```python
from fences.grammar.types import NonTerminal, CharacterRange
from fences import parse_grammar

number = NonTerminal("number")
integer = NonTerminal("integer")
fraction = NonTerminal("fraction")
exponent = NonTerminal("exponent")
digit = NonTerminal("digit")
digits = NonTerminal("digits")
one_to_nine = NonTerminal("one_to_nine")
sign = NonTerminal("sign")

grammar = {
    number:      integer + fraction + exponent,
    integer:     digit
                 | one_to_nine + digits
                 | '-' + digit
                 | '-' + one_to_nine + digits,
    digit:       '0'
                 | one_to_nine,
    digits:      digit*(1, None),
    one_to_nine: CharacterRange('1', '9'),
    fraction:    ""
                 | "." + digits,
    exponent:    ""
                 | 'E' + sign + digits
                 | "e" + sign + digits,
    sign:        ["", "+", "-"]
}

graph = parse_grammar(grammar, number)
for i in graph.generate_paths():
    sample = graph.execute(i.path)
    print(sample)
```

<details>
<summary>Output</summary>

```
0
91.0901E0901
-0e+9
-10901.0
9E-0109
```

</details>

### OpenAPI (Swagger)

You can use Fences to parse an OpenAPI specification and generate a set of sample requests:

```python
from fences import parse_open_api

description = {
    'info': {
        'title': 'Video API'
    },
    'paths': {
        '/videos': {
            'get': {
                'operationId': 'listVideos',
                'parameters': [{
                    'name': 'type',
                    'in': 'query',
                    'schema': {
                        'enum': ['public', 'private']
                    }
                }, {
                    'name': 'title',
                    'in': 'query',
                    'schema': {
                        'type': 'string',
                        'minLength': 3
                    }
                }],
                'responses': {}
            }
        },
        '/videos/{videoId}': {
            'patch': {
                'operationId': 'updateVideo',
                'parameters': [
                    {
                        'name': 'videoId',
                        'in': 'path',
                        'schema': {
                            'type': 'number'
                        }
                    }
                ],
                'requestBody': {
                    'content': {
                        'application/json': {
                            'schema': {
                                'type': 'object',
                                'properties': {
                                    'title': {
                                        'type': 'string',
                                        'minLength': 10
                                    }
                                },
                                'required': ['title']
                            }
                        }
                    }
                },
                'responses': {}
            }
        }
    }
}

graph = parse_open_api(description)
for i in graph.generate_paths():
    request = graph.execute(i.path)
    request.dump()
```

<details>
<summary>Output</summary>

```
GET /videos?type=public&title=xxx
GET /videos?type=private
GET /videos?title=xxx
PATCH /videos/0
  BODY: {"title": "xxxxxxxxxx"}
GET /videos?type=%23%23%23%23%23%23%23%23
GET /videos?type=public&title=42
GET /videos?type=private&title=true
GET /videos?title=false
GET /videos?type=public&title=
GET /videos?type=private&title=
PATCH /videos/string
  BODY: {"title": "xxxxxxxxxx"}
PATCH /videos/true
  BODY: {"title": "xxxxxxxxxx"}
PATCH /videos/false
  BODY: {"title": "xxxxxxxxxx"}
PATCH /videos/
  BODY: {"title": "xxxxxxxxxx"}
PATCH /videos/
  BODY: {"title": "xxxxxxxxxx"}
PATCH /videos/0
  BODY: {"title": 42}
PATCH /videos/0
  BODY: {"title": null}
PATCH /videos/0
  BODY: {"title": true}
PATCH /videos/0
  BODY: {"title": false}
PATCH /videos/0
  BODY: {"title": {}}
PATCH /videos/0
  BODY: {"title": []}
PATCH /videos/0
PATCH /videos/0
  BODY: "string"
PATCH /videos/0
  BODY: 42
PATCH /videos/0
  BODY: true
PATCH /videos/0
```
</details>

You can execute the generated tests using the `request.execute()` method.
Please note, that you need to install the `requests` library for this.

```python
import requests

...

graph = parse_open_api(description)
for i in graph.generate_paths():
    request = graph.execute(i.path)
    request.dump()
    request.execute('http://localhost:8080')
```

</details>


## Real-World Examples

Find some real-world examples in the `examples` folder.

## Limitations

General:

Fences does not check if your schema is syntactically correct.
Fences is designed to be as permissive as possible when parsing a schema but will complain if there is an aspect it does not understand.

For XML:

Python's default XML implementation `xml.etree.ElementTree` has a very poor support for namespaces (https://docs.python.org/3/library/xml.etree.elementtree.html#parsing-xml-with-namespaces).
This might lead to problems when using the `targetNamespace` attribute in your XML schema.

For Grammars:

Fences currently does not generate invalid samples for grammars.

For OpenAPI:

The test cases generated by Fences are purely syntactic. They do not check for semantics, e.g. if retrieving a deleted resource returns 404.
 