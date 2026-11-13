# pylint: disable=consider-using-f-string,differing-param-doc,docstring-first-line-empty,import-error,logging-fstring-interpolation,missing-param-doc,missing-raises-doc,missing-return-doc,no-self-use,redefined-outer-name,redundant-returns-doc,too-many-arguments,too-many-positional-arguments,unnecessary-dunder-call,unspecified-encoding,use-implicit-booleaness-not-comparison-to-string,wrong-import-order
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
#
# See LICENSE for more details.
#
# Copyright 2013-2026 Intranet AG and contributors
# Author: Plamen Dimitrov <plamen.dimitrov@intra2net.com>

"""
Module for handling all Cartesian config parsing and making it reusable and maximally performant.

SUMMARY
------------------------------------------------------

Copyright: Intra2net AG

INTERFACE
------------------------------------------------------

"""

import collections
import logging
import os
from typing import Generator

from avocado.core.settings import settings

from virttest.cartconf import Parser
from virttest.cartesian_config import print_dicts
from virttest.utils_params import Params

log = logging.getLogger("avocado.job." + __name__)


class EmptyCartesianProduct(Exception):
    """Empty Cartesian product of variants."""

    def __init__(self, message: str) -> None:
        """
        Initialize an empty Cartesian product exception.

        :param message: additional message about the exception
        """
        message = "Empty Cartesian product of parameters!\n" + message
        message = (
            "Check for self-excluding variants in your current configuration:\n"
            + message
        )
        super().__init__(message)


###################################################################
# preprocessing
###################################################################


_devel_tp_folder = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "tp_multivm")
)
settings.register_option(
    section="vt.common",
    key="suite_path",
    key_type=str,
    default=_devel_tp_folder,
    help_msg="Path to the test suite containing Cartesian variants and test scripts.",
)


def custom_configs_dir() -> str:
    """Get custom directory for all config files."""
    suite_path = settings.as_dict().get("vt.common.suite_path")
    return os.path.join(suite_path, "configs")


def tests_ovrwrt_file() -> str:
    """Get overwrite file for all tests (nodes)."""
    ovrwrt_file = os.path.join(os.environ["HOME"], "avocado_overwrite_tests.cfg")
    if not os.path.exists(ovrwrt_file):
        logging.warning(
            "Generating a file to use for overwriting the original test parameters"
        )
        with open(ovrwrt_file, "w") as handle:
            handle.write(
                "# Use this config to override with test nodes configuration\n"
                "include "
                + os.path.join(custom_configs_dir(), "sets-overwrite.cfg")
                + "\n"
            )
    return ovrwrt_file


def vms_ovrwrt_file() -> str:
    """Get overwrite file for all vms (a category of objects)."""
    ovrwrt_file = os.path.join(os.environ["HOME"], "avocado_overwrite_vms.cfg")
    if not os.path.exists(ovrwrt_file):
        logging.warning(
            "Generating a file to use for overwriting the original vm parameters"
        )
        with open(ovrwrt_file, "w") as handle:
            handle.write(
                "# Use this config to override with test objects configuration\n"
                "include "
                + os.path.join(custom_configs_dir(), "objects-overwrite.cfg")
                + "\n"
            )
    return ovrwrt_file


def ovrwrt_file(category: str) -> str:
    """Get overwrite file for all objects."""
    ovrwrt_file = os.path.join(os.environ["HOME"], f"avocado_overwrite_{category}.cfg")
    if not os.path.exists(ovrwrt_file):
        logging.warning(
            f"Generating a file to use for overwriting the original {category} parameters"
        )
        with open(ovrwrt_file, "w") as handle:
            handle.write(
                "# Use this config to override with test objects configuration\n"
                "include "
                + os.path.join(custom_configs_dir(), f"{category}-overwrite.cfg")
                + "\n"
            )
    return ovrwrt_file


###################################################################
# main parameter parsing methods
###################################################################


def get_parser() -> Parser:
    """Create a parser with the host and test suite defaults."""
    parser = Parser()
    parser.parse_string(
        "hostname = %s\n"
        % os.environ.get("PREFIX", os.environ.get("HOSTNAME", "avocado"))
    )
    suite_path = settings.as_dict().get("vt.common.suite_path")
    parser.parse_string("suite_path = %s\n" % suite_path)
    parser.parse_string(
        "test_pre_hook = %s\n"
        % os.path.join(suite_path, "controls", "pre_test.control")
    )
    return parser


def report_parser(parser: Parser) -> str:
    """Describe the parser's recorded file, string and dictionary inputs."""
    restriction = "Parsing parameters with the following configuration:\n"
    labels = {"file": "file", "string": "string", "dict": "dictionary"}
    for kind, content in parser.steps:
        content = content.rstrip("\n").replace("\n", "\n\t\t")
        restriction += "\tParsed %s:\n\t\t%s\n" % (labels[kind], content)
    return restriction


def parse_batch(
    parser: Parser,
    base_file: str = None,
    base_str: str | None = "",
    base_dict: dict[str, str] = None,
    ovrwrt_file: str = None,
    ovrwrt_str: str | None = "",
    ovrwrt_dict: dict[str, str] = None,
) -> None:
    """
    Parse a batch of base file, string, and dictionary.

    Possibly also parse a batch of an overwrite file (with custom parameters
    at the user's home location).

    :param parser: parser to extend
    :param base_file: file to be parsed first
    :param base_str: string to be parsed first
    :param base_dict: params to be added first
    :param ovrwrt_file: file to be parsed last
    :param ovrwrt_str: string to be parsed last
    :param ovrwrt_dict: params to be added last

    The priority of the setting follows the order of the arguments:
    Dictionary with some parameters is topmost, string with some
    parameters is next and the file with parameters is taken as a base.
    The overwriting version is taken last, the base version first.
    """
    if base_file:
        parser.parse_file(os.path.join(custom_configs_dir(), base_file))
    if base_str:
        parser.parse_string(base_str)
    if base_dict:
        parser.parse_dict(base_dict)
    if ovrwrt_file:
        parser.parse_file(os.path.join(custom_configs_dir(), ovrwrt_file))
    if ovrwrt_str:
        parser.parse_string(ovrwrt_str)
    if ovrwrt_dict:
        parser.parse_dict(ovrwrt_dict)


def get_dicts(parser: Parser) -> Generator[dict[str, str], None, None]:
    """
    Yield parameters, raising EmptyCartesianProduct if no variant exists.

    :param parser: parser to evaluate
    :returns: parameter dictionaries yielded for the configured variants
    :raises EmptyCartesianProduct: if no variant exists
    """
    dictionaries = parser.get_dicts_gen()
    try:
        first = next(dictionaries)
    except StopIteration:
        raise EmptyCartesianProduct(report_parser(parser)) from None
    yield first
    yield from dictionaries


def get_params(
    parser: Parser,
    list_of_keys: list[str] = None,
    dict_index: int = 0,
    show_restriction: bool = False,
    show_dictionaries: bool = False,
    show_dict_fullname: bool = False,
    show_dict_contents: bool = False,
) -> Params:
    """
    Select a parameter dictionary from the current parser snapshot.

    :param parser: parser to evaluate
    :param list_of_keys: parameter keys to retain, or all keys if omitted
    :param dict_index: index of the dictionary to select
    :param show_restriction: whether to log the parsing inputs
    :param show_dictionaries: whether to print all resulting variants
    :param show_dict_fullname: whether to print full variant names
    :param show_dict_contents: whether to print the variant parameters
    :returns: selected parameters
    :raises: EmptyCartesianProduct if no variant exists
    :raises: ValueError if the requested dictionary index does not exist
    """
    if show_restriction:
        logging.debug(report_parser(parser))
    if show_dictionaries:
        options = collections.namedtuple(
            "options", ["repr_mode", "fullname", "contents"]
        )
        dictionaries = get_dicts(parser)
        print_dicts(
            options(False, show_dict_fullname, show_dict_contents),
            (next(dictionaries),),
        )
        print_dicts(
            options(False, show_dict_fullname, show_dict_contents), dictionaries
        )

    for i, default_params in enumerate(get_dicts(parser)):
        if i == dict_index:
            break
    else:
        raise ValueError(
            f"There must be a configuration for the restriction:\n{report_parser(parser)}"
        )

    if list_of_keys is None:
        selected_params = default_params
    else:
        selected_params = {key: default_params[key] for key in list_of_keys}
    return Params(selected_params)


###################################################################
# overwrite string and overwrite dictionary automation methods
###################################################################


def all_restrictions() -> list[str]:
    """
    Return all restrictions that can be passed for any test configuration.

    :returns: all available (from configuration) vms
    """
    rep = get_parser()
    parse_batch(rep, base_file="groups-base.cfg")
    return get_params(rep, list_of_keys=["main_restrictions"]).objects(
        "main_restrictions"
    )


def all_objects(key: str = "vms", composites: list[str] = None) -> list[str]:
    """
    Return all test objects that can be passed for any test configuration.

    :param: key: key to extract parametric objects from
    :param composites: composite restriction of the returned objects
    :returns: all available (from configuration) objects of a given type
    """
    rep = get_parser()
    parse_batch(rep, base_file="guest-base.cfg")
    params = get_params(rep)
    composites = [] if not composites else composites
    for composite in composites:
        params = params.object_params(composite)
    return params.objects(key)


def all_suffixes_by_restriction(restriction: str, key: str = "nets") -> list[str]:
    """
    Return all object suffixes via restriction of their variants.

    :param: restriction: restriction of the suffix variants
    :param: key: key to describe the parametric object type
    :returns: all restricted (from configuration) object suffixes of a given type
    """
    rep = get_parser()
    parse_batch(rep, base_file=f"{key}.cfg")
    rep.parse_string(restriction)
    return [d["shortname"] for d in get_dicts(rep)]


def main_vm() -> str | None:
    """
    Return the default main vm that can be passed for any test configuration.

    :returns: main available (from configuration) vm
    """
    rep = get_parser()
    parse_batch(rep, base_file="guest-base.cfg")
    return get_params(rep, list_of_keys=["main_vm"]).get("main_vm")


def re_str(variant_str: str, base_str: str = "", tag: str = "") -> str:
    """
    Add a variant restriction to the base string, optionally adding a custom tag as well.

    :param variant_str: variant restriction
    :param base_str: string where the variant restriction will be added
    :param tag: additional tag to the variant combination
    :returns: restricted parameter string
    """
    if tag != "":
        variant_str = "variants:\n    - %s:\n        only %s\n" % (tag, variant_str)
    else:
        variant_str = "only %s\n" % variant_str
    return base_str + variant_str


def join_str(variant_strs: dict[str, str], sort_key: str, base_str: str = "") -> str:
    """
    Join all object variant restrictions over the base string.

    :param variant_strs: variant restrictions for each object as key, value pair
    :param sort_key: key to extract parametric objects from
    :param base_str: string where the variant restriction will be added
    :returns: restricted parameter string
    """
    objects, variant_str = "", ""
    available_objects = all_objects(sort_key)
    for suffix in available_objects:
        if suffix not in variant_strs.keys():
            continue
        variant = variant_strs[suffix]
        subvariant = "".join(
            ["    " + line + "\n" for line in variant.rstrip("\n").split("\n")]
        )
        variant_str += "%s:\n%s" % (suffix, subvariant)
        objects += " " + suffix
    if objects == "":
        raise ValueError(
            f"Could not find some of {list(variant_strs.keys())} among "
            f"the available {available_objects}"
        )
    variant_str += "join" + objects + "\n"
    return base_str + variant_str
