#! /usr/bin/env python3

from fences.grammar.types import NonTerminal, CharacterRange, Grammar, Terminal as T
from fences import parse_grammar

import os
import shutil

# Grammar from https://cs.lmu.edu/~ray/notes/xmlgrammar/
document = NonTerminal('document')
prolog = NonTerminal("prolog")
element = NonTerminal("element")
char = NonTerminal("Char")
whitespace = NonTerminal("S")
name_char = NonTerminal("NameChar")
letter = NonTerminal("Letter")
digit = NonTerminal("Digit")
combining_char = NonTerminal("CombiningChar")
extender = NonTerminal("Extender")
name = NonTerminal("Name")
names = NonTerminal("Names")
name_tokens = NonTerminal("Nmtokens")
name_token = NonTerminal("Nmtoken")
entity_value = NonTerminal("EntityValue")
pe_reference = NonTerminal("PEReference")
reference = NonTerminal("Reference")
att_value = NonTerminal("AttValue")
system_literal = NonTerminal("SystemLiteral")
pubid_literal = NonTerminal("PubidLiteral")
pubid_char = NonTerminal("PubidChar")
comment = NonTerminal("Comment")
misc = NonTerminal("Misc")
xml_decl = NonTerminal("XMLDecl")
doctype = NonTerminal("doctypedecl")
version_info = NonTerminal("VersionInfo")
encoding = NonTerminal("EncodingDecl")
sd_decl = NonTerminal("SDDecl")
eq = NonTerminal("Eq")
version_num = NonTerminal("VersionNum")
external_id = NonTerminal("ExternalID")
int_subset = NonTerminal("intSubset")
decl_sep = NonTerminal("DeclSep")
markup_decl = NonTerminal("markupdecl")
ext_subset = NonTerminal("extSubset")
ext_subset_decl = NonTerminal("extSubsetDecl")
text_decl = NonTerminal("TextDecl")
empty_element_tag = NonTerminal("EmptyElemTag")
stag = NonTerminal("STag")
content = NonTerminal("content")
etag = NonTerminal("ETag")
attribute = NonTerminal("Attribute")
char_data = NonTerminal("CharData")
element_decl = NonTerminal("elementdecl")
content_spec = NonTerminal("contentspec")
children = NonTerminal("children")
cp = NonTerminal("cp")
choice = NonTerminal("choice")
seq = NonTerminal("seq")
ext_parsed_ent = NonTerminal("extParsedEnt")
enc_name = NonTerminal("EncName")
notation_decl = NonTerminal("NotationDecl")
public_id = NonTerminal("PublicID")
letter = NonTerminal("Letter")
base_char = NonTerminal("BaseChar")
ideographic = NonTerminal("Ideographic")
char_ref = NonTerminal("CharRef")
entity_ref = NonTerminal("EntityRef")

grammar: Grammar = {
    # Document
    document: prolog + element,  # TODO: + misc*
    # Character Range
    char: [
        chr(0x9),
        chr(0xA),
        # chr(0xD),
        CharacterRange(chr(0x20), chr(0xD7FF)),
        CharacterRange(chr(0xE000), chr(0xFFFD)),
        CharacterRange(chr(0x10000), chr(0x10FFFF)),
    ],
    # Whitespace
    whitespace: (
        T(chr(0x20)) |
        chr(0x9) |
        # chr(0xD) |
        chr(0xA)
    )*(1, None),
    # Names and Tokens
    name_char: [
        letter,
        digit,
        '.',
        '-',
        '_',
        ':',
        combining_char,
        extender,
    ],
    name: (letter | '_' | ':') + name_char*(0, None),
    names: name + (' ' + name)*(0, None),
    name_token: [
        name_char,
        name_char + name_token,
    ],
    name_tokens: [
        name_token,
        name_token + ' ' + name_tokens,
    ],
    # Literals
    entity_value: [
        '"' + (
            CharacterRange(None, None)  # TODO: without % and &
            | pe_reference | reference
        )*(0, None) + '"',
        "'" + (
            CharacterRange(None, None)  # TODO: without % and &
            | pe_reference | reference
        )*(0, None) + "'",
    ],
    att_value: [
        '"' + (
            CharacterRange(None, None)  # TODO: without % and &
            | reference
        )*(0, None) + '"',
        "'" + (
            CharacterRange(None, None)  # TODO: without % and &
            | reference
        )*(0, None) + "'",
    ],
    system_literal: [
        ('"' + CharacterRange(None, None) + '"'),  # TODO: without "
        ("'" + CharacterRange(None, None) + "'"),  # TODO: without "
    ],
    pubid_literal: [
        '"' + pubid_char*(0, None) + '"',
        "'" + pubid_char*(0, None) + "'",  # TODO without "'"
    ],
    pubid_char: [
        chr(0x20),
        chr(0xD),
        chr(0xA),
        CharacterRange('a', 'z'),
        CharacterRange('A', 'Z'),
        CharacterRange('0', '9'),
        "-", "'", "(", ")", "+", ",", ".", "/", ":", "=", "?",
        ";", "!", "*", "#", "@", "$", "_", "%",
    ],
    # Character Data
    char_data: T('A')*(1, None),  # TODO
    # Comments
    # TODO: without -
    comment: '<!--' + (char | ('-' + char))*(0, None) + '-->',
    # Processing Instructions
    # TODO
    # CDATA Sections
    # TODO
    # Prolog
    prolog:
        xml_decl*(0, 1) +
        misc*(0, None) + (
            doctype +
            misc*(0, None)
        )*(0, 1),
    xml_decl: '<?xml' + version_info + encoding + sd_decl + whitespace + '?>',  # TODO: optionals
    version_info: whitespace + 'version' + eq + (
            "'" + version_num + "'" |
            '"' + version_num + '"'
    ),
    eq: whitespace*(0, 1) + '=' + whitespace*(0, 1),
    version_num: '1.0',
    misc: comment | whitespace,  # TODO: | PI
    # Document Type Definition
    doctype:
        '<!DOCTYPE' +
        whitespace +
        name +
        (whitespace + external_id)*(0, 1) +
        whitespace*(0, 1) +
        ('[' + int_subset + ']' + whitespace*(0, 1))*(0, 1) +
        '>',
    decl_sep: pe_reference | whitespace,
    int_subset: (markup_decl | decl_sep)*(0, None),
    # TODO: elementdecl | AttlistDecl | EntityDecl | NotationDecl |  PI | Comment
    markup_decl: comment,
    ext_subset: text_decl*(0, 1) + ext_subset_decl*(0, 1),
    # TODO: conditionalSect,
    ext_subset_decl: (markup_decl | decl_sep)*(0, None),
    # Standalone Document Declaration
    sd_decl: whitespace + 'standalone' + eq + (
        ("'" + (T('yes') | 'no') + "'") |
        ('"' + (T('yes') | 'no') + '"')
    ),
    # Elements, Tags and Element Content
    element: [
        empty_element_tag,
        stag + content + etag
    ],
    stag: '<' + name + (whitespace + attribute)*(0, None) + whitespace*(0, 1) + '>',
    attribute:  name + eq + att_value,
    etag: '</' + name + whitespace*(0, None) + '>',
    content:
        char_data*(0, 1) +
        (
            (element | reference | comment) +  # TODO: CDSect | PI |
            char_data*(0, 1)
    )*(0, None),
    empty_element_tag:
        '<' +
        name +
        (whitespace + attribute)*(0, None) +
        whitespace*(0, 1) +
        '/>',
    # Elements in the DTD
    element_decl: '<!ELEMENT' + whitespace + name + whitespace + content_spec + whitespace*(0, 1) + '>',
    content_spec: ['EMPTY', 'ANY', children],  # TODO: mixed
    children: (choice | seq) + (T('?') | '*' | '+')*(0, 1),
    cp: (name | choice | seq) + (T('?') | '*' | '+')*(0, 1),
    choice: '(' + whitespace*(0, 1) + cp + (whitespace*(0, 1) + '|' + whitespace*(0, 1) + cp)*(1, None) + whitespace*(0, 1) + ')',
    seq:    '(' + whitespace*(0, 1) + cp + (whitespace*(0, 1) + ',' + whitespace*(0, 1) + cp)*(0, None) + whitespace*(0, 1) + ')',
    # Attributes in the DTD
    # TODO
    # Conditional Section
    # TODO
    # Character and Entity References
    char_ref: [
        '&#' + CharacterRange('0', '9')*(1, None) + ';',
        '&#x' + (
            CharacterRange('0', '9') |
            CharacterRange('a', 'f') |
            CharacterRange('A', 'F')
        )*(1, None) +
        ';',
    ],
    reference: entity_ref | char_ref,
    entity_ref: '&' + name + ';',
    pe_reference: '%' + name + ';',
    # Entity Declarations
    # TODO
    external_id: [
        'SYSTEM' + whitespace + system_literal,
        'PUBLIC' + whitespace + pubid_literal + whitespace + system_literal
    ],
    # Parsed Entities
    text_decl: '<?xml' + version_info*(0, 1) + element_decl + whitespace*(1, 0) + '?>',
    ext_parsed_ent: text_decl*(0, 1) + content,
    encoding: whitespace + 'encoding' + eq + (
        '"' + enc_name + '"' |
        "'" + enc_name + "'"
    ),
    enc_name:
        (CharacterRange('A', 'Z') | CharacterRange('a', 'z')) +
        (
            (CharacterRange('A', 'Z') | CharacterRange('a', 'z') | CharacterRange('0', '9') | '.' | '_') |
            '-'
    )*(0, None),
    notation_decl:
        '<!NOTATION' + whitespace + name + whitespace +
        (external_id | public_id) +
        whitespace*(0, 1) + '>',
    public_id: 'PUBLIC' + whitespace + pubid_literal,
    # Characters
    letter: base_char | ideographic,
    base_char: [
        CharacterRange(chr(0x41), chr(0x5A)),
        # TODO: remaining chars
    ],
    ideographic: [
        CharacterRange(chr(0x4E00), chr(0x9FA5)),
        chr(0x3007),
        CharacterRange(chr(0x3021), chr(0x3029))
    ],
    combining_char: [
        CharacterRange(chr(0x300), chr(0x345)),
        # TODO: remaining chars
    ],
    digit: [
        CharacterRange(chr(0x30), chr(0x39)),
        # TODO: remaining chars
    ],
    extender: [
        chr(0xB7),
        # TODO: remaining chars
    ]
}

script_dir = os.path.dirname(os.path.realpath(__file__))
samples_dir = os.path.join(script_dir, 'samples')
if os.path.exists(samples_dir):
    shutil.rmtree(samples_dir)
os.mkdir(samples_dir)

graph = parse_grammar(grammar, document)
for idx, i in enumerate(graph.generate_paths()):
    sample = graph.execute(i.path)
    open(os.path.join(samples_dir, f"{idx}.xml"), "w").write(sample)
