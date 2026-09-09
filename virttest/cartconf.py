"""Prefer CartConf, with the local Cartesian configuration parser as fallback."""

import copy
import logging

from .cartesian_config import Parser as PythonParser

__all__ = ["IS_VARIANTER", "Parser", "ParserError", "copy_parser"]

try:
    from cartconf.parser import Parser, ParserError

    IS_VARIANTER = True
except ImportError:
    from .cartesian_config import ParserError

    IS_VARIANTER = False
    Parser = PythonParser

    IS_VARIANTER = False

    logging.getLogger("avocado.app").info(
        "Using the local cartesian_config module; "
        "consider installing and trying cartconf instead"
    )


def copy_parser(parser: Parser) -> Parser:
    """Share CartConf's immutable AST, but isolate the mutable Python fallback.

    :param parser: parser whose current configuration will be reused
    :returns: independent parser sharing only immutable syntax
    """
    if isinstance(parser, PythonParser):
        return copy.deepcopy(parser)
    return copy.copy(parser)
