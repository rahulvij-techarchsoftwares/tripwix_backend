from typing import Dict, List, Union

from typing_extensions import TypeAlias

JSON: TypeAlias = Union[Dict[str, "JSON"], List["JSON"], str, int, float, bool, None]
