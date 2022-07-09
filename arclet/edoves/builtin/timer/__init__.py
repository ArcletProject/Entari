from typing import List, Callable
from datetime import datetime, timedelta
from arclet.letoderea.utils import run_always_await

from arclet.edoves.main.utilles.security import EDOVES_DEFAULT
from arclet.edoves.main.interact.module import BaseModule, ModuleMetaComponent, ModuleBehavior, Component
from arclet.edoves.main.typings import TProtocol

TIMER = Callable[[], timedelta]


class TimerModuleData(ModuleMetaComponent):
    verify_code = EDOVES_DEFAULT
    identifier = "edoves.builtin.timer"
    name = "Timer Module"
    description = "A module for time scheduler"


class TimerMounter:
    route: bool
    interval: TIMER
    next_time: datetime
    scheduler_task: Callable

    def __init__(self, scheduler_task: Callable, interval: TIMER, route: bool = False):
        self.scheduler_task = scheduler_task
        self.interval = interval
        self.route = route
        self.offset = timedelta(seconds=0)
        if not route:
            self.next_time = datetime.now() + self.interval()
        else:
            self.next_time = self.route_time()

    def route_time(self):
        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        second = now.second
        _interval = self.interval()
        if _interval.total_seconds() < 60:
            if _interval.seconds - second < 0:
                minute += 1
            second = _interval.seconds
        elif 0 < _interval.total_seconds() < 3600:
            if _interval.seconds / 60 - minute < 0:
                hour += 1
            minute = _interval.seconds // 60
            second = 0
        elif 3600 < _interval.total_seconds() < 86400:
            if _interval.seconds / 3600 - hour < 0:
                day += 1
            hour = _interval.seconds // 3600
            minute = 0
            second = 0

        elif 0 < _interval.days < 32:
            if _interval.days - day < 0:
                month += 1
            day = _interval.days
            hour = 0
            minute = 0
            second = 0
        return datetime(
            year=year,
            month=month,
            day=day,
            hour=hour,
            minute=minute,
            second=second,
            microsecond=now.microsecond
        )

    async def update(self):
        now = datetime.now()
        self.offset = timedelta(seconds=now.microsecond / 1000000)
        if self.next_time < now - self.offset:
            if self.route:
                self.next_time = self.route_time()
            else:
                self.next_time = now + self.interval() - self.offset
            await run_always_await(self.scheduler_task)


class TimerHandler(Component):
    io: "Timer"
    mounters: List[TimerMounter]

    def __init__(self, io: "Timer"):
        super().__init__(io)
        self.mounters = []

    def add_timer(self, scheduler_task: Callable, interval: TIMER, route: bool = False):
        self.mounters.append(TimerMounter(scheduler_task, interval, route))


class TimerBehavior(ModuleBehavior):

    async def update(self):
        timer_handler = self.get_component(TimerHandler)
        for mounter in timer_handler.mounters:
            await mounter.update()


class Timer(BaseModule):
    prefab_metadata = TimerModuleData
    prefab_behavior = TimerBehavior
    timer_handler: TimerHandler

    __slots__ = ["timer_handler"]

    def __init__(self, protocol: TProtocol):
        super().__init__(protocol)
        self.timer_handler = TimerHandler(self)

    def schedule(
            __timer_self__,
            interval: TIMER,
            route: bool = False,
    ):
        def __wrapper(func):
            __timer_self__.timer_handler.add_timer(func, interval, route)

        return __wrapper
