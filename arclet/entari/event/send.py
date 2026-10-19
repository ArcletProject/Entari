from warnings import warn

warn(
    "arclet.entari.event.send is deprecated, please use arclet.entari.event.api instead",
    DeprecationWarning,
    stacklevel=2,
)

from .api import SendRequest as SendRequest  # noqa: F401
from .api import SendResponse as SendResponse  # noqa: F401
