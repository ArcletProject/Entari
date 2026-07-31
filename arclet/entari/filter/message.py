import re
from typing import Any

from arclet.letoderea import STOP, Propagator, propagate, Contexts, provide
from arclet.letoderea.utils import TCallable
from nepattern import ANY, BasePattern, MatchMode, parser
from satori import Text
from tarina import Empty

from ..const import ITEM_MESSAGE_CONTENT
from ..message import MessageChain


def _prefixed(pat: BasePattern):
    if pat.mode not in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
        return pat
    new_pat = pat.copy()
    new_pat.regex_pattern = re.compile(f"^{new_pat.pattern}")
    return new_pat


def _suffixed(pat: BasePattern):
    if pat.mode not in (MatchMode.REGEX_MATCH, MatchMode.REGEX_CONVERT):
        return pat
    new_pat = pat.copy()
    new_pat.regex_pattern = re.compile(f"{new_pat.pattern}$")
    return new_pat


class startswith(Propagator):
    def __init__(self, prefix: Any, include: bool = False, bind: str | None = None, priority: int = 80):
        """
        前缀匹配

        Args:
            prefix: 需要匹配的前缀, 支持格式有 a|b , ['a', At(...)] 等
            include: 指示消息链是否仅返回前缀被匹配的部分, 默认为 False
            bind: 指定注入返回值的参数名称，未指定则注入到所有的 MessageChain 参数中
            priority: 优先级
        """
        self.prefix = prefix
        self.priority = priority
        self.include = include
        self.bind = bind

        pattern = BasePattern(prefix, mode=MatchMode.REGEX_MATCH) if isinstance(prefix, str) else parser(prefix)
        if pattern in (ANY, Empty):
            raise ValueError(prefix)
        self.pattern = _prefixed(pattern)

    def providers(self):
        if self.bind:
            return [provide(MessageChain, self.bind, call=f"$startswith_{self.bind}", priority=4)]
        return []

    async def before(self, ctx: Contexts, message: MessageChain):
        message = message.fork()
        if message:
            elem = message[0]
            if isinstance(elem, Text) and (res := self.pattern.validate(elem.text)).success:
                if self.include:
                    message = MessageChain(Text(str(res.value())))
                else:
                    message[0] = Text(elem.text[len(str(res.value())) :].lstrip())
            elif self.pattern.validate(elem).success:
                if self.include:
                    message = MessageChain(elem)
                else:
                    message.remove(elem)
            else:
                return STOP
        if self.bind:
            return {f"$startswith_{self.bind}": message}
        if ITEM_MESSAGE_CONTENT in ctx:
            return {ITEM_MESSAGE_CONTENT: message}
        return {"$message": message}

    def compose(self):
        yield self.before, True, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class endswith(Propagator):
    def __init__(self, suffix: Any, include: bool = False, bind: str | None = None, priority: int = 80):
        """
        后缀匹配

        Args:
            suffix: 需要匹配的后缀, 支持格式有 a|b , ['a', At(...)] 等
            include: 指示消息链是否仅返回后缀被匹配的部分, 默认为 False
            bind: 指定注入返回值的参数名称，未指定则注入到所有的 MessageChain 参数中
            priority: 优先级
        """
        self.suffix = suffix
        self.priority = priority
        self.include = include
        self.bind = bind

        pattern = BasePattern(suffix, mode=MatchMode.REGEX_MATCH) if isinstance(suffix, str) else parser(suffix)
        if pattern in (ANY, Empty):
            raise ValueError(suffix)
        self.pattern = _suffixed(pattern)

    def providers(self):
        if self.bind:
            return [provide(MessageChain, self.bind, call=f"$endswith_{self.bind}", priority=4)]
        return []

    async def before(self, ctx: Contexts, message: MessageChain):
        message = message.fork()
        if message:
            elem = message[-1]
            if isinstance(elem, Text) and (res := self.pattern.validate(elem.text)).success:
                if self.include:
                    message = MessageChain(Text(str(res.value())))
                else:
                    message[-1] = Text(elem.text[: elem.text.rfind(str(res.value()))].rstrip())
            elif self.pattern.validate(elem).success:
                if self.include:
                    message = MessageChain(elem)
                else:
                    message.remove(elem)
            else:
                return STOP
        if self.bind:
            return {f"$endswith_{self.bind}": message}
        if ITEM_MESSAGE_CONTENT in ctx:
            return {ITEM_MESSAGE_CONTENT: message}
        return {"$message": message}

    def compose(self):
        yield self.before, True, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


__all__ = ["startswith", "endswith"]
