"""Prefer CartConf, with the local Cartesian configuration parser as fallback."""

import logging

__all__ = ["Parser", "ParserError"]

try:
    from cartconf.parser import Parser, ParserError
except ImportError:
    from .cartesian_config import Parser, ParserError

    logging.getLogger("avocado.app").info(
        "Using the local cartesian_config module; "
        "consider installing and trying cartconf instead"
    )
