from __future__ import annotations

from typing import Callable, TypeVar

from ..plugin import dispatch

TE = TypeVar("TE", bound="BasedEvent")


class BasedEvent:
    @classmethod
    def dispatch(cls: type[TE], predicate: Callable[[TE], bool] | None = None, name: str | None = None):
        name = name or getattr(cls, "__disp_name__", None)
        return dispatch(cls, predicate=predicate, name=name)  # type: ignore
