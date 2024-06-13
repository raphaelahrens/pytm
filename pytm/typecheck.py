from inspect import isclass
from typing import get_type_hints, get_origin, get_args, Union
from types import UnionType, GenericAlias
from functools import reduce
from itertools import zip_longest


def union(a, b):
    return Union[a, b]


def _get_type(value):
    value_type = type(value)
    if value_type in (list, set):
        if len(value) == 0:
            return value_type[()]
        inner_types = reduce(union, (_get_type(v) for v in value))
        return value_type[inner_types]
    if value_type is dict:
        if len(value) == 0:
            return value_type[(), ()]
        key_types = reduce(union, (_get_type(v) for v in value.keys()))
        value_types = reduce(union, (_get_type(v) for v in value.values()))
        return value_type[key_types, value_types]
    if value_type is tuple:
        if len(value) == 0:
            return value_type[()]
        value_types = (_get_type(v) for v in value)
        return value_type[tuple(value_types)]
    else:
        return value_type


class TypeInfo:
    def __init__(self, t):
        self.is_base_type = isclass(t) and not isinstance(t, GenericAlias)
        self.origin = get_origin(t)
        self.is_union = isinstance(t, UnionType) or self.origin is Union
        self.args = get_args(t)


def _cmp_types(annotation, value_type):
    if annotation == value_type:  # Lucky shoot
        return True
    i_anno = TypeInfo(annotation)
    i_value = TypeInfo(value_type)

    if i_anno.is_base_type:
        return False  # since our lucky shot failed and a base type must be equal to value type
    # Union/Option
    if i_anno.is_union:
        if i_value.is_union:
            return all(any((_cmp_types(a_t, v_t) for a_t in i_anno.args)) for v_t in i_value.args)
        else:
            return any((_cmp_types(a_t, value_type) for a_t in i_anno.args))
    # Sequences
    elif i_anno.origin in (list, set) and i_value.origin in (list, set):
        if len(i_value.args) == 0:  # An empty list has no inner type args
            return True
        return _cmp_types(i_anno.args[0], i_value.args[0])  # list and set should only have one arg
    # Dictionary
    elif i_anno.origin is dict and i_value.origin is dict:
        k_anno, v_anno = i_anno.args
        k_value, v_value = i_value.args
        # dict has a two types k and v both need to be a match
        return _cmp_types(k_anno, k_value) and _cmp_types(v_anno, v_value)
    # Tuple
    elif i_anno.origin is tuple and i_value.origin is tuple:
        if i_anno.args[-1] is Ellipsis:
            # If the type is tuple[X,Y, ...] drop the ... and check for infinite Y
            return all(_cmp_types(a, b)
                       for a, b in zip_longest(i_anno.args[:-1], i_value.args, fillvalue=i_anno.args[-2]))
        return all(_cmp_types(a, b) for a, b in zip_longest(i_anno.args, i_value.args))
    return False


class TypeChecked:
    def __setattr__(self, name, value):
        if not name[0] == "_":  # don't type check private attributes
            value_type = _get_type(value)
            anno_type = get_type_hints(self.__class__).get(name)
            if anno_type is None:
                attr = getattr(self.__class__, name, None)
                if isinstance(attr, property):
                    prop_hints = get_type_hints(attr.fset)
                    prop_hints.pop("self", None)
                    prop_hints.pop("return", None)
                    if len(prop_hints) == 1:
                        anno_type = next(iter(prop_hints.values()))
            if anno_type is not None and not _cmp_types(anno_type, value_type):
                raise TypeError(anno_type, value_type, value)
        object.__setattr__(self, name, value)


class TypeError(Exception):
    def __init__(self, annotation, value_type, value):
        self.annotation = annotation
        self.value_type = value_type
        self.value = value
