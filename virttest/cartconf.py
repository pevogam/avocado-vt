"""CartConf integration and parameter conversion for VT."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from typing import Generator

from cartconf.parser import Parser as BaseParser
from cartconf.parser import ParserError

from .utils_params import Params, print_dicts

__all__ = ["Parser", "ParserError", "EmptyCartesianProduct"]


class EmptyCartesianProduct(Exception):
    """Empty Cartesian product of variants."""

    def __init__(self, message: str) -> None:
        super().__init__(
            "Check for self-excluding variants in your current configuration:\n"
            "Empty Cartesian product of parameters!\n" + message
        )


class Parser(BaseParser):
    """Add VT parameter objects and empty-product errors to the parser API."""

    def __str__(self) -> str:
        report = "Parsing parameters with the following configuration:\n"
        labels = {"dict": "dictionary", "str": "string", "file": "file"}
        for kind, content in self.steps:
            content = content.rstrip("\n").replace("\n", "\n\t\t")
            report += f"\tParsed {labels[kind]}:\n\t\t{content}\n"
        return report

    def iter_params(self) -> Generator[dict[str, str], None, None]:
        """Yield dictionaries, rejecting an empty Cartesian product.

        :returns: parameter dictionary generator for the configured variants
        :raises EmptyCartesianProduct: if no variant exists
        """
        dictionaries = self.get_dicts_gen()
        try:
            first = next(dictionaries)
        except StopIteration:
            raise EmptyCartesianProduct(str(self)) from None
        yield first
        yield from dictionaries

    def get_params(self, dict_index: int = 0, verbose: bool = False) -> Params:
        """Select a VT parameter dictionary, optionally printing all variants.

        :param dict_index: index of the dictionary to select
        :param verbose: whether to log inputs and print all variant names
        :returns: selected VT parameter dictionary
        :raises EmptyCartesianProduct: if no variant exists
        :raises ValueError: if the requested dictionary index does not exist
        """
        dictionaries = self.iter_params()
        if verbose:
            logging.debug(self)
            dictionaries = list(dictionaries)
            print_dicts(
                SimpleNamespace(repr_mode=False, fullname=False, contents=False),
                dictionaries,
            )
        for index, parameters in enumerate(dictionaries):
            if index == dict_index:
                return Params(parameters)
        raise ValueError(f"There must be a configuration for the restriction:\n{self}")
