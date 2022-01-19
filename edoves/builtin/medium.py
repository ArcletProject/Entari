from typing import Dict, Union, TYPE_CHECKING
import json as JSON

from ..main.typings import TData
from ..main.medium import BaseMedium

if TYPE_CHECKING:
    from ..main import Monomer


class JsonMedium(BaseMedium):
    content: Dict[str, TData]

    def json_loads(self, json: Union[dict, str]):
        if isinstance(json, str):
            json = JSON.loads(json)
        self.content = json
        return self
