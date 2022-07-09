from .elements import *
from arclet.edoves.builtin.message.chain import MessageChain

Quote.update_forward_refs(MessageChain=MessageChain)
ForwardNode.update_forward_refs(MessageChain=MessageChain)
