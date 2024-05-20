from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar, Union

from arclet.alconna import Alconna, Arparma
from tarina import Empty

T = TypeVar("T")


@dataclass
class Match(Generic[T]):
    """
    匹配项，表示参数是否存在于 `all_matched_args` 内

    Attributes:
        result (T): 匹配结果
        available (bool): 匹配状态
    """

    result: T
    available: bool


class Query(Generic[T]):
    """
    查询项，表示参数是否可由 `Arparma.query` 查询并获得结果

    Attributes:
        result (T): 查询结果
        available (bool): 查询状态
        path (str): 查询路径
    """

    result: T
    available: bool
    path: str

    def __init__(self, path: str, default: Union[T, type[Empty]] = Empty):
        self.path = path
        self.result = default  # type: ignore
        self.available = False

    def __repr__(self):
        return f"Query({self.path}, {self.result})"


@dataclass(frozen=True)
class CommandResult:
    source: Alconna
    result: Arparma
    output: Optional[str] = field(default=None)

    @property
    def matched(self) -> bool:
        return self.result.matched
