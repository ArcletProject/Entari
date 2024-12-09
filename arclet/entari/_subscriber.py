from typing import Callable, TypeVar

from arclet.letoderea import Subscriber
from arclet.letoderea.typing import TTarget

T = TypeVar("T")


class SubscribeLoader:
    sub: Subscriber

    def __init__(self, func: TTarget[T], caller: Callable[[TTarget[T]], Subscriber[T]]):
        self.func = func
        self.caller = caller
        self.loaded = False

    def load(self):
        if not self.loaded:
            self.sub = self.caller(self.func)
            self.loaded = True
        return self.sub

    def dispose(self):
        if self.loaded:
            self.sub.dispose()
            self.loaded = False
        del self.func
        del self.caller
