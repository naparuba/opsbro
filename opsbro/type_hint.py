# Use only in pycharm for type hint
try:
    from typing import Set, Dict, Any, Tuple, Union, List, Callable, Optional, Text, NoReturn, Type, cast, TYPE_CHECKING, Iterator, NewType, Literal, Collection, Iterable
    
    Str = Union[str]
    Number = Union[float, int]
except ImportError:
    class GenericType(object):
        def __getitem__(self, a):
            pass
    
    
    def cast(x, y):
        return y
    
    
    def _type_mock(p):
        return p
    
    
    def NewType(name, tp):
        return _type_mock
    
    
    TYPE_CHECKING = False
    Literal = GenericType()
    Set = GenericType()
    Dict = GenericType()
    Any = GenericType()
    Tuple = GenericType()
    Union = GenericType()
    List = GenericType()
    Callable = GenericType()
    Optional = GenericType()
    Text = GenericType()
    NoReturn = GenericType()
    Type = GenericType()
    Iterator = GenericType()
    Str = GenericType()
    Number = GenericType()
    Collection = GenericType()
    Iterable = GenericType()
