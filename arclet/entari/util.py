from inspect import Parameter, Signature

from arclet.letoderea import Depends


def Param(name: str):
    func = lambda **kwargs: kwargs[name]
    func.__signature__ = Signature(
        parameters=[Parameter(name, Parameter.POSITIONAL_OR_KEYWORD, annotation=str)], return_annotation=str
    )
    return Depends(func)
