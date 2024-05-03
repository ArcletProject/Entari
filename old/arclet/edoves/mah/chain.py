from arclet.edoves.builtin.message.chain import MessageChain

from .elements import *

Quote.update_forward_refs(MessageChain=MessageChain)
ForwardNode.update_forward_refs(MessageChain=MessageChain)
