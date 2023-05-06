from fences.core.node import Decision, Node, Leaf, NoOpDecision, NoOpLeaf
from .exception import RegexException, InternalParserException
from typing import Set, Dict, Union
import string

from .grammar import Lark_StandAlone, Tree, Token, LarkError
_parser = Lark_StandAlone()


class Repetition:
    Infinity = 'inf'

    def __init__(self, min: int, max: Union[int, None]) -> None:
        self.min = min
        self.max = max

    def __str__(self) -> str:
        return f"[{self.min}, {self.max}]"


class CreateInputNode(Decision):
    def __init__(self) -> None:
        super().__init__(None, False)

    def apply(self, data: any) -> any:
        return []

    def description(self) -> str:
        return "Create input"


class FetchOutputNode(Leaf):
    def __init__(self) -> None:
        super().__init__(None, True)

    def apply(self, data: any) -> any:
        return "".join(data)

    def description(self) -> str:
        return "Fetch output"


class AppendCharsLeaf(Leaf):

    def __init__(self, id: str, is_valid: bool, char: str) -> None:
        super().__init__(id, is_valid)
        self.char = char

    def apply(self, data: list) -> any:
        data.append(self.char)
        return data

    def mask(self, s: str) -> str:
        allowed = string.ascii_letters + string.digits
        return "".join([
            (i if i in allowed else f"chr({ord(i)})") for i in s
        ])

    def description(self) -> str:
        return f"Append {self.mask(self.char)}"


def _parse_repetition(tree: Tree[Token]) -> "MatchConverter.Repetition":
    assert len(tree.children) in [1, 2]
    repetition_type = tree.children[0]
    assert isinstance(repetition_type, Tree)
    assert repetition_type.data == 'repetition_type'
    assert len(repetition_type.children) == 1
    qualifier = repetition_type.children[0]
    if isinstance(qualifier, Tree):
        if qualifier.data == 'range':
            assert len(qualifier.children) in [1, 2]
            first = qualifier.children[0]
            assert isinstance(first, Token)
            first_value = int(first.value)

            if len(qualifier.children) == 2:
                second = qualifier.children[1]
                assert isinstance(second, Token)
                second_value = int(second.value)
            else:
                second_value = first_value
            if first_value > second_value:
                raise RegexException(
                    f"Invalid range: {first_value} > {second_value}")
            return Repetition(first_value, second_value)
        raise InternalParserException(
            f"Unknown type {type(qualifier)} ('{qualifier.data}')")
    elif isinstance(qualifier, Token):
        if qualifier.type == 'ZERO_OR_MORE_QUANTIFIER':
            return Repetition(0, None)
        elif qualifier.type == 'ONE_OR_MORE_QUANTIFIER':
            return Repetition(1, None)
        elif qualifier.type == 'ZERO_OR_ONE_QUANTIFIER':
            return Repetition(0, 1)
        raise InternalParserException(
            f"Unknown type {type(qualifier)} ('{qualifier.type}')")
    raise InternalParserException(f"Unknown type {type(qualifier)}")


def _add_repetition(root: Decision, item: Node, times: int):
    assert times >= 0
    subroot = NoOpDecision(None, True)
    for _ in range(times):
        subroot.add_transition(item)
    root.add_transition(subroot)


def _repeat(root: Decision, item: Node, rep: Repetition):
    # Instantiate open ranges
    if rep.max is None:
        rep.max = rep.min + 2
    assert rep.min is not None

    # Special case: do nothing
    # TODO: this invalid for rep.min == 0
    if rep.min == 0 or rep.max == 0:
        root.add_transition(NoOpLeaf(None, True))

    # TODO: invalid: rep.min-1 and rep.max+1
    if rep.min > 0:
        _add_repetition(root, item, rep.min)
    if rep.max != rep.min:
        _add_repetition(root, item, rep.max)


class TreeConverter:

    children: Dict[str, "TreeConverter"] = {}
    all_transitions = False

    def __init__(self, tree: Tree[Token]) -> None:
        assert isinstance(tree, Tree)
        self.tree = tree

    def convert(self, child: Union[Tree, Token]) -> Node:
        if isinstance(child, Tree):
            try:
                converter = self.children[str(child.data)]
            except KeyError as e:
                raise InternalParserException(
                    f"Unexpected token {e} ({type(self)})")
            return converter(child).to_node()
        elif isinstance(child, Token):
            try:
                method = "convert_" + child.type.lower()
            except KeyError as e:
                raise InternalParserException(f"Unexpected token {e}")
            return getattr(self, method)(child)
        else:
            raise InternalParserException(f"Unexpected type {type(child)}")

    def to_node(self) -> Node:
        root = NoOpDecision(None, self.all_transitions)
        for child in self.tree.children:
            root.add_transition(self.convert(child))
        return root


class GroupConverter(TreeConverter):
    children = {
        'expression': None
    }

    def to_node(self) -> Node:
        expression = None
        repetition = None
        for child in self.tree.children:
            if isinstance(child, Tree):
                if child.data == 'expression':
                    expression = child
                elif child.data == 'repetition':
                    repetition = child
        if expression is None:
            raise InternalParserException("Expression not found")

        item = ExpressionConverter(expression).to_node()
        if repetition is None:
            return item
        else:
            root = NoOpDecision(None, self.all_transitions)
            rep = _parse_repetition(repetition)
            _repeat(root, item, rep)
            return root


class CharacterRangeConverter(TreeConverter):
    def to_node(self) -> Node:
        assert len(self.tree.children) == 2
        assert self.tree.data == 'character_range'
        first = self.tree.children[0]
        second = self.tree.children[1]
        assert isinstance(first, Token)
        assert isinstance(second, Token)
        if ord(first.value) > ord(second.value):
            raise RegexException(
                f"Invalid character range: {first.value}-{second.value}")
        root = NoOpDecision(None, self.all_transitions)
        root.add_transition(AppendCharsLeaf(None, True, first.value))
        root.add_transition(AppendCharsLeaf(None, True, second.value))
        # TODO: invalid samples
        # root.add_transition(AppendCharsLeaf(None, False, chr(ord(first.value)-1)))
        # root.add_transition(AppendCharsLeaf(None, False, chr(ord(second.value)+1)))
        return root


class CharacterGroupItemConverter(TreeConverter):
    children = {
        'character_range': CharacterRangeConverter
    }

    def convert_char(self, token: Token) -> Node:
        return AppendCharsLeaf(None, True, token.value)

    def convert_character_class(self, token: Token) -> Node:
        samples = {
            '\w': 'hello',
            '\W': '42',
            '\d': '42',
            '\D': 'world',
        }
        try:
            sample = samples[str(token)]
        except KeyError as e:
            raise RegexException(f"Unknown character class {e}")
        return AppendCharsLeaf(None, True, sample)


class CharacterGroupConverter(TreeConverter):

    children = {
        'character_group_item': CharacterGroupItemConverter
    }

    def to_node(self) -> Node:
        assert len(self.tree.children) >= 1
        invert = False
        start = 0
        if isinstance(self.tree.children[0], Token) and self.tree.children[0].type == 'CHARACTER_GROUP_NEGATIVE_MODIFIER':
            invert = True
            start = 1
        root = NoOpDecision(None, self.all_transitions)
        for child in self.tree.children[start:]:
            root.add_transition(self.convert(child))
        # TODO: use invert
        return root


class MatchCharacterClassConverter(TreeConverter):
    children = {
        'character_group': CharacterGroupConverter
    }


class EscapedCharacterConverter(TreeConverter):
    def convert_special_char(self, token: Token):
        return AppendCharsLeaf(None, True, str(token))


class MatchItemConverter(TreeConverter):
    children = {
        'match_character_class': MatchCharacterClassConverter,
        'escaped_character': EscapedCharacterConverter,
    }

    def convert_char(self, token: Token):
        return AppendCharsLeaf(None, True, str(token))

    def convert_match_any_character(self, token: Token):
        return NoOpLeaf(None, True)


class MatchConverter(TreeConverter):
    children = {
        'matchitem': MatchItemConverter,
        'match_character_class': MatchCharacterClassConverter,
    }
    all_transitions = False

    def to_node(self) -> Node:
        assert len(self.tree.children) in [1, 2]
        assert self.tree.children[0].data == 'matchitem'
        item = MatchItemConverter(self.tree.children[0]).to_node()
        if len(self.tree.children) == 2:
            repetition = self.tree.children[1]
            assert isinstance(repetition, Tree)
            assert repetition.data == 'repetition'
            rep = _parse_repetition(repetition)
            root = NoOpDecision(None, self.all_transitions)
            _repeat(root, item, rep)
            return root
        else:
            return item


class SubExpressionItemConverter(TreeConverter):
    children = {
        'match': MatchConverter,
        'group': GroupConverter,
    }

    def convert_anchor(self, token: Token):
        # TODO
        return NoOpLeaf(None, True)


class SubExpressionConverter(TreeConverter):
    children = {
        'subexpressionitem': SubExpressionItemConverter
    }
    all_transitions = True


class ExpressionConverter(TreeConverter):
    children = {
        'subexpression': SubExpressionConverter,
        'expression': None,
    }


class StartConverter(TreeConverter):
    children = {
        'expression': ExpressionConverter,
    }
    all_transitions = True

    def convert_start_of_string_anchor(self, token: Token):
        return AppendCharsLeaf(None, True, 'X')


GroupConverter.children['expression'] = ExpressionConverter
ExpressionConverter.children['expression'] = ExpressionConverter


def unescape(s: str) -> str:
    for i in ['\\', '{', '}', '.', '(', ')', '[', ']']:
        s = s.replace('\\' + i, i)
    return s


def parse(regex: str) -> Node:
    regex = unescape(regex)
    try:
        tree: Tree[Token] = _parser.parse(regex)
    except LarkError as e:
        raise RegexException(f"Cannot parse '{regex}' as regex: {e}")
    # print(tree.pretty())
    assert isinstance(tree, Tree)
    assert tree.data == 'start'
    root = StartConverter(tree).to_node()
    root.optimize()

    create_input = CreateInputNode()
    super_root = NoOpDecision(None, True)
    create_input.add_transition(super_root)
    super_root.add_transition(root)
    super_root.add_transition(FetchOutputNode())
    return create_input
