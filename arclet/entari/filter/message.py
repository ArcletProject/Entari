import re
from typing import Any

from arclet.letoderea import STOP, Contexts, Propagator, deref, propagate, provide
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


class fullmatch(Propagator):
    def __init__(
        self, pattern: str | tuple[str, ...], ignorecase: bool = False, bind: str = "fullmatch", priority: int = 80
    ):
        """
        完全匹配

        Args:
            pattern: 指定消息全匹配字符串元组
            ignorecase: 是否忽略大小写, 默认为 False
            bind: 指定注入返回值的参数名称，默认为 "fullmatch"
            priority: 优先级
        """
        if isinstance(pattern, str):
            pattern = (pattern,)
        self.pattern = tuple(map(str.casefold, pattern)) if ignorecase else pattern
        self.ignorecase = ignorecase
        self.priority = priority
        self.bind = bind

    def providers(self):
        if self.bind:
            return [provide(str, self.bind, call=f"$fullmatch_{self.bind}", priority=4)]
        return []

    async def before(self, ctx: Contexts, message: MessageChain):
        text = message.extract_plain_text()
        if not text:
            return STOP
        text = text.casefold() if self.ignorecase else text
        if text in self.pattern:
            return {f"$fullmatch_{self.bind}": text}
        return STOP

    def compose(self):
        yield self.before, True, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


class regexmatch(Propagator):
    def __init__(self, pattern: str, flags: int | re.RegexFlag = 0, priority: int = 80):
        """
        正则匹配，注意正则表达式匹配使用 search 而非 match，如需从头匹配请使用 `r"^xxx"` 来确保匹配开头

        Args:
            pattern: 需要匹配的正则表达式
            flags: 正则匹配标志, 默认为 0
            priority: 优先级
        """
        self.pattern = re.compile(pattern, flags)
        self.priority = priority

    def providers(self):
        return [provide(re.Match, call="$regexmatch", priority=4)]

    async def before(self, ctx: Contexts, message: MessageChain):
        text = message.extract_plain_text()
        if not text:
            return STOP
        if matched := self.pattern.search(text):
            return {"$regexmatch": matched}
        return STOP

    def compose(self):
        yield self.before, True, self.priority

    def __call__(self, func: TCallable) -> TCallable:
        return propagate(self)(func)


def regex_origin():
    return deref(re.Match)


__all__ = ["startswith", "endswith", "fullmatch", "regexmatch", "regex_origin"]
