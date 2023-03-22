from .exception import XmlSchemaException
from .config import Config, TypeGenerator
from .xpath import NormalizedXPath

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
        type_generators={
            'xs:string': TypeGenerator(
                valid=lambda *_: [
                    'foo', generate_random_string(StringProperties(1))],
                invalid=lambda *_: []
            ),
            'xs:dateTime': TypeGenerator(
                valid=lambda *_: ['2001-10-26T21:32:52'],
                invalid=lambda *_: ["foo"]
            ),
            'xs:positiveInteger': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0)],
                invalid=lambda *_: ["-10", "foo"]
            ),
            'xs:integer': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0)],
                invalid=lambda *_: ["xyz"]
            ),
            'xs:boolean': TypeGenerator(
                valid=lambda *_: ["true", "false", "0", "1"],
                invalid=lambda *_: ["foo"]
            ),
            'xs:unsignedInt': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0)],
                invalid=lambda *_: ["-10", "bar"]
            ),
            'xs:unsignedShort': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0)],
                invalid=lambda *_: ["-10", "bar"]
            ),
            'xs:unsignedByte': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0, max_value=255)],
                invalid=lambda *_: ["-10", "bar"]
            ),
            'xs:int': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0)],
                invalid=lambda *_: ["bar"]
            ),
            'xs:double': TypeGenerator(
                valid=lambda *_: [generate_random_number(min_value=0)],
                invalid=lambda *_: ["bar"]
            ),
            'xs:decimal': TypeGenerator(
                valid=lambda *_: [generate_random_number()],
                invalid=lambda *_: ["bar"]
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


def parse_enumeration_restriction(element: ElementTree.Element, path) -> Node:
    if any(_get_tag(child) != 'enumeration' for child in element):
        raise XmlSchemaException("Only enumeration allowed", path)

    root = NoOpDecision(str(path), False)
    for child in element:
        value = child.attrib['value']
        root.add_transition(SetValueLeaf(None, True, value))
    return root


def parse_string_restriction(base: str, props: Dict[str, str], config: Config, parsed_props: Set[str], path: NormalizedXPath) -> Node:
    if base not in ['xs:string', 'xs:token']:
        raise XmlSchemaException(
            f"String restrictions must be based on string class, is {base}",
            path)

    s = StringProperties()
    if 'pattern' in props:
        s.pattern = _lookup(props, 'pattern', parsed_props)
    if 'minLength' in props:
        s.min_length = int(_lookup(props, 'minLength', parsed_props))
    if 'maxLength' in props:
        s.max_length = int(_lookup(props, 'maxLength', parsed_props))

    return SetValueLeaf(str(path), True, generate_random_string(s))


def parse_any(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    if 'processContents' in element.attrib:
        process_contents = _lookup(
            element.attrib, 'processContents', parsed_attributes)
    # TODO: use processContents
    return NoOpLeaf(str(path), True)


def parse_restriction(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    base = _lookup(element.attrib, 'base', parsed_attributes)

    # Normally, we would use base to check if we really restrict the base type
    # However, Fences is not meant to be a schema checker, so we discard it here

    if len(element) == 0:
        return resolve_type(base, element, config, path)

    # Special handling for enumerations
    if _get_tag(next(iter(element))) == 'enumeration':
        return parse_enumeration_restriction(element, path)

    handler = None
    for child in element:
        tag = _get_tag(child)
        if tag in config.restriction_handlers:
            handler = config.restriction_handlers[tag]
            break
    if handler is None:
        child_tags = [_get_tag(i) for i in element]
        raise XmlSchemaException(
            f"No restriction handler found, child tags are {child_tags}", path)

    props = {}
    for child in element:
        if len(child.attrib) != 1 or 'value' not in child.attrib:
            raise XmlSchemaException(
                "Restriction children must have exactly one attribute 'value'", path)
        key = _get_tag(child)
        value = child.attrib['value']
        if key in props:
            raise XmlSchemaException(
                f"Duplicate restriction value '{key}'", path)
        props[key] = value

    parsed_props = set(props.keys())
    node = handler(base, props, config, parsed_props, path)
    if parsed_props:
        raise XmlSchemaException(
            f"Unhandled restriction properties {parsed_props}", path)

    # TODO: in case of contentContent/restriction we have to parse the children as well!
    return node


def parse_annotation(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    return NoOpLeaf(str(path), True)


def parse_content(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    root = NoOpDecision(str(path), True)
    for subpath, child in path.enumerate(element):
        root.add_transition(
            parse_xml_element(child, config, subpath)
        )
    return root


def parse_extension(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    root = NoOpDecision(str(path), True)
    base = _lookup(element.attrib, 'base', parsed_attributes)

    root.add_transition(
        resolve_type(base, element, config, path)
    )

    for subpath, child in path.enumerate(element):
        root.add_transition(
            parse_xml_element(child, config, subpath)
        )

    return root


def _parse_occurs(element: ElementTree.Element, path: NormalizedXPath, parsed_attributes: Set[str]):
    if 'minOccurs' in element.attrib:
        s = _lookup(element.attrib, 'minOccurs', parsed_attributes)
        try:
            min_occurs = int(s)
        except ValueError as e:
            raise XmlSchemaException(
                f"Invalid value for 'minOccurs': {e}", path)
    else:
        min_occurs = 1

    if 'maxOccurs' in element.attrib:
        s = _lookup(element.attrib, 'maxOccurs', parsed_attributes)
        if s == 'unbounded':
            max_occurs = None
        else:
            try:
                max_occurs = int(s)
            except ValueError as e:
                raise XmlSchemaException(
                    f"Invalid value for 'maxOccurs': {e}", path)
    else:
        max_occurs = 1

    return min_occurs, max_occurs


def _repeat(child: Node, min_occurs: int, max_occurs: Optional[int]) -> Node:

    root = NoOpDecision(None, False)
    root.add_transition(NoOpLeaf(None, is_valid=min_occurs == 0))

    # Check parameters
    if max_occurs is None:
        max_occurs = min_occurs + 1
    if min_occurs > max_occurs:
        raise XmlSchemaException(
            f"minOccurs = {min_occurs} > maxOccurs = {min_occurs}", None)

    # valid: min_occurs
    if min_occurs > 0:
        subroot = NoOpDecision(None, True)
        for _ in range(min_occurs):
            subroot.add_transition(child)
        root.add_transition(subroot)

    # invalid: min_occurs - 1
    if min_occurs > 1:
        subroot = NoOpDecision(None, True)
        for _ in range(min_occurs - 1):
            subroot.add_transition(child, True)
        root.add_transition(subroot, False)

    if max_occurs != min_occurs:
        # Valid: max_occurs
        subroot = NoOpDecision(None, True)
        for _ in range(max_occurs):
            subroot.add_transition(child)
        root.add_transition(subroot)

    return root


def parse_sequence(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    if 'name' in element.attrib:
        name = _lookup(element.attrib, 'name', parsed_attributes)
    else:
        name = None
    root = NoOpDecision(str(path), True)
    for subpath, i in path.enumerate(element):
        root.add_transition(parse_xml_element(i, config, subpath))
    return root


def parse_choice(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    if 'name' in element.attrib:
        name = _lookup(element.attrib, 'name', parsed_attributes)
    else:
        name = None
    root = NoOpDecision(str(path), False)
    for subpath, i in path.enumerate(element):
        root.add_transition(parse_xml_element(i, config, subpath))
    return root


def parse_attribute(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    if 'ref' in element.attrib:
        raise XmlSchemaException("references currently not supported", path)

    name = _lookup(element.attrib, 'name', parsed_attributes)
    required = False  # Attributes are optional by default
    if 'use' in element.attrib and _lookup(element.attrib, 'use', parsed_attributes) == "required":
        required = True
    # TODO: can we combine required with fixed?

    if 'default' in element.attrib:
        if required:
            raise XmlSchemaException(
                "Cannot set a default value for a required attribute", path)
        _lookup(element.attrib, 'default', parsed_attributes)

    super_root = NoOpDecision(str(path), False)
    super_root.add_transition(NoOpLeaf(None, is_valid=not required))

    root = StartAttribute(None, False, name)
    super_root.add_transition(root)

    if 'fixed' in element.attrib:
        if 'type' in element.attrib:
            # Discard the type
            _lookup(element.attrib, 'type', parsed_attributes)
        if 'default' in element.attrib:
            raise XmlSchemaException(
                f"Cannot set default value for fixed attribute", path)
        fixed_value = _lookup(element.attrib, 'fixed', parsed_attributes)
        root.add_transition(SetValueLeaf(None, True, fixed_value))
        root.add_transition(SetValueLeaf(
            None, False, fixed_value + '_INVALID'))
    else:
        if 'type' in element.attrib:
            if len(element) != 0:
                raise XmlSchemaException(
                    f"Attribute with type cannot have children", path)
            type = _lookup(element.attrib, 'type', parsed_attributes)
            root.add_transition(resolve_type(type, element, config, path))
        else:
            for subpath, i in path.enumerate(element):
                root.add_transition(parse_xml_element(i, config, subpath))

    return super_root


def parse_type(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    if 'name' in element.attrib:
        name = _lookup(element.attrib, 'name', parsed_attributes)
    else:
        name = None
    root = NoOpDecision(name, True)

    for subpath, child in path.enumerate(element):
        child_node = parse_xml_element(child, config, subpath)
        root.add_transition(child_node)

    return root


def parse_element(element: ElementTree.Element, config: Config, parsed_attributes: Set[str], path: NormalizedXPath) -> Node:
    name = _lookup(element.attrib, 'name', parsed_attributes)
    if 'type' in element.attrib:
        type = _lookup(element.attrib, 'type', parsed_attributes)
        root = StartNewElement(str(path), False, name)
        root.add_transition(
            resolve_type(type, element, config, path)
        )
        return root
    else:
        if len(element) != 1:
            raise XmlSchemaException(f"Expected exactly one child", path)
        root = StartNewElement(str(path), False, name)
        for subpath, child in path.enumerate(element):
            child_node = parse_xml_element(child, config, subpath)
        root.add_transition(child_node)
        return root


def _remove_if_available(s: set, key: str):
    if key in s:
        s.remove(key)


def parse_xml_element(element: ElementTree.Element, config: Config, path: NormalizedXPath) -> Node:
    tag = _get_tag(element)
    try:
        handler = config.tag_handlers[tag]
    except KeyError:
        raise XmlSchemaException(f"Unknown tag '{tag}'", path)
    parsed_attributes = set(element.attrib.keys())
    node = handler(element, config, parsed_attributes, path)

    if 'minOccurs' in element.attrib or 'maxOccurs' in element.attrib:
        min_occurs, max_occurs = _parse_occurs(element, path, parsed_attributes)
        node = _repeat(node, min_occurs, max_occurs)

    if parsed_attributes:
        raise XmlSchemaException(
            f"Unknown attributes '{parsed_attributes}' in <{tag}>", path)

    return node


def resolve_type(type: str, element: ElementTree.Element, config: Config, path: NormalizedXPath) -> Node:
    if type in config.type_generators:
        handler = config.type_generators[type]
        root = NoOpDecision(None, False)
        for value in handler.valid(element, path):
            value_node = SetValueLeaf(None, True, str(value))
            root.add_transition(value_node)
        for value in handler.invalid(element, path):
            value_node = SetValueLeaf(None, False, str(value))
            root.add_transition(value_node)
        return root
    else:
        # We assume the type is a user defined simple or complex type
        return Reference(None, type)


def parse(schema: ElementTree.Element, config: Optional[dict] = None) -> Node:
    actual_config = default_config()
    if config is not None:
        actual_config.merge(config)
    path = NormalizedXPath([('schema', 0)])
    tag = _get_tag(schema)
    if tag != 'schema':
        raise XmlSchemaException(f"Expected tag 'schema', got '{tag}'", path)
    target_namespace = schema.get('targetNamespace', None)

    # The actual schemas
    element_nodes: List[Node] = []
    other_nodes: List[Node] = []
    for subpath, i in path.enumerate(schema):
        node = parse_xml_element(i, actual_config, subpath)
        if _get_tag(i) == 'element':
            element_nodes.append(node)
        else:
            other_nodes.append(node)

    if len(element_nodes) == 0:
        raise XmlSchemaException("No root element found", None)
    root = element_nodes.pop(0)
    root = root.resolve(element_nodes + other_nodes)
    root.optimize()

    super_root = StartNode(str(path), True)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutput(target_namespace))
    return super_root
