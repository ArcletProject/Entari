from copy import deepcopy
from typing import (
    TYPE_CHECKING,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
    Union,
    overload,
)

from satori import Element, Text
from typing_extensions import Self, SupportsIndex

T = TypeVar("T")
TE = TypeVar("TE", bound=Element)
TE1 = TypeVar("TE1", bound=Element)


class MessageChain(List[TE]):
    """消息序列

    参数:
        message: 消息内容
    """

    def __init__(
        self: "MessageChain[Element]",
        message: Union[Iterable[Union[str, TE]], str, TE, None] = None,
    ):
        super().__init__()
        if isinstance(message, str):
            self.__iadd__(Text(message))
        elif isinstance(message, Iterable):
            for i in message:
                self.__iadd__(Text(i) if isinstance(i, str) else i)
        elif isinstance(message, Element):
            self.__iadd__(message)

    def __str__(self) -> str:
        return "".join(str(seg) for seg in self)

    def __repr__(self) -> str:
        return "[" + ", ".join(repr(seg) for seg in self) + "]"

    @overload
    def __add__(self, other: str) -> "MessageChain[Union[TE, Text]]":
        ...

    @overload
    def __add__(self, other: Union[TE, Iterable[TE]]) -> "MessageChain[TE]":
        ...

    @overload
    def __add__(
        self, other: Union[TE1, Iterable[TE1]]
    ) -> "MessageChain[Union[TE, TE1]]":
        ...

    def __add__(
        self, other: Union[str, TE, TE1, Iterable[Union[TE, TE1]]]
    ) -> "MessageChain":
        result: MessageChain = self.copy()
        if isinstance(other, str):
            if result and isinstance(text := result[-1], Text):
                text.text += other
            else:
                result.append(Text(other))
        elif isinstance(other, Element):
            if result and isinstance(result[-1], Text) and isinstance(other, Text):
                result[-1] = Text(result[-1].text + other.text)
            else:
                result.append(other)
        elif isinstance(other, Iterable):
            for seg in other:
                result += seg
        else:
            raise TypeError(f"Unsupported type {type(other)!r}")
        return result

    @overload
    def __radd__(self, other: str) -> "MessageChain[Union[Text, TE]]":
        ...

    @overload
    def __radd__(self, other: Union[TE, Iterable[TE]]) -> "MessageChain[TE]":
        ...

    @overload
    def __radd__(
        self, other: Union[TE1, Iterable[TE1]]
    ) -> "MessageChain[Union[TE1, TE]]":
        ...

    def __radd__(self, other: Union[str, TE1, Iterable[TE1]]) -> "MessageChain":
        result = MessageChain(other)
        return result + self

    def __iadd__(self, other: Union[str, TE, Iterable[TE]]) -> Self:
        if isinstance(other, str):
            if self and isinstance(text := self[-1], Text):
                text.text += other
            else:
                self.append(Text(other))  # type: ignore
        elif isinstance(other, Element):
            if self and (
                isinstance(text := self[-1], Text) and isinstance(other, Text)
            ):
                text.text += other.text
            else:
                self.append(other)
        elif isinstance(other, Iterable):
            for seg in other:
                self.__iadd__(seg)
        else:
            raise TypeError(f"Unsupported type {type(other)!r}")
        return self

    @overload
    def __getitem__(self, args: Type[TE1]) -> "MessageChain[TE1]":
        """获取仅包含指定消息段类型的消息

        参数:
            args: 消息段类型

        返回:
            所有类型为 `args` 的消息段
        """

    @overload
    def __getitem__(self, args: Tuple[Type[TE1], int]) -> TE1:
        """索引指定类型的消息段

        参数:
            args: 消息段类型和索引

        返回:
            类型为 `args[0]` 的消息段第 `args[1]` 个
        """

    @overload
    def __getitem__(self, args: Tuple[Type[TE1], slice]) -> "MessageChain[TE1]":
        """切片指定类型的消息段

        参数:
            args: 消息段类型和切片

        返回:
            类型为 `args[0]` 的消息段切片 `args[1]`
        """

    @overload
    def __getitem__(self, args: int) -> TE:
        """索引消息段

        参数:
            args: 索引

        返回:
            第 `args` 个消息段
        """

    @overload
    def __getitem__(self, args: slice) -> Self:
        """切片消息段

        参数:
            args: 切片

        返回:
            消息切片 `args`
        """

    def __getitem__(
        self,
        args: Union[
            Type[TE1],
            Tuple[Type[TE1], int],
            Tuple[Type[TE1], slice],
            int,
            slice,
        ],
    ) -> Union[TE, TE1, "MessageChain[TE1]", Self]:
        arg1, arg2 = args if isinstance(args, tuple) else (args, None)
        if isinstance(arg1, int) and arg2 is None:
            return super().__getitem__(arg1)
        if isinstance(arg1, slice) and arg2 is None:
            return MessageChain(super().__getitem__(arg1))
        if TYPE_CHECKING:
            assert not isinstance(arg1, (slice, int))
        if issubclass(arg1, Element) and arg2 is None:
            return MessageChain(seg for seg in self if isinstance(seg, arg1))
        if issubclass(arg1, Element) and isinstance(arg2, int):
            return [seg for seg in self if isinstance(seg, arg1)][arg2]
        if issubclass(arg1, Element) and isinstance(arg2, slice):
            return MessageChain([seg for seg in self if isinstance(seg, arg1)][arg2])
        raise ValueError("Incorrect arguments to slice")  # pragma: no cover

    def __contains__(self, value: Union[str, Element, Type[Element]]) -> bool:
        """检查消息段是否存在

        参数:
            value: 消息段或消息段类型
        返回:
            消息内是否存在给定消息段或给定类型的消息段
        """
        if isinstance(value, type):
            return bool(next((seg for seg in self if isinstance(seg, value)), None))
        if isinstance(value, str):
            value = Text(value)
        return super().__contains__(value)

    def has(self, value: Union[str, Element, Type[Element]]) -> bool:
        """与 {ref}``__contains__` <nonebot.adapters.Message.__contains__>` 相同"""
        return value in self

    def index(
        self, value: Union[str, Element, Type[Element]], *args: SupportsIndex
    ) -> int:
        """索引消息段

        参数:
            value: 消息段或者消息段类型
            arg: start 与 end

        返回:
            索引 index

        异常:
            ValueError: 消息段不存在
        """
        if isinstance(value, type):
            first_segment = next((seg for seg in self if isinstance(seg, value)), None)
            if first_segment is None:
                raise ValueError(f"Element with type {value!r} is not in message")
            return super().index(first_segment, *args)
        if isinstance(value, str):
            value = Text(value)
        return super().index(value, *args)  # type: ignore

    def get(self, type_: Type[TE], count: Optional[int] = None) -> "MessageChain[TE]":
        """获取指定类型的消息段

        参数:
            type_: 消息段类型
            count: 获取个数

        返回:
            构建的新消息
        """
        if count is None:
            return self[type_]

        iterator, filtered = (
            seg for seg in self if isinstance(seg, type_)
        ), MessageChain()
        for _ in range(count):
            seg = next(iterator, None)
            if seg is None:
                break
            filtered.append(seg)
        return filtered

    def count(self, value: Union[Type[Element], str, Element]) -> int:
        """计算指定消息段的个数

        参数:
            value: 消息段或消息段类型

        返回:
            个数
        """
        if isinstance(value, str):
            value = Text(value)
        return (
            len(self[value])  # type: ignore
            if isinstance(value, type)
            else super().count(value)  # type: ignore
        )

    def only(self, value: Union[Type[Element], str, Element]) -> bool:
        """检查消息中是否仅包含指定消息段

        参数:
            value: 指定消息段或消息段类型

        返回:
            是否仅包含指定消息段
        """
        if isinstance(value, type):
            return all(isinstance(seg, value) for seg in self)
        if isinstance(value, str):
            value = Text(value)
        return all(seg == value for seg in self)

    def join(
        self, iterable: Iterable[Union[TE1, "MessageChain[TE1]"]]
    ) -> "MessageChain[Union[TE, TE1]]":
        """将多个消息连接并将自身作为分割

        参数:
            iterable: 要连接的消息

        返回:
            连接后的消息
        """
        ret = MessageChain()
        for index, msg in enumerate(iterable):
            if index != 0:
                ret.extend(self)
            if isinstance(msg, Element):
                ret.append(msg)
            else:
                ret.extend(msg.copy())
        return ret

    def copy(self) -> "MessageChain[TE]":
        """深拷贝消息"""
        return deepcopy(self)

    def include(self, *types: Type[Element]) -> Self:
        """过滤消息

        参数:
            types: 包含的消息段类型

        返回:
            新构造的消息
        """
        return MessageChain(seg for seg in self if seg.__class__ in types)

    def exclude(self, *types: Type[Element]) -> Self:
        """过滤消息

        参数:
            types: 不包含的消息段类型

        返回:
            新构造的消息
        """
        return MessageChain(seg for seg in self if seg.__class__ not in types)

    def extract_plain_text(self) -> str:
        """提取消息内纯文本消息"""

        return "".join(seg.text for seg in self if isinstance(seg, Text))
