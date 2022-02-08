from arclet.edoves.builtin.actions import MessageSend, GetMonomer, Union, ChangeStatus, ExecutiveAction
from .monomers import MahEntity


class MuteMember(ChangeStatus):
    def __init__(self, target: MahEntity, mute_time: int = None):
        if target.prime_tag != "Member":
            raise ValueError
        super().__init__(target, "mute", True, mute_time=mute_time)


class UnmuteMember(ChangeStatus):
    def __init__(self, target: MahEntity, mute_time: int = None):
        if target.prime_tag != "Member":
            raise ValueError
        super().__init__(target, "mute", False, mute_time=mute_time)


class GroupMuteAll(ChangeStatus):
    def __init__(self, target: MahEntity, mute_time: int = None):
        if target.prime_tag != "Group":
            raise ValueError
        super().__init__(target, "mute", True, mute_time=mute_time)


class GroupUnmuteAll(ChangeStatus):
    def __init__(self, target: MahEntity, mute_time: int = None):
        if target.prime_tag != "Group":
            raise ValueError
        super().__init__(target, "mute", False, mute_time=mute_time)


class GetFriend(GetMonomer):
    def __init__(self, target: Union[int, str]):
        super().__init__(target, "Friend")


class GetMember(GetMonomer):
    def __init__(self, target: Union[int, str]):
        super().__init__(target, "Member")
        self.rest = {"group": self.target.current_group}


class Reply(MessageSend):
    async def execute(self):
        return await self.target.action(self.action)(
            self.data, reply=True, quote=self.data.id
        )


class NudgeWith(MessageSend):
    async def execute(self):
        return await self.target.action(self.action)(
            self.data, nudge=True
        )


class Nudge(ExecutiveAction):

    def __init__(self):
        super().__init__("nudge")

    async def execute(self):
        return await self.target.action(self.action)(
            self.target.metadata.identifier
        )


send_message = MessageSend
send_nudge = Nudge
nudge_with = NudgeWith
reply = Reply
get_friend = GetFriend
get_member = GetMember
mute_member = MuteMember
unmute_member = UnmuteMember
mute_all = GroupMuteAll
unmute_all = GroupUnmuteAll
