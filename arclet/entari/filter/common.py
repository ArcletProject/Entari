from ..session import Session


def user(*ids: str):
    async def check_user(session: Session):
        return (session.user.id in ids) if ids else True

    return check_user


def channel(*ids: str):
    async def check_channel(session: Session):
        return (session.channel.id in ids) if ids else True

    return check_channel


def guild(*ids: str):
    async def check_guild(session: Session):
        return (session.guild.id in ids) if ids else True

    return check_guild


def account(*ids: str):
    async def check_account(session: Session):
        return (session.account.self_id in ids) if ids else True

    return check_account


def platform(*ids: str):
    async def check_platform(session: Session):
        return (session.account.platform in ids) if ids else True

    return check_platform
