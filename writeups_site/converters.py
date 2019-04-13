import re
from typing import Tuple, Union

from starlette.convertors import Convertor, CONVERTOR_TYPES


class FileConverter(Convertor):
    regex = r"([^/]+)\.([^/]+)"

    _compiled_regex = re.compile(f"^{regex}$")

    def convert(self, value: str) -> Tuple[str, str]:
        r = self._compiled_regex.match(value)

        assert r, "Path like param required"

        return (r.group(1), r.group(2))


    def to_string(self, value: Union[str, Tuple[str, str]]) -> str:
        assert isinstance(value, (tuple, str)), "Must be a tuple or integer"

        if isinstance(value, tuple):
            return f"{value[0]}.{value[1]}"

        if isinstance(value, str):
            return value


def inject():
    CONVERTOR_TYPES["file"] = FileConverter()
