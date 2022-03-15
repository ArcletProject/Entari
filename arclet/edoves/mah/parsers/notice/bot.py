from typing import cast

from arclet.edoves.builtin.medium import DictMedium
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from arclet.edoves.main.utilles import IOStatus
from ...monomers import MahEntity
from ...protocol import MAHProtocol


class BotBaseNoticeMeta(ParserMetadata):
    parser_targets = [
        "BotOnlineEvent",
        "BotOfflineEventActive",
        "BotOfflineEventForce",
        "BotOfflineEventDropped",
        "BotReloginEvent"
    ]


class BotStatusMeta(ParserMetadata):
    parser_targets = [
        "BotGroupPermissionChangeEvent",
        "BotMuteEvent",
        "BotUnmuteEvent"
    ]


class BotRelationshipMeta(ParserMetadata):
    parser_targets = [
        "BotJoinGroupEvent",
        "BotLeaveEventActive",
        "BotLeaveEventKick",
        "RelationshipRemove"

    ]


class BotNoticeMeBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        await protocol.post_notice(
            "NoticeMe",
            cast(MahEntity, protocol.scene.protagonist),
            self.io.metadata.select_type,
            {}
        )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        pass


class BotStatusUpdateBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        ev_type = self.io.metadata.select_type
        if ev_type == "BotGroupPermissionChangeEvent":
            group = protocol.include_group(data.content.pop('group'))
            protocol.scene.protagonist.metadata.update_data("group_id", group.metadata.pure_id)
            await protocol.post_notice(
                "MonomerStatusUpdate",
                cast(MahEntity, protocol.scene.protagonist),
                ev_type,
                data.content
            )
        elif ev_type in ("BotMuteEvent", "BotUnmuteEvent"):
            operator_data = data.content.pop('operator')
            operator = protocol.include_member(operator_data)
            group = protocol.include_group(operator_data['group'])
            if not group.get_child(operator.metadata.pure_id):
                group.set_child(operator)
            operator.metadata.update_data("group_id", group.metadata.pure_id)
            await protocol.post_notice(
                "MonomerStatusUpdate",
                cast(MahEntity, protocol.scene.protagonist),
                ev_type,
                data.content,
                operator=operator,
                action="set" + ev_type.replace('Bot', '').replace('Event', '')
            )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        pass


class BotRelationshipOperateBehavior(ParserBehavior):

    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        ev_type = self.io.metadata.select_type
        if ev_type == "BotJoinGroupEvent":
            group = protocol.include_group(data.content.pop('group'))
            protocol.scene.protagonist.metadata.update_data("group_id", group.metadata.pure_id)
            await protocol.post_notice(
                "RelationshipSetup",
                cast(MahEntity, protocol.scene.protagonist),
                ev_type,
                data.content,
                relationship="Group"
            )
        elif ev_type == "BotLeaveEventActive":
            group = protocol.exclude_group(data.content.pop('group'))
            await protocol.post_notice(
                "RelationshipTerminate",
                cast(MahEntity, protocol.scene.protagonist),
                ev_type,
                {"group": group},
                relationship="Group"
            )
        elif ev_type == "BotLeaveEventKick":
            group = protocol.exclude_group(data.content.pop('group'))
            operator = protocol.exclude_member(data.content.pop('operator'), group.metadata.pure_id)
            operator.metadata.update_data("group_id", group.metadata.pure_id)
            await protocol.post_notice(
                "RelationshipSevered",
                cast(MahEntity, protocol.scene.protagonist),
                ev_type,
                {"group": group},
                operator=operator,
                relationship="Group"
            )

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        target = cast(MahEntity, data.content.get("target"))
        relationship = data.content.get("relationship")
        if relationship == "Friend":
            # 删除好友
            protocol.scene.protagonist.relation['children'].remove(target.metadata.identifier)
            if not target.compare("Member"):
                # 解除所有关系
                protocol.scene.monomers.remove(target.metadata.pure_id)
                target.metadata.state = IOStatus.DELETE_WAIT
            else:
                target.remove_tags("Friend")  # 删除好友标签
            await protocol.docker.behavior.session_handle(
                "post",
                "deletaFriend",
                {
                    "sessionKey": protocol.docker.metadata.session_key,
                    "target": target.metadata.identifier,
                }
            )
        if relationship == "Group":
            protocol.scene.protagonist.parents.pop(target.metadata.identifier)  # 群组与bot的关系解除
            for mo in target.children.values():
                mo.parents.pop(target.metadata.identifier)  # 群组与群组成员的关系解除
                if len(mo.parents) == 0:
                    protocol.scene.monomers.pop(mo.metadata.identifier)  # 群组成员与bot的所有关系解除
                elif mo.compare("Friend") and len(mo.parents) == 1:
                    mo.remove_tags("Member")  # 群组成员与bot的群友关系解除

            await protocol.docker.behavior.session_handle(
                "post",
                "quit",
                {
                    "sessionKey": protocol.docker.metadata.session_key,
                    "target": target.metadata.identifier,
                }
            )


@MAHProtocol.register_parser
class BotBaseEventParser(BaseDataParser):
    prefab_metadata = BotBaseNoticeMeta
    prefab_behavior = BotNoticeMeBehavior


@MAHProtocol.register_parser
class BotStatusUpdateEventParser(BaseDataParser):
    prefab_metadata = BotStatusMeta
    prefab_behavior = BotStatusUpdateBehavior


@MAHProtocol.register_parser
class BotRelationshipEventParser(BaseDataParser):
    prefab_metadata = BotBaseNoticeMeta
    prefab_behavior = BotRelationshipOperateBehavior
