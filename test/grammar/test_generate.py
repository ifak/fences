from fences.grammar.types import Grammar, NonTerminal, Terminal as T
from fences.grammar.convert import convert

from unittest import TestCase
from typing import Callable

from fences.core.node import Node
from fences.core.render import render
from fences.core.debug import check_consistency

import json


class GenerateTest(TestCase):

    def check(self, grammar: Grammar, start: NonTerminal, is_valid: Callable[[any], bool], debug=False):
        graph = convert(grammar, start=start)
        check_consistency(graph)
        if debug:
            render(graph).write_svg('graph.svg')
        for i in graph.generate_paths():
            sample = graph.execute(i.path)
            if debug:
                print("Valid:" if i.is_valid else "Invalid:")
                print(sample)
            if i.is_valid:
                self.assertTrue(is_valid(sample))
            else:
                self.assertFalse(is_valid(sample))

    def test_json(self):
        # Grammar from https://www.json.org/json-en.html
        start = NonTerminal("json")
        element = NonTerminal("element")
        value = NonTerminal("value")
        obj = NonTerminal("object")
        array = NonTerminal("array")
        string = NonTerminal("string")
        number = NonTerminal("number")
        whitespace = NonTerminal("whitespace")
        member = NonTerminal("member")
        members = NonTerminal("members")
        array = NonTerminal("array")
        elements = NonTerminal("elements")
        characters = NonTerminal("characters")
        character = NonTerminal("character")
        escape = NonTerminal("escape")
        hexn = NonTerminal("hex")
        integer = NonTerminal("integer")
        fraction = NonTerminal("fraction")
        exponent = NonTerminal("exponent")
        digits = NonTerminal("digits")
        digit = NonTerminal("digit")
        one_to_nine = NonTerminal("one_to_nine")
        sign = NonTerminal("sign")

        grammar: Grammar = {
            start: [
                element,
            ],
            value: [
                obj,
                array,
                string,
                number,
                "true",
                "false",
                "null",
            ],
            obj: [
                T("{") + whitespace + "}",
                T("{") + members + "}",
            ],
            members: [
                member,
                # member + "," + members,# TODO: recursion
            ],
            member: [
                whitespace + string + whitespace + ":" + element,
            ],
            array: [
                T("[") + whitespace + "]",
                T("[") + elements + "]",
            ],
            elements: [
                element,
                # element + "," + elements, # TODO: recursion
            ],
            element: [
                whitespace + value + whitespace,
            ],
            string: [
                T('"') + characters + '"'
            ],
            characters: [
                "",
                character + characters
            ],
            character: [
                'A',  # TODO: char range
                T('\\') + escape,
            ],
            escape: [
                '"',
                '\\',
                '/',
                'b',
                'f',
                'n',
                'r',
                't',
                T('u') + hexn + hexn + hexn + hexn,
            ],
            hexn: [
                digit,
                'A'  # TODO: char range
            ],
            number: [
                integer + fraction + exponent,
            ],
            integer: [
                digit,
                one_to_nine + digits,
                T('-') + digit,
                T('-') + one_to_nine + digits,
            ],
            digits: [
                digit,
                # digit + digits, # TODO: recursion
            ],
            digit: [
                '0',
                one_to_nine,
            ],
            one_to_nine: [
                '1',  # TODO: char range
            ],
            fraction: [
                "",
                T(".") + digits,
            ],
            exponent: [
                "",
                T('E') + sign + digits,
                T("e") + sign + digits,
            ],
            sign: [
                "",
                "+",
                "-",
            ],
            whitespace: [
                '',
                T('\u0020') + whitespace,
                T('\u000A') + whitespace,
                T('\u000D') + whitespace,
                T('\u0009') + whitespace,
            ]
        }

        def is_valid(sample: str) -> bool:
            try:
                json.loads(sample)
                return True
            except ValueError:
                return False
        self.check(grammar, start, is_valid)

    def test_simple(self):
        start = NonTerminal("start")
        grammar: Grammar = {
            start: {
                T("bar") + start,
                'END'
            }
        }

        def is_valid(sample: str):
            return sample.endswith('END')

        self.check(grammar, start, is_valid)

    def DISABLED_test_recursion(self):
        digits = NonTerminal("digits")
        digit = NonTerminal("digit")

        grammar: Grammar = {
            digits: [
                digit,
                digit + digits,
            ],
            digit: [
                '0',
                '1'
            ],
        }
        self.check(grammar, digits, lambda x: True)


    def test_number(self):
        number = NonTerminal("number")
        integer = NonTerminal("integer")
        fraction = NonTerminal("fraction")
        exponent = NonTerminal("exponent")
        digit = NonTerminal("digit")
        digits = NonTerminal("digits")
        one_to_nine = NonTerminal("one_to_nine")
        sign = NonTerminal("sign")
        grammar: Grammar = {
            number: [
                integer + fraction + exponent,
            ],
            integer: [
                digit,
                one_to_nine + digits,
                T('-') + digit,
                T('-') + one_to_nine + digits,
            ],
            digits: [
                digit,
                # digit + digits,
            ],
            digit: [
                '0',
                one_to_nine,
            ],
            one_to_nine: [
                '1',  # TODO: char range
            ],
            fraction: [
                "",
                T(".") + digits,
            ],
            exponent: [
                "",
                T('E') + sign + digits,
                T("e") + sign + digits,
            ],
            sign: [
                "",
                "+",
                "-",
            ]
        }

        def is_valid(sample: str) -> bool:
            try:
                float(sample)
                return True
            except ValueError:
                return False
        self.check(grammar, number, is_valid)

    def test_whitespace(self):
        whitespace = NonTerminal("whitespace")
        grammar: Grammar = {
            whitespace: [
                '',
                T('\u0020') + whitespace,
                T('\u000A') + whitespace,
                T('\u000D') + whitespace,
                T('\u0009') + whitespace,
            ]
        }

        def is_valid(sample: str) -> bool:
            return sample.strip() == ''

        self.check(grammar, whitespace, is_valid)
