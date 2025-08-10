import asyncio
from asyncio.events import _get_running_loop  # type: ignore
from datetime import datetime, timedelta
from traceback import print_exc
from typing import Callable, Literal

from arclet.letoderea import Scope, Subscriber, make_event
from arclet.letoderea.typing import Contexts
from launart import Launart, Service, any_completed
from launart.status import Phase

from .plugin import RootlessPlugin, get_plugin


@make_event(name="entari.event/internal/schedule")
class _ScheduleEvent:
    pass


scope = Scope.of("entari.scheduler")
contexts: Contexts = {"$event": _ScheduleEvent()}  # type: ignore


class TimerTask:
    def __init__(self, supplier: Callable[[], timedelta], sub: Subscriber):
        self.sub = sub
        self.supplier = supplier
        self.handle = None
        self.available = True

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
        self.tasks: dict[str, TimerTask] = {}

    @property
    def required(self) -> set[str]:
        return set()

    @property
    def stages(self) -> set[Phase]:
        return {"preparing", "blocking", "cleanup"}

    async def fetch(self):
        while True:
            task = await self.queue.get()
            if not task.available:
                del self.tasks[task.sub.id]
                continue
            task.start(self.queue)
            if task.sub.available:
                try:
                    await task.sub.handle(contexts.copy())
                except Exception:
                    print_exc()

    def schedule(self, time_fn: Callable[[], timedelta], once: bool = False):
        """
        设置一个定时任务

        Args:
            time_fn: 用于提供定时间隔的函数
            once: 是否只执行一次
        """

        def wrapper(func: Callable):
            plg = get_plugin(1, optional=True)
            if plg:
                sub = plg.dispatch(_ScheduleEvent).handle(func, once=once)
            else:
                sub = scope.register(func, _ScheduleEvent, once=once)
            task = self.tasks[sub.id] = TimerTask(time_fn, sub)

            def _dispose(_):
                task.available = False

            sub._attach_disposes(_dispose)

            if _get_running_loop():
                self.tasks[sub.id].start(self.queue)
            return sub

        return wrapper

    async def launch(self, manager: Launart):
        async with self.stage("preparing"):
            for task in self.tasks.values():
                task.start(self.queue)

        async with self.stage("blocking"):
            sigexit_task = asyncio.create_task(manager.status.wait_for_sigexit())
            fetch_task = asyncio.create_task(self.fetch())
            done, pending = await any_completed(sigexit_task, fetch_task)
            if sigexit_task in done:
                fetch_task.cancel()

        async with self.stage("cleanup"):
            for task in self.tasks.values():
                task.cancel()

    id = "entari.scheduler"


scheduler = service = Scheduler()
schedule = scheduler.schedule


@RootlessPlugin.apply("scheduler", default=True)
def _(plg: RootlessPlugin):
    plg.service(service)


class timer:
    @staticmethod
    def every_second():
        """每秒执行一次"""
        return lambda: timedelta(seconds=1)

    @staticmethod
    def every_seconds(seconds: int):
        """每 seconds 秒执行一次

        Args:
            seconds (int): 距离下一次执行的时间间隔, 单位为秒
        """
        if seconds > 59 or seconds < 1:
            raise ValueError
        return lambda: timedelta(seconds=seconds)

    @staticmethod
    def every_minute():
        """每分钟执行一次"""
        return lambda: timedelta(minutes=1)

    @staticmethod
    def every_minutes(minutes: int):
        """每 minutes 分钟执行一次

        Args:
            minutes (int): 距离下一次执行的时间间隔, 单位为分
        """
        if minutes > 59 or minutes < 1:
            raise ValueError
        return lambda: timedelta(minutes=minutes)

    @staticmethod
    def every_hour():
        """每小时执行一次"""
        return lambda: timedelta(hours=1)

    @staticmethod
    def every_hours(hours: int):
        """每 hours 小时执行一次

        Args:
            hours (int): 距离下一次执行的时间间隔, 单位为小时
        """
        if hours > 23 or hours < 1:
            raise ValueError
        return lambda: timedelta(hours=hours)

    @staticmethod
    def every_week():
        """每隔一周执行一次"""
        return lambda: timedelta(weeks=1)

    @staticmethod
    def every_weeks(weeks: int):
        """每 weeks 周执行一次

        Args:
            weeks (int): 距离下一次执行的时间间隔, 单位为周
        """
        if weeks > 52 or weeks < 1:
            raise ValueError
        return lambda: timedelta(weeks=weeks)

    @staticmethod
    def every_day():
        """每隔一天执行一次"""
        return lambda: timedelta(days=1)

    @staticmethod
    def every_days(days: int):
        """每 days 天执行一次

        Args:
            days (int): 距离下一次执行的时间间隔, 单位为天
        """
        if days > 31 or days < 1:
            raise ValueError
        return lambda: timedelta(days=days)

    @staticmethod
    def crontab(cron_str: str):
        """根据 cron 表达式执行

        Args:
            cron_str (str): cron 表达式
        """
        try:
            from croniter import croniter
        except ModuleNotFoundError:
            raise ImportError(
                "Please install `croniter` first. Install with `pip install arclet-entari[cron]`"
            ) from None

        it = croniter(cron_str, datetime.now(), datetime)

        return lambda iter=it: iter.get_next(datetime) - datetime.now()


def cron(pattern: str):
    """使用 cron 表达式设置一个定时任务"""
    return service.schedule(timer.crontab(pattern))


def every(value: int = 1, mode: Literal["second", "minute", "hour"] = "second"):
    """依据 mode 设置一个定时任务"""
    _TIMER_MAPPING = {
        "second": timer.every_seconds,
        "minute": timer.every_minutes,
        "hour": timer.every_hours,
    }
    return service.schedule(_TIMER_MAPPING[mode](value))


def invoke(delay: float):
    """延迟 delay 秒执行"""
    return service.schedule(lambda: timedelta(seconds=delay), once=True)


__all__ = ["scheduler", "schedule", "timer", "cron", "every", "invoke"]
