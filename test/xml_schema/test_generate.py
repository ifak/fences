from unittest import TestCase
from xmlschema import XMLSchema, XMLSchemaException
from xml.etree import ElementTree
from fences import parse_xml_schema
from fences.core.debug import check_consistency
from fences.core.render import render

from xml.dom import minidom
import os

SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))


class GenerateTest(TestCase):

    def dump(self, e: ElementTree.ElementTree):
        s = ElementTree.tostring(e.getroot(), )
        print(minidom.parseString(s).toprettyxml(indent="   "))

    def check(self, schema, debug=False, wrap=True):
        if wrap:
            schema = "".join([
                '<?xml version="1.0"?>',
                '<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">',
                schema,
                '</xs:schema>'
            ])
        et = ElementTree.fromstring(schema)
        graph = parse_xml_schema(et)
        check_consistency(graph)
        for i in graph.items():
            i.description()
        if debug:
            render(graph).write_svg('graph.svg')
        validator = XMLSchema(schema)
        for i in graph.generate_paths():
            sample: ElementTree.ElementTree = graph.execute(i.path)
            if debug:
                print("Valid:") if i.is_valid else print("Invalid:")
                self.dump(sample)
            sample = ElementTree.fromstring(
                ElementTree.tostring(sample.getroot()))
            if i.is_valid:
                validator.validate(sample)
            else:
                with self.assertRaises(XMLSchemaException):
                    validator.validate(sample)

    def test_simple(self):
        schema = """
            <xs:element name="note">
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name="to" type="xs:string"/>
                        <xs:element name="from" type="xs:string"/>
                        <xs:element name="heading" type="xs:string"/>
                        <xs:element name="body" type="xs:string"/>
                    </xs:sequence>
                </xs:complexType>
            </xs:element>
            """
        self.check(schema)

    def test_repeat(self):
        schema = """
            <xs:element name = 'class'>
                <xs:complexType>
                    <xs:sequence>
                        <xs:element name = 'student' type = 'StudentType' minOccurs = '0' 
                        maxOccurs = 'unbounded' />
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
            """
        self.check(schema)

    def test_enumeration(self):
        schema = """
            <xs:element name="car">
                <xs:simpleType>
                    <xs:restriction base="xs:string">
                        <xs:enumeration value="Audi"/>
                        <xs:enumeration value="Golf"/>
                        <xs:enumeration value="BMW"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:element>
            """
        self.check(schema)

    def test_string_restriction(self):
        schema = """
            <xs:element name="car">
                <xs:simpleType>
                    <xs:restriction base="xs:string">
                        <xs:minLength value="5"/>
                        <xs:maxLength value="8"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:element>
            """
        self.check(schema)

    def test_simple_content(self):
        schema = """
            <xs:element name="shoesize">
                <xs:complexType>
                    <xs:simpleContent>
                        <xs:extension base="xs:integer">
                            <xs:attribute name="country" type="xs:string" />
                        </xs:extension>
                    </xs:simpleContent>
                </xs:complexType>
            </xs:element>
            """
        self.check(schema)

    def test_all(self):
        schema = """
            <xs:element name="person">
                <xs:complexType>
                    <xs:all>
                        <xs:element name="firstname" type="xs:string"/>
                        <xs:element name="lastname" type="xs:string"/>
                    </xs:all>
                </xs:complexType>
            </xs:element>
            """
        self.check(schema)

    def test_attribute(self):
        schema = """
            <xs:element name="someComplexType">
                <xs:simpleType>
                    <xs:restriction base="xs:string">
                        <xs:minLength value="10"/>
                    </xs:restriction>
                </xs:simpleType>
            </xs:element>
            """
        self.check(schema)

    def test_extension_simple(self):
        schema = """
            <xs:simpleType name="size">
                <xs:restriction base="xs:string">
                    <xs:enumeration value="small" />
                    <xs:enumeration value="medium" />
                    <xs:enumeration value="large" />
                </xs:restriction>
            </xs:simpleType>

            <xs:element name="test">
                <xs:complexType>
                    <xs:simpleContent>
                        <xs:extension base="size">
                        <xs:attribute name="sex">
                            <xs:simpleType>
                            <xs:restriction base="xs:string">
                                <xs:enumeration value="male" />
                                <xs:enumeration value="female" />
                            </xs:restriction>
                            </xs:simpleType>
                        </xs:attribute>
                        </xs:extension>
                    </xs:simpleContent>
                </xs:complexType>
            </xs:element>
        """
        self.check(schema)

    def test_extension_complex(self):
        schema = """
            <xs:element name="employee" type="fullpersoninfo"/>
            <xs:complexType name="personinfo">
                <xs:sequence>
                    <xs:element name="firstname" type="xs:string"/>
                    <xs:element name="lastname" type="xs:string"/>
                </xs:sequence>
            </xs:complexType>

            <xs:complexType name="fullpersoninfo">
                <xs:complexContent>
                    <xs:extension base="personinfo">
                        <xs:sequence>
                            <xs:element name="address" type="xs:string"/>
                            <xs:element name="city" type="xs:string"/>
                            <xs:element name="country" type="xs:string"/>
                        </xs:sequence>
                    </xs:extension>
                </xs:complexContent>
            </xs:complexType>
            """
        self.check(schema)

    def test_fixed_value(self):
        schema = """
            <xs:element name="test">
                <xs:complexType>
                    <xs:attribute name="foo" type="xs:string" fixed="bar"/>
                </xs:complexType>
            </xs:element>"""
        self.check(schema)

    def test_opcua(self):
        with open(os.path.join(SCRIPT_DIR, '..', '..', 'examples', 'opcua_nodeset', 'UANodeSet.xsd')) as file:
            schema = file.read()
        self.check(schema, wrap=False)
