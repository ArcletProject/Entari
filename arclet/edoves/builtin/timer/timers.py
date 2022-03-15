import time
from datetime import datetime, timedelta


def every_second():
    """每秒执行一次
    """
    return lambda: timedelta(seconds=1)


def every_custom_seconds(seconds: int):
    """每 seconds 秒执行一次

    Args:
        seconds (int): 距离下一次执行的时间间隔, 单位为秒
    """
    if seconds > 59 or seconds < 1:
        raise ValueError
    return lambda: timedelta(seconds=seconds)


def every_minute():
    """每分钟执行一次
    """
    return lambda: timedelta(minutes=1)


def every_custom_minutes(minutes: int):
    """每 minutes 分钟执行一次

    Args:
        minutes (int): 距离下一次执行的时间间隔, 单位为分
    """
    if minutes > 59 or minutes < 1:
        raise ValueError
    return lambda: timedelta(minutes=minutes)


def every_hour():
    """每小时执行一次
    """
    return lambda: timedelta(hours=1)


def every_custom_hours(hours: int):
    """每 hours 小时执行一次

    Args:
        hours (int): 距离下一次执行的时间间隔, 单位为小时
    """
    if hours > 23 or hours < 1:
        raise ValueError
    return lambda: timedelta(hours=hours)


def every_week():
    """每隔一周执行一次
    """
    return lambda: timedelta(weeks=1)


def every_custom_weeks(weeks: int):
    """每 weeks 周执行一次

    Args:
        weeks (int): 距离下一次执行的时间间隔, 单位为周
    """
    if weeks > 52 or weeks < 1:
        raise ValueError
    return lambda: timedelta(weeks=weeks)


def every_day():
    """每隔一天执行一次
    """
    return lambda: timedelta(days=1)


def every_custom_days(days: int):
    """每 days 天执行一次

    Args:
        days (int): 距离下一次执行的时间间隔, 单位为天
    """
    if days > 31 or days < 1:
        raise ValueError
    return lambda: timedelta(days=days)


def set_special_day(
        month: int,
        day: int,
        hour: int = 0,
        minute: int = 0,
        second: int = 0
):
    interval = {'month': month, 'day': day, 'hour': hour, 'minute': minute, 'second': second}
    now = datetime.now()
    year = now.year
    if interval['month'] < now.month:
        year += 1
    return lambda: datetime(year=year, **interval) - now


if __name__ == '__main__':
    def route_time(timer):
        import time
        now = datetime.now()
        year = now.year
        month = now.month
        day = now.day
        hour = now.hour
        minute = now.minute
        second = now.second
        _interval = timer()
        if _interval.seconds < 60:
            if _interval.seconds - second < 0:
                minute += 1
            second = _interval.seconds + 60
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
        return datetime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)
    while True:
        time.sleep(0.5)
        print(route_time(every_second()))