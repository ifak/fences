from .exception import XmlSchemaException
from .config import Config, TypeHandler

from fences.core.node import Leaf, Decision, NoOpLeaf, NoOpDecision, Node, Reference
from fences.core.random import generate_random_number, generate_random_string, StringProperties

from xml.etree import ElementTree
from typing import Set, List, Optional, Dict


def default_config() -> Config:
    return Config(
        tag_handlers={
            'all': parse_sequence,  # TODO: special handling
            'element': parse_element,
            'sequence': parse_sequence,
            'choice': parse_choice,
            'simpleType': parse_type,
            'complexType': parse_type,
            'simpleContent': parse_content,
            'complexContent': parse_content,
            'attribute': parse_attribute,
            'annotation': parse_annotation,
            'extension': parse_extension,
            'restriction': parse_restriction,
            'any': parse_any,
        },
        buildin_types={
            'xs:string': TypeHandler(
                valid=lambda _: [
                    'foo', generate_random_string(StringProperties(1))],
                invalid=lambda _: []
            ),
            'xs:dateTime': TypeHandler(
                valid=lambda _: ['2001-10-26T21:32:52'],
                invalid=lambda _: ["foo"]
            ),
            'xs:positiveInteger': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["-10", "foo"]
            ),
            'xs:integer': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["xyz"]
            ),
            'xs:boolean': TypeHandler(
                valid=lambda _: ["true", "false", "0", "1"],
                invalid=lambda _: ["foo"]
            ),
            'xs:unsignedInt': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["-10", "bar"]
            ),
            'xs:unsignedShort': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["-10", "bar"]
            ),
            'xs:unsignedByte': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["-10", "bar"]
            ),
            'xs:int': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["bar"]
            ),
            'xs:double': TypeHandler(
                valid=lambda _: [generate_random_number(min_value=0)],
                invalid=lambda _: ["bar"]
            ),
            'xs:decimal': TypeHandler(
                valid=lambda _: [generate_random_number()],
                invalid=lambda _: ["bar"]
            ),
        },
        restriction_handlers={
            'pattern': parse_string_restriction,
            'minLength': parse_string_restriction,
            'maxLength': parse_string_restriction,
        }
    )


class Binding:
    def __init__(self, element: ElementTree.Element, attr: Optional[str]) -> None:
        self.element = element
        self.attr = attr

    def set_value(self, value: any):
        if self.attr:
            self.element.attrib[self.attr] = value
        else:
            self.element.text = value


class StartNode(Decision):

    def apply(self, data: any) -> Binding:
        return Binding(ElementTree.Element('dummy'), None)

    def description(self) -> str:
        return "Start"


class FetchOutput(Leaf):
    def __init__(self, namespace: Optional[str]) -> None:
        super().__init__(None, True)
        self.namespace = namespace

    def apply(self, data: Binding) -> ElementTree.ElementTree:
        root = next(iter(data.element))
        if self.namespace:
            root.attrib['xmlns'] = self.namespace
        return ElementTree.ElementTree(root)

    def description(self) -> str:
        return "Fetch output"


class StartAttribute(Decision):
    def __init__(self, id: str, all_transitions: bool, attr: str) -> None:
        super().__init__(id, all_transitions)
        self.attr = attr

    def apply(self, data: Binding) -> Binding:
        return Binding(data.element, self.attr)

    def description(self) -> Optional[str]:
        return f"Start attribute '{self.attr}'"


class StartNewElement(Decision):

    def __init__(self, id: str, all_transitions: bool, tag: str) -> None:
        super().__init__(id, all_transitions)
        self.tag = tag

    def apply(self, data: Binding) -> ElementTree.Element:
        element = ElementTree.Element(self.tag)
        data.element.append(element)
        return Binding(element, None)

    def description(self) -> str:
        return f"Start <{self.tag}..."


class SetValueLeaf(Leaf):
    def __init__(self, id: str, is_valid: bool, value: any) -> None:
        super().__init__(id, is_valid)
        self.value = value

    def apply(self, data: Binding) -> any:
        data.set_value(self.value)
        return data

    def description(self) -> Optional[str]:
        return f"= '{self.value}'"


def _get_tag(el: ElementTree.Element) -> str:
    _, _, tag_wo_namespace = el.tag.rpartition('}')
    return tag_wo_namespace


def _lookup(attrib: Dict[str, str], key: str, parsed_attributes: Set[str]) -> str:
    parsed_attributes.remove(key)
    return attrib[key]


def parse_enumeration_restriction(element: ElementTree.Element) -> Node:
    if any(_get_tag(child) != 'enumeration' for child in element):
        raise XmlSchemaException("Only enumeration allowed")

    root = NoOpDecision(None, False)
    for child in element:
        value = child.attrib['value']
        root.add_transition(SetValueLeaf(None, True, value))
    return root


def parse_string_restriction(base: str, props: Dict[str, str], config: Config, parsed_props: Set[str]) -> Node:
    if base not in ['xs:string', 'xs:token']:
        raise XmlSchemaException(
            f"String restrictions must be based on string class, is {base}")

    s = StringProperties()
    if 'pattern' in props:
        s.pattern = _lookup(props, 'pattern', parsed_props)
    if 'minLength' in props:
        s.min_length = int(_lookup(props, 'minLength', parsed_props))
    if 'maxLength' in props:
        s.max_length = int(_lookup(props, 'maxLength', parsed_props))

    return SetValueLeaf(None, True, generate_random_string(s))


def parse_any(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    if 'processContents' in element.attrib:
        process_contents = _lookup(
            element.attrib, 'processContents', parsed_attributes)
    # TODO: use processContents
    return NoOpLeaf(None, True)


def parse_restriction(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    base = _lookup(element.attrib, 'base', parsed_attributes)

    # Normally, we would use base to check if we really restrict the base type
    # However, Fences is not meant to be a schema checker, so we discard it here

    if len(element) == 0:
        return resolve_type(base, config)

    # Special handling for enumerations
    if _get_tag(next(iter(element))) == 'enumeration':
        return parse_enumeration_restriction(element)

    handler = None
    for child in element:
        tag = _get_tag(child)
        if tag in config.restriction_handlers:
            handler = config.restriction_handlers[tag]
            break
    if handler is None:
        child_tags = [_get_tag(i) for i in element]
        raise XmlSchemaException(
            f"No restriction handler found, child tags are {child_tags}")

    props = {}
    for child in element:
        if len(child.attrib) != 1 or 'value' not in child.attrib:
            raise XmlSchemaException(
                "Restriction children must have exactly one attribute 'value'")
        key = _get_tag(child)
        value = child.attrib['value']
        if key in props:
            raise XmlSchemaException(f"Duplicate restriction value '{key}'")
        props[key] = value

    parsed_props = set(props.keys())
    node = handler(base, props, config, parsed_props)
    if parsed_props:
        raise XmlSchemaException(
            f"Unhandled restriction properties {parsed_props}")

    # TODO: in case of contentContent/restriction we have to parse the children as well!
    return node


def parse_annotation(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    return NoOpLeaf(None, True)


def parse_content(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    root = NoOpDecision(None, True)
    for child in element:
        root.add_transition(
            parse_xml_element(child, config)
        )
    return root


def parse_extension(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    root = NoOpDecision(None, True)
    base = _lookup(element.attrib, 'base', parsed_attributes)

    root.add_transition(
        resolve_type(base, config)
    )

    for child in element:
        root.add_transition(
            parse_xml_element(child, config)
        )

    return root


def _parse_occurs(element: ElementTree.Element):
    if 'minOccurs' in element.attrib:
        s = element.attrib['minOccurs']
        try:
            min_occurs = int(s)
        except ValueError as e:
            raise XmlSchemaException(f"Invalid value for 'minOccurs': {e}")
    else:
        min_occurs = 1

    if 'maxOccurs' in element.attrib:
        s = element.attrib['maxOccurs']
        if s == 'unbounded':
            max_occurs = None
        else:
            try:
                max_occurs = int(s)
            except ValueError as e:
                raise XmlSchemaException(f"Invalid value for 'maxOccurs': {e}")
    else:
        max_occurs = 1

    return min_occurs, max_occurs


def _repeat(child: Node, min_occurs: int, max_occurs: Optional[int]) -> Node:

    root = NoOpDecision(None, False)
    root.add_transition(NoOpLeaf(None, is_valid=min_occurs == 0))

    if min_occurs > 0:
        subroot = NoOpDecision(None, True)
        for _ in range(min_occurs):
            subroot.add_transition(child)
        root.add_transition(subroot)

    if min_occurs > 1:
        subroot = NoOpDecision(None, True)
        for _ in range(min_occurs - 1):
            subroot.add_transition(child, True)
        root.add_transition(subroot, False)

    if max_occurs is not None:
        if min_occurs > max_occurs:
            raise XmlSchemaException(
                f"minOccurs = {min_occurs} > maxOccurs = {min_occurs}")

        if max_occurs != min_occurs:
            subroot = NoOpDecision(None, True)
            for _ in range(max_occurs):
                subroot.add_transition(child)
            root.add_transition(subroot)

    return root


def parse_sequence(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    if 'name' in element.attrib:
        name = _lookup(element.attrib, 'name', parsed_attributes)
    else:
        name = None
    root = NoOpDecision(None, True)
    for i in element:
        min_occurs, max_occurs = _parse_occurs(i)
        child_node = parse_xml_element(i, config)
        root.add_transition(
            _repeat(child_node, min_occurs, max_occurs)
        )
    return root


def parse_choice(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    if 'name' in element.attrib:
        name = _lookup(element.attrib, 'name', parsed_attributes)
    else:
        name = None
    root = NoOpDecision(None, False)
    for i in element:
        min_occurs, max_occurs = _parse_occurs(i)
        child_node = parse_xml_element(i, config)
        root.add_transition(
            _repeat(child_node, min_occurs, max_occurs)
        )
    return root


def parse_attribute(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    if 'ref' in element.attrib:
        raise XmlSchemaException("references currently not supported")

    name = _lookup(element.attrib, 'name', parsed_attributes)
    required = False
    if 'use' in element.attrib and _lookup(element.attrib, 'use', parsed_attributes) == "required":
        required = True

    if 'fixed' in element.attrib:
        fixed = _lookup(element.attrib, 'fixed', parsed_attributes)
    else:
        fixed = None
    if 'default' in element.attrib:
        default = _lookup(element.attrib, 'default', parsed_attributes)
    else:
        default = None
    if fixed and default:
        raise XmlSchemaException(f"Cannot set default and fixed together")
    # TODO: use default and fixed

    super_root = NoOpDecision(None, False)
    super_root.add_transition(NoOpLeaf(None, is_valid=not required))

    root = StartAttribute(None, False, name)
    super_root.add_transition(root)

    if 'type' in element.attrib:
        if len(element) != 0:
            raise XmlSchemaException(
                f"Attribute with type cannot have children")
        type = _lookup(element.attrib, 'type', parsed_attributes)
        root.add_transition(resolve_type(type, config))
    else:
        for i in element:
            root.add_transition(parse_xml_element(i, config))

    return super_root


def parse_type(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    if 'name' in element.attrib:
        name = _lookup(element.attrib, 'name', parsed_attributes)
    else:
        name = None
    root = NoOpDecision(name, True)

    for child in element:
        child_node = parse_xml_element(child, config)
        root.add_transition(child_node)

    return root


def parse_element(element: ElementTree.Element, config: Config, parsed_attributes: Set[str]) -> Node:
    name = _lookup(element.attrib, 'name', parsed_attributes)
    if 'type' in element.attrib:
        type = _lookup(element.attrib, 'type', parsed_attributes)
        root = StartNewElement(None, False, name)
        root.add_transition(
            resolve_type(type, config)
        )
        return root
    else:
        if len(element) != 1:
            raise XmlSchemaException(f"Expected exactly one child")
        root = StartNewElement(None, False, name)
        child_node = parse_xml_element(next(iter(element)), config)
        root.add_transition(child_node)
        return root


def _remove_if_available(s: set, key: str):
    if key in s:
        s.remove(key)


def parse_xml_element(element: ElementTree.Element, config: Config) -> Node:
    tag = _get_tag(element)
    try:
        handler = config.tag_handlers[tag]
    except KeyError:
        raise XmlSchemaException(f"Unknown tag '{tag}'")
    parsed_attributes = set(element.attrib.keys())
    node = handler(element, config, parsed_attributes)
    # these are handled by the parent element, namely All, Choice or Sequence
    _remove_if_available(parsed_attributes, 'minOccurs')
    _remove_if_available(parsed_attributes, 'maxOccurs')
    if parsed_attributes:
        raise XmlSchemaException(
            f"Unknown attributes '{parsed_attributes}' in <{tag}>")
    return node


def resolve_type(type: str, config: Config) -> Node:
    if type in config.buildin_types:
        handler = config.buildin_types[type]
        root = NoOpDecision(None, False)
        for value in handler.valid(config):
            value_node = SetValueLeaf(None, True, str(value))
            root.add_transition(value_node)
        for value in handler.invalid(config):
            value_node = SetValueLeaf(None, False, str(value))
            root.add_transition(value_node)
        return root
    else:
        # We assume the type is a user defined simple or complex type
        return Reference(None, type)


def parse(schema: ElementTree.Element, config=None) -> Node:
    if config is None:
        config = default_config()
    tag = _get_tag(schema)
    if tag != 'schema':
        raise XmlSchemaException(f"Expected tag 'schema', got '{tag}'")
    target_namespace = schema.get('targetNamespace', None)

    # The actual schemas
    element_nodes: List[Node] = []
    other_nodes: List[Node] = []
    for i in schema:
        node = parse_xml_element(i, config)
        if _get_tag(i) == 'element':
            element_nodes.append(node)
        else:
            other_nodes.append(node)

    if len(element_nodes) == 0:
        raise XmlSchemaException("No root element found")
    root = element_nodes.pop(0)
    root = root.resolve(element_nodes + other_nodes)
    root.optimize()

    super_root = StartNode(None, True)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutput(target_namespace))
    return super_root
