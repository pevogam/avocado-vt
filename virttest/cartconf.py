"""Prefer CartConf, with the local Cartesian configuration parser as fallback."""

import copy
import logging
from typing import Generator

__all__ = ["IS_VARIANTER", "Parser", "ParserError"]

try:
    from cartconf.parser import Parser, ParserError

    IS_VARIANTER = True
except ImportError:
    from .cartesian_config import Parser as LocalParser
    from .cartesian_config import ParserError

    IS_VARIANTER = False

    logging.getLogger("avocado.app").info(
        "Using the local cartesian_config module; "
        "consider installing and trying cartconf instead"
    )

    class Parser(LocalParser):
        """Support eager parameter recipes with the local parser."""

        def __init__(self, *args, **kwargs):
            self._steps = ()
            super().__init__(*args, **kwargs)

        @property
        def steps(self) -> tuple[tuple[str, str], ...]:
            """Return successful parsing inputs in order."""
            return self._steps

        def __copy__(self):
            """Detach the local parser's mutable syntax and traversal state."""
            new = object.__new__(type(self))
            new.__dict__ = copy.deepcopy(self.__dict__)
            return new

        def parse_file(self, filename: str) -> None:
            super().parse_file(filename)
            self._steps += (("file", filename),)

        def parse_string(self, s: str) -> None:
            super().parse_string(s)
            self._steps += (("string", s),)

        def parse_dict(self, params: dict[str, str]) -> None:
            """Parse dictionary entries as parameter assignments.

            :param params: parameter names and values to assign
            """
            content = "".join(f"{key} = {value}\n" for key, value in params.items())
            super().parse_string(content)
            self._steps += (("dict", content),)

        def get_dicts_gen(self) -> Generator[dict[str, str], None, None]:
            """Evaluate a detached parser so traversal cannot modify its source.

            :returns: parameter dictionaries yielded for the configured variants
            """
            yield from copy.copy(self).get_dicts()
