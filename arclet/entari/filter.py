from typing import Optional

from arclet.letoderea import Interface, JudgeAuxiliary, Scope
from satori import Channel, ChannelType, Guild, User
from satori.client import Account


class UserFilter(JudgeAuxiliary):
    def __init__(self, *user_ids: str):
        self.user_ids = set(user_ids)
        super().__init__()

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (user := await interface.query(User, "user", force_return=True)):
            return False
        return user.id in self.user_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/user"


class GuildFilter(JudgeAuxiliary):
    def __init__(self, *guild_ids: str):
        self.guild_ids = set(guild_ids)
        super().__init__()

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (guild := await interface.query(Guild, "guild", force_return=True)):
            return False
        return guild.id in self.guild_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/guild"


class ChannelFilter(JudgeAuxiliary):
    def __init__(self, *channel_ids: str):
        self.channel_ids = set(channel_ids)
        super().__init__()

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.id in self.channel_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/channel"


class SelfFilter(JudgeAuxiliary):
    def __init__(self, *self_ids: str):
        self.self_ids = set(self_ids)
        super().__init__()

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (account := await interface.query(Account, "account", force_return=True)):
            return False
        return account.self_id in self.self_ids

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/self"


class PlatformFilter(JudgeAuxiliary):
    def __init__(self, *platforms: str):
        self.platforms = set(platforms)
        super().__init__()

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (account := await interface.query(Account, "account", force_return=True)):
            return False
        return account.platform in self.platforms

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/platform"


class DirectMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type == ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/direct_message"


direct_message = DirectMessageJudger()


class PublicMessageJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        if not (channel := await interface.query(Channel, "channel", force_return=True)):
            return False
        return channel.type != ChannelType.DIRECT

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/public_message"


public_message = PublicMessageJudger()


class ReplyMeJudger(JudgeAuxiliary):

    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return interface.ctx.get("is_reply_me", False)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/judge_reply_me"


reply_me = ReplyMeJudger()


class NoticeMeJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        return interface.ctx.get("is_notice_me", False)

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/judge_notice_me"


notice_me = NoticeMeJudger()


class ToMeJudger(JudgeAuxiliary):
    async def __call__(self, scope: Scope, interface: Interface) -> Optional[bool]:
        is_reply_me = interface.ctx.get("is_reply_me", False)
        is_notice_me = interface.ctx.get("is_notice_me", False)
        return is_reply_me or is_notice_me

    @property
    def scopes(self) -> set[Scope]:
        return {Scope.prepare}

    @property
    def id(self) -> str:
        return "entari.filter/judge_to_me"


to_me = ToMeJudger()
