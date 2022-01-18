from typing import Type, TypeVar, Optional, Dict, Tuple, Any
from types import FunctionType

_T = TypeVar("_T")


def _create_init(needy_args, optional_args):
    header = " def __init__"
    args = ["self"]
    body = []
    local_param = {"Optional": Optional}
    for k, v in needy_args.items():
        args.append(f"{k}: {v.__name__}")
        body.append(f"self.{k} = {k}")
        local_param.setdefault(v.__name__, v)

    for k, v in optional_args.items():
        args.append(f"{k}: Optional[{v[0].__name__}] = None")
        body.append(f"self.{k} = {k} or {v[1]}")
        local_param.setdefault(v[0].__name__, v[0])

    args = ", ".join(args)
    local_vars = ', '.join(local_param.keys())
    header = header + "(" + args + "):"
    body = '\n'.join(f'  {b}' for b in body)
    txt = f'{header}\n{body}'
    txt = f"def __create_fn__({local_vars}):\n{txt}\n return __init__"
    ns = {}
    exec(txt, {}, ns)
    return ns['__create_fn__'](**local_param)


def create_model(cls: Type[_T]) -> Type[_T]:
    if not isinstance(cls.__init__, FunctionType):
        needy_data: Dict = cls.__annotations__
        optional_data: Dict[str, Tuple[Type, Any]] = {}
        for k in cls.__dict__:
            if k in cls.__annotations__:
                optional_data.setdefault(k, (needy_data.pop(k), cls.__dict__[k]))
        cls.__init__ = _create_init(needy_data, optional_data)
    return cls