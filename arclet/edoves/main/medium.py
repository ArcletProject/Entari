from typing import Optional, Callable, Coroutine, Any, Set
from asyncio import Future, AbstractEventLoop, wait_for
from .monomer import Monomer
from .typings import TMeta
from .utilles import MediumStatus


class MediumObserver:
    __fut: Optional[Future]
    __medium: "BaseMedium"

    def __init__(self, medium: "BaseMedium", loop: AbstractEventLoop) -> None:
        self.__fut = loop.create_future()
        self.__medium = medium

    @property
    def target_status(self) -> "MediumStatus":
        return self.__medium.status

    def set_result(self, result: Any) -> None:
        self.__medium.status = MediumStatus.FINISHED
        self.__fut.set_result(result)

    async def wait_response(self, timeout: float = 0) -> Any:
        if timeout > 0:
            await wait_for(self.__fut, timeout=timeout)
        else:
            await self.__fut
        return self.__fut.result()

    def __del__(self):
        if self.__fut is not None:
            self.__fut.cancel()

    def __repr__(self):
        return f"<MediumObserver @M_{self.__medium.mid}>"


class MediumIdManager:
    """内置的 Medium ID 管理器, 不应在外部使用. 非线程安全."""

    allocated: Set[int] = {0}

    @classmethod
    def head(cls) -> int:
        return min(cls.allocated)

    @classmethod
    def allocate(cls) -> int:
        """分配一个新的 Medium ID.

        Returns:
            int: 生成的 Medium ID. 注意使用 done() 方法标记本 Medium ID.
        """
        new_id = max(cls.allocated) + 1
        cls.allocated.add(new_id)
        return new_id

    @classmethod
    def done(cls, medium_id: int) -> None:
        """标记一个 Medium ID 的任务完成. 本 Medium ID 随后可被复用.

        Args:
            medium_id (int): 标记的 Medium ID.
        """
        if medium_id in cls.allocated:
            cls.allocated.remove(medium_id)


class BaseMedium:
    purveyor: Monomer
    type: str
    content: TMeta
    mid: int
    status: MediumStatus

    __metadata__ = ["type", "content", "purveyor"]

    def __init__(self):
        self.mid = MediumIdManager.allocate()
        self.status = MediumStatus.CREATED

    def __str__(self):
        return self.__repr__()

    def __hash__(self):
        return hash(self.mid)

    def __eq__(self, other):
        return self.mid == other.mid

    def __lt__(self, other):
        return self.mid < other.mid

    def send_response(self, result: Any):
        """发送对medium发起者的响应."""
        self.purveyor.metadata.protocol.set_call(self.mid, result)

    def create(self, purveyor: Monomer, content: Any, medium_type: Optional[str] = None, **kwargs):
        self.purveyor = purveyor
        self.type = medium_type or self.__class__.__name__
        self.content = content
        for k, v in kwargs.items():
            setattr(self, k, v)
        return self

    def action(self, method_name: str) -> Callable[..., Coroutine]:
        for func in [getattr(c, method_name, None) for c in self.purveyor.all_components]:
            if not func:
                continue
            return func

    def __repr__(self):
        return (
            f"<{self.__class__.__name__}; {', '.join([f'{k}={v}' for k, v in vars(self).items() if v])}>"
        )
