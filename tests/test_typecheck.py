import unittest
from dataclasses import dataclass
from typing import Union, Annotated, TypeAlias, TypeVar, Any

from functools import reduce
from hypothesis.strategies import composite, sampled_from, sets, builds, recursive, integers
from hypothesis import given

from pytm import typecheck
from pytm.typecheck import required, optional


BASE_TYPES = sampled_from(elements=[int, str, float, bool, complex, bytes, type(None)])


@composite
def dict_generate(draw, elements):
    key_type = draw(BASE_TYPES)
    value_type = draw(elements)
    return dict[key_type, value_type]


@composite
def tuple_generate(draw, elements):
    count = draw(integers(min_value=2, max_value=8))
    value_type = tuple(draw(sets(elements, min_size=count, max_size=count)))
    return tuple[value_type]


def union(ts):
    return reduce(lambda a, b: a | b, ts)


def union2(ts):
    return reduce(lambda a, b: Union[a, b], ts)


def list_type(t):
    return list[t]


# Construct simple base type Unions
BASE_UNION_TYPES = builds(union, sets(BASE_TYPES, min_size=1))

# Construct complex type expressions
T = recursive(BASE_TYPES,
              lambda child:
              builds(union, sets(child, min_size=1, max_size=7)) |
              builds(union2, sets(child, min_size=1, max_size=7)) |
              builds(list_type, child) |
              dict_generate(child) |
              tuple_generate(child),
              max_leaves=10
              )


def create_subset_type(t):
    i_t = typecheck.TypeInfo(t)
    if i_t.is_base_type:
        return t
    if i_t.is_union:
        return union((i_t.args[:-1]))
    return i_t.origin[tuple((create_subset_type(arg) for arg in i_t.args))]


@composite
def union_and_sub(draw, elements=T):
    ts = list(draw(sets(elements, min_size=1, max_size=3)))
    sub_types = list(draw(sets(sampled_from(elements=ts), min_size=1, max_size=len(ts))))
    t = union(ts)
    s = union(sub_types)
    return (t, s)


class B(typecheck.TypeChecked):

    one: str = required("", """ One is the loneliest number it's the number one""")

    # Maybe like this
    abc: Annotated[
            str,
            "Very long text. Which is too long for this! Which makes it look silly, but anyway"
            ] = "ahhh"

    def __init__(self, one: str):
        self.one = one


class InnerA(typecheck.TypeChecked):
    one: int | float
    two: str

    def __init__(self):
        self.one = 1
        self.two = ""


class A(typecheck.TypeChecked):
    first: int = required(0, "first attr")
    second: list[int] = optional([], "Optional second attr")
    third: B = required(None, "This is strange")
    complex_type: list[int | float | str] | dict[int | float, str | bytes]
    inner: InnerA

    _xyz: int

    def __init__(self):
        self.first = 0
        self.second = [1]
        self._xyz = 0
        self.inner = InnerA()

    @property
    def prop(self) -> int:
        return self._xyz

    @prop.setter
    def prop(self, v: int) -> float:
        self._xyz = v
        return 5

    @property
    def test(self):
        return 0

    @test.setter
    def test(self, v: str, k: int, lol: float):
        return 5


class C(A):
    forth: float


@dataclass
class D(A):
    forth: float = 0.0
    abc: str = "lol"


class TestCmpTypes(unittest.TestCase):
    @given(T)
    def test_base_type(self, t):
        assert typecheck._cmp_types(t, t)

    @given(T)
    def test_sunset_type(self, t):
        assert typecheck._cmp_types(t, create_subset_type(t))

    @given(BASE_UNION_TYPES, union_and_sub())
    def test_base_dict(self, k, v):
        v_t, v_s = v
        assert typecheck._cmp_types(dict[k, v_t], dict[k, v_s])

    @given(union_and_sub())
    def test_union(self, x):
        t, s = x
        assert typecheck._cmp_types(t, s)


class TestTypeChecked(unittest.TestCase):
    def testA(self):
        a = A()
        a.first = 1
        a.second = [1, 2, 3]
        a.third = B("")
        a.complex_type = [1]
        a.complex_type = [1.0]
        a.complex_type = ["one"]
        a.complex_type = {1: "one"}
        a.complex_type = {1.0: b"one"}
        a.inner.one = 1.0

    def testC(self):
        c = C()
        c.first = 1
        c.second = [1, 2, 3]
        c.third = B("")
        c.complex_type = [1]
        c.complex_type = [1.0]
        c.complex_type = ["one"]
        c.complex_type = {1: "one"}
        c.complex_type = {1.0: b"one"}
        c.inner.one = 1.0
        c.forth = 10.0
        c.abc = "LOL"

    def test_empty_list(self):
        a = A()
        a.second = []

    def testA_false_type(self):
        a = A()
        with self.assertRaises(typecheck.TypeError):
            a.first = 1.0
        with self.assertRaises(typecheck.TypeError):
            a.second = [1, 2, 3.0]
        with self.assertRaises(typecheck.TypeError):
            a.complex_type = [b""]
        with self.assertRaises(typecheck.TypeError):
            a.complex_type = [B("test")]
        with self.assertRaises(typecheck.TypeError):
            a.inner.one = []

    def test_property(self):
        a = A()
        a.prop = 4
        with self.assertRaises(typecheck.TypeError):
            a.prop = 4.0
