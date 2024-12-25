import asyncio
from asyncio.events import _get_running_loop  # type: ignore
from datetime import datetime, timedelta
from traceback import print_exc
from typing import Callable, Literal

from arclet.letoderea import es
from arclet.letoderea.typing import Contexts
from launart import Launart, Service, any_completed
from launart.status import Phase

from .plugin import RootlessPlugin, _current_plugin


class _ScheduleEvent:
    async def gather(self, context: Contexts):
        pass


pub = es.define(_ScheduleEvent, "entari.event/schedule")
scope = es.scope("entari.scheduler")
contexts: Contexts = {"$event": _ScheduleEvent()}  # type: ignore


class TimerTask:
    def __init__(self, supplier: Callable[[], timedelta], sub_id: str):
        self.sub_id = sub_id
        self.supplier = supplier
        self.handle = None

    def start(self, queue: asyncio.Queue):
        loop = asyncio.get_running_loop()
        self.handle = loop.call_later(self.supplier().total_seconds(), queue.put_nowait, self)

    def cancel(self):
        if self.handle and not self.handle.cancelled():
            self.handle.cancel()


class Scheduler(Service):

    def __init__(self):
        super().__init__()
        self.queue: asyncio.Queue[TimerTask] = asyncio.Queue()
        self.timers: dict[str, TimerTask] = {}

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    async def fetch(self):
        while True:
            timer = await self.queue.get()
            if timer.sub_id not in scope.subscribers:
                del self.timers[timer.sub_id]
                continue
            timer.start(self.queue)
            try:
                await scope.subscribers[timer.sub_id][0].handle(contexts.copy())
            except Exception:
                print_exc()

    def schedule(self, timer: Callable[[], timedelta], once: bool = False):

        def wrapper(func: Callable):
            sub = scope.register(func, temporary=once, publisher=pub)
            if plugin := _current_plugin.get():
                plugin.collect(sub.dispose)
            self.timers[sub.id] = TimerTask(timer, sub.id)
            if _get_running_loop():
                self.timers[sub.id].start(self.queue)
            return sub

        return wrapper

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            for timer in self.timers.values():
                timer.start(self.queue)

        async with self.stage("blocking"):
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            fetch_task = asyncio.create_task(self.fetch())
            done, pending = await any_completed(sigexit_task, fetch_task)
            if sigexit_task in done:
                fetch_task.cancel()

        async with self.stage("cleanup"):
            for timer in self.timers.values():
                timer.cancel()

    id = "entari.scheduler"


scheduler = service = Scheduler()


@RootlessPlugin.apply("scheduler")
def _(plg: RootlessPlugin):
    plg.service(service)


def every_second():
    """每秒执行一次"""
    return lambda: timedelta(seconds=1)


def every_seconds(seconds: int):
    """每 seconds 秒执行一次

    Args:
        seconds (int): 距离下一次执行的时间间隔, 单位为秒
    """
    if seconds > 59 or seconds < 1:
        raise ValueError
    return lambda: timedelta(seconds=seconds)


def every_minute():
    """每分钟执行一次"""
    return lambda: timedelta(minutes=1)


def every_minutes(minutes: int):
    """每 minutes 分钟执行一次

    Args:
        minutes (int): 距离下一次执行的时间间隔, 单位为分
    """
    if minutes > 59 or minutes < 1:
        raise ValueError
    return lambda: timedelta(minutes=minutes)


def every_hour():
    """每小时执行一次"""
    return lambda: timedelta(hours=1)


def every_hours(hours: int):
    """每 hours 小时执行一次

    Args:
        hours (int): 距离下一次执行的时间间隔, 单位为小时
    """
    if hours > 23 or hours < 1:
        raise ValueError
    return lambda: timedelta(hours=hours)


def every_week():
    """每隔一周执行一次"""
    return lambda: timedelta(weeks=1)


def every_weeks(weeks: int):
    """每 weeks 周执行一次

    Args:
        weeks (int): 距离下一次执行的时间间隔, 单位为周
    """
    if weeks > 52 or weeks < 1:
        raise ValueError
    return lambda: timedelta(weeks=weeks)


def every_day():
    """每隔一天执行一次"""
    return lambda: timedelta(days=1)


def every_days(days: int):
    """每 days 天执行一次

    Args:
        days (int): 距离下一次执行的时间间隔, 单位为天
    """
    if days > 31 or days < 1:
        raise ValueError
    return lambda: timedelta(days=days)


def crontab(cron_str: str):
    """根据 cron 表达式执行

    Args:
        cron_str (str): cron 表达式
    """
    try:
        from croniter import croniter
    except ModuleNotFoundError:
        raise ImportError("Please install `croniter` first. Install with `pip install arclet-entari[cron]`") from None

    it = croniter(cron_str, datetime.now())

    return lambda iter=it: iter.get_next(datetime) - datetime.now()


def cron(pattern: str):
    return service.schedule(crontab(pattern))


def every(
    value: int = 1,
    mode: Literal["second", "minute", "hour"] = "second",
):
    _TIMER_MAPPING = {
        "second": every_seconds,
        "minute": every_minutes,
        "hour": every_hours,
    }
    return service.schedule(_TIMER_MAPPING[mode](value))


def invoke(delay: float):
    """延迟执行"""
    return service.schedule(lambda: timedelta(seconds=delay), once=True)
