from typing import Dict, cast

from arclet.edoves.builtin.medium import DictMedium, Message, Notice
from arclet.edoves.main.parser import BaseDataParser, ParserBehavior, ParserMetadata
from ..protocol import MAHProtocol
from ..chain import MessageChain


class NudgeOperateMeta(ParserMetadata):
    parser_targets = "NudgeSend", "NudgeEvent"


class MessageActionMeta(ParserMetadata):
    parser_targets = (
        "MessageSend",
        "MessageGet",
        "MessageRevoke",
        "FriendMessage",
        "GroupMessage",
        "TempMessage",
        "StrangerMessage",
        "GroupRecallEvent",
        "FriendRecallEvent",
    )


class NudgeParserBehavior(ParserBehavior):
    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        operator_id = str(data.content.pop('fromId'))
        target_id = str(data.content.pop('target'))
        operator = protocol.current_scene.monomer_map.get(f"{operator_id}@{protocol.identifier}")
        subject = data.content.pop('subject')
        if subject['kind'] == "Group":
            if not operator or not getattr(operator.metadata, "group_id", None):
                resp = await protocol.screen.push_medium(
                    DictMedium().create(
                        protocol.current_scene.protagonist,
                        {
                            "relationship": "Member",
                            "target": operator_id,
                            "rest": {"group": subject['id']},
                        },
                        "RelationshipGet"
                    )
                )
                await self.to_docker(protocol, await protocol.screen.get_medium())
                operator = await resp.wait_response()
            else:
                operator.set_prime_tag("Member")
        elif subject['kind'] == "Friend":
            if not operator:
                resp = await protocol.screen.push_medium(
                    DictMedium().create(
                        protocol.current_scene.protagonist,
                        {
                            "relationship": "Friend",
                            "target": operator_id,
                            "rest": {"detail": True},
                        },
                        "RelationshipGet"
                    )
                )
                await self.to_docker(protocol, await protocol.screen.get_medium())
                operator = await resp.wait_response()
            else:
                operator.set_prime_tag("Friend")
        target = protocol.current_scene.monomer_map.get(f"{target_id}@{protocol.identifier}") or target_id
        notice = Notice().create(operator, {**data.content, "target": target}, self.io.metadata.select_type)
        await protocol.screen.push_medium(notice)
        await protocol.screen.broadcast_medium("NoticeMe")

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        rest = data.content.get('rest')
        source_type = rest.get('type')
        subject = target = data.content.get("target")
        sender = protocol.current_scene.monomer_map.get(f"{target}@{protocol.identifier}")
        kind = sender.prime_tag
        if source_type:
            if source_type.startswith("Friend") and sender.compare("Friend"):
                kind = "Friend"
            elif source_type.startswith("Group") and sender.compare("Member"):
                if sender.parents:
                    subject = sender.metadata.group_id
                    kind = "Group"
        else:
            if sender.prime_tag == "Member":
                if sender.parents:
                    subject = sender.metadata.group_id
                    kind = "Group"
        await protocol.docker.behavior.session_handle(
            "post",
            "sendNudge",
            {
                "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                "target": target,
                "subject": subject,
                "kind": kind
            }
        )
        protocol.screen.edoves.logger.info(
            f"{protocol.current_scene.protagonist.metadata.pure_id}: "
            f"{kind}({target}) <- Nudge"
        )


class MessageActionParserBehavior(ParserBehavior):

    async def to_docker(self, protocol: MAHProtocol, data: DictMedium):
        action = data.type
        target = data.content.get("target")
        if action.endswith("Send"):
            sender = protocol.current_scene.monomer_map.get(f"{target}@{protocol.identifier}")
            rest = data.content.get('rest')
            source_type = rest.get('type')
            if source_type:
                if source_type.startswith("Friend") and sender.compare("Friend"):
                    action = "sendFriendMessage"
                elif source_type.startswith("Group") and sender.compare("Member"):
                    if sender.parents:
                        target = sender.metadata.group_id
                        action = "sendGroupMessage"
            else:
                if sender.prime_tag == "Member":
                    if sender.parents:
                        target = sender.metadata.group_id
                        action = "sendGroupMessage"
                elif sender.prime_tag == "Group":
                    action = "sendGroupMessage"
                elif sender.prime_tag == "Friend":
                    action = "sendFriendMessage"
            message = cast(MessageChain, data.content.get("content")).replace_type("Text", "Plain")
            resp: Dict = await protocol.docker.behavior.session_handle(
                "post",
                action,
                {
                    "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                    "target": target,
                    "messageChain": message.dict()["__root__"],
                    **(
                        {"quote": rest.get("quote")} if data.content.get("reply") else {}
                    )
                }
            )
            resp['id'] = target
            data.send_response(DictMedium().create(sender, resp, action.replace('send', '').replace('Message', '')))
        elif action.endswith("Revoke"):
            await protocol.docker.behavior.session_handle(
                "post",
                "recall",
                {
                    "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                    "target": target,
                }
            )
        elif action.endswith("Get"):
            message = await protocol.docker.behavior.session_handle(
                "get",
                "messageFromId",
                {
                    "sessionKey": protocol.docker.metadata.session_keys[protocol.current_scene.scene_name],
                    "id": target
                }
            )
            data.send_response(message)

    async def from_docker(self, protocol: MAHProtocol, data: DictMedium):
        ev_type: str = self.io.metadata.select_type
        sender_data: Dict = data.content.get("sender")
        if ev_type.endswith("Message"):
            if ev_type.startswith("Friend"):
                sender = protocol.include_monomer("friend", sender_data)
            elif ev_type.startswith("Group") or ev_type.startswith("Temp"):
                sender = protocol.include_monomer("member", sender_data)
                group = protocol.include_monomer("group", sender_data.get("group"))
                if not group.get_child(sender.metadata.pure_id):
                    group.set_child(sender)
                sender.metadata.group_id = group.metadata.pure_id
            else:
                sender = protocol.include_temporary_monomer(sender_data.get("nickname"), str(sender_data.get('id')))
            msg = Message().create(
                sender, MessageChain.parse_obj(data.content.get("messageChain")), ev_type
            )
            msg.id = str(msg.content.find("Source").id)
            msg.time = msg.content.find("Source").time
            msg.content.remove("Source")
            await protocol.screen.push_medium(msg)
            await protocol.screen.broadcast_medium("MessageReceived")
        elif ev_type.endswith("RecallEvent"):
            call = await protocol.screen.push_medium(
                DictMedium().create(
                    protocol.current_scene.protagonist,
                    {
                        "target": data.content.pop('messageId'),
                    },
                    "MessageGet"
                )
            )
            await self.to_docker(protocol, await protocol.screen.get_medium())
            message = await call.wait_response()
            if ev_type.startswith("Friend"):
                resp = await protocol.screen.push_medium(
                    DictMedium().create(
                        protocol.current_scene.protagonist,
                        {
                            "relationship": "Friend",
                            "target": data.content.pop('operator'),
                            "rest": {"detail": True},
                        },
                        "RelationshipGet"
                    )
                )
                await self.to_docker(protocol, await protocol.screen.get_medium())
                operator = await resp.wait_response()
            else:
                group_data = data.content.pop('group')
                group = protocol.include_monomer("group", group_data)
                operator_data = data.content.pop('operator')
                operator = protocol.include_monomer("member", operator_data)
                if not group.get_child(operator.metadata.pure_id):
                    group.set_child(operator)
                operator.metadata.group_id = group.metadata.pure_id
            msg = Message().create(operator, MessageChain.parse_obj(message['messageChain']), ev_type)
            msg.id = str(msg.content.find("Source").id)
            msg.time = msg.content.find("Source").time
            msg.content.remove("Source")
            await protocol.screen.push_medium(msg)
            await protocol.screen.broadcast_medium("MessageRevoked")


@MAHProtocol.register_parser
class NudgeEventParser(BaseDataParser):
    prefab_metadata = NudgeOperateMeta
    prefab_behavior = NudgeParserBehavior


@MAHProtocol.register_parser
class MessageEventParser(BaseDataParser):
    prefab_metadata = MessageActionMeta
    prefab_behavior = MessageActionParserBehavior
