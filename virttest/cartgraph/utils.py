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

"""Test-suite paths, defaults and Cartesian object restrictions."""

from __future__ import annotations

import logging
import os

from avocado.core.settings import settings

from ..cartconf import Parser

settings.register_option(
    section="vt.common",
    key="suite_path",
    key_type=str,
    default=os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "tp_multivm")
    ),
    help_msg="Path to the test suite containing Cartesian variants and test scripts.",
)


def custom_configs_dir() -> str:
    """Return the active test suite's configuration directory.

    :returns: suite configuration directory
    """
    return os.path.join(settings.as_dict()["vt.common.suite_path"], "configs")


def config_file(filename: str) -> str:
    """Resolve a suite configuration filename, retaining absolute paths.

    :param filename: relative or absolute configuration filename
    :returns: configuration path
    """
    return os.path.join(custom_configs_dir(), filename)


def ovrwrt_file(category: str) -> str:
    """Find or create a user's overwrite file for a suite category.

    :param category: suite category such as tests, vms or nets
    :returns: user's overwrite configuration path
    """
    filename = os.path.join(os.environ["HOME"], f"avocado_overwrite_{category}.cfg")
    if not os.path.exists(filename):
        template = {"tests": "sets", "vms": "objects"}.get(category, category)
        logging.warning(
            "Generating a file to overwrite the original %s parameters", category
        )
        with open(filename, "w", encoding="utf-8") as handle:
            handle.write(
                f"# Use this config to override with {category} configuration\n"
                f"include {config_file(template + '-overwrite.cfg')}\n"
            )
    return filename


def tests_ovrwrt_file() -> str:
    """Return the user's test overwrite file.

    :returns: test overwrite configuration path
    """
    return ovrwrt_file("tests")


def vms_ovrwrt_file() -> str:
    """Return the user's VM overwrite file.

    :returns: VM overwrite configuration path
    """
    return ovrwrt_file("vms")


def get_parser() -> Parser:
    """Create a parser with the current host and test-suite defaults.

    :returns: parser initialized with host and suite parameters
    """
    parser = Parser()
    suite_path = settings.as_dict()["vt.common.suite_path"]
    parser.parse_dict(
        {
            "hostname": os.environ.get("PREFIX", os.environ.get("HOSTNAME", "avocado")),
            "suite_path": suite_path,
            "test_pre_hook": os.path.join(suite_path, "controls", "pre_test.control"),
        }
    )
    return parser


def all_restrictions() -> list[str]:
    """Return the primary restrictions declared by the suite.

    :returns: available primary test restrictions
    """
    rep = get_parser()
    rep.parse_file(config_file("groups-base.cfg"))
    return rep.get_params().objects("main_restrictions")


def all_objects(key: str = "vms", composites: list[str] = None) -> list[str]:
    """Return object suffixes, optionally scoped through composite objects.

    :param key: object category to list
    :param composites: composite objects to select before listing
    :returns: available object suffixes
    """
    rep = get_parser()
    rep.parse_file(config_file("guest-base.cfg"))
    params = rep.get_params()
    composites = [] if not composites else composites
    for composite in composites:
        params = params.object_params(composite)
    return params.objects(key)


def all_suffixes_by_restriction(restriction: str, key: str = "nets") -> list[str]:
    """Return network or VM suffixes matching a Cartesian restriction.

    :param restriction: Cartesian restriction to apply
    :param key: object category to list
    :returns: matching object suffixes
    """
    rep = get_parser()
    rep.parse_file(config_file(f"{key}.cfg"))
    rep.parse_str(restriction)
    return [d["shortname"] for d in rep.iter_params()]


def main_vm() -> str | None:
    """Return the suite's default primary VM.

    :returns: primary VM suffix, if configured
    """
    rep = get_parser()
    rep.parse_file(config_file("guest-base.cfg"))
    return rep.get_params().get("main_vm")


def re_str(variant_str: str, base_str: str = "", tag: str = "") -> str:
    """Build a restriction string with an optional variant tag.

    :param variant_str: variant expression to restrict
    :param base_str: configuration text to extend
    :param tag: optional tag for the restricted variant
    :returns: configuration text with the restriction appended
    """
    if tag:
        variant_str = f"variants:\n    - {tag}:\n        only {variant_str}\n"
    else:
        variant_str = f"only {variant_str}\n"
    return base_str + variant_str


def join_str(variant_strs: dict[str, str], sort_key: str, base_str: str = "") -> str:
    """Join object restrictions in the order declared by the suite.

    :param variant_strs: restrictions indexed by object suffix
    :param sort_key: object category defining the join order
    :param base_str: configuration text to extend
    :returns: configuration text with the ordered join appended
    :raises ValueError: if none of the requested suffixes exists
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
        variant_str += f"{suffix}:\n{subvariant}"
        objects += " " + suffix
    if not objects:
        raise ValueError(
            f"Could not find some of {list(variant_strs.keys())} among "
            f"the available {available_objects}"
        )
    variant_str += "join" + objects + "\n"
    return base_str + variant_str
