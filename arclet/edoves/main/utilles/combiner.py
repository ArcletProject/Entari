from typing import TypeVar, Union, Type, Optional
from inspect import isclass
from ..component.behavior import BaseBehavior

TB = TypeVar("TB", bound=BaseBehavior)


def combine_behaviors(*behavior: Union[Type[TB], TB]) -> Optional[Type[BaseBehavior]]:
    """
    混合传入的行为器, 要求传入的所有行为器的父类与io属性类型一致

    Behavior_B(BehaviorA){io: Monomer}, Behavior_C(BehaviorA){io: Monomer}  # 通过

    Behavior_B(BehaviorA){io: Monomer}, Behavior_C(BehaviorD){io: Monomer}  # 不通过

    Behavior_B(BehaviorA){io: Module}, Behavior_C(BehaviorA){io: Monomer}  # 不通过

    """
    if not behavior:
        return
    base = behavior[0].__base__ if isclass(behavior[0]) else behavior[0].__class__.__base__
    io = behavior[0].__annotations__.get("io") if isclass(behavior[0]) else behavior[0].io.__class__
    for be in behavior:
        if isclass(be):
            if be.__base__ != base or be.__annotations__.get("io") != io:
                return
        else:
            if be.__class__.__base__ != base or be.io.__class__ != io:
                return

    class CombineBehavior(*behavior):
        pass
    return CombineBehavior
