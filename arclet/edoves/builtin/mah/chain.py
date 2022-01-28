from .messages import *
from ...message.chain import MessageChain

Quote.update_forward_refs(MessageChain=MessageChain)
ForwardNode.update_forward_refs(MessageChain=MessageChain)
