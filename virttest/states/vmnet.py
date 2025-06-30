# pylint: disable=abstract-method,docstring-first-line-empty,missing-param-doc,missing-return-doc,redefined-builtin,unnecessary-pass
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
Module for the VMNet state management backend.

SUMMARY
------------------------------------------------------

Copyright: Intra2net AG

INTERFACE
------------------------------------------------------

"""

from typing import Any

from virttest.utils_params import Params

from ..vmnet import VMNetwork, setup_vmnet
from .composition import NetStateBackend


class VMNetBackend(NetStateBackend):
    """Backend manipulating network states as VMNet operations."""

    network_class = VMNetwork

    @classmethod
    def get(cls, params: Params, object: Any = None) -> None:
        """
        Retrieve a state disregarding the current changes.

        All arguments match the base class.
        """
        setup_vmnet(params, object, cls.network_class)
