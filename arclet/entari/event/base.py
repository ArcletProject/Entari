from __future__ import annotations

from typing import Callable, TypeVar

TE = TypeVar("TE", bound="BasedEvent")


class BasedEvent:
    @classmethod
    def dispatch(cls: type[TE], predicate: Callable[[TE], bool] | None = None, name: str | None = None):
        from ..plugin import dispatch

        name = name or getattr(cls, "__publisher__", None)
        return dispatch(cls, predicate=predicate, name=name)  # type: ignore
