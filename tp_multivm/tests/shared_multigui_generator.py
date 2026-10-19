"""

SUMMARY
------------------------------------------------------
Create a GUI (or even non-GUI) test directly on top of a running vm.

Copyright: Intra2net AG


CONTENTS
------------------------------------------------------
The following test generates a GUI panel to control a vm or
a set of vms.

At the present it must be used in conjunction with a normal
VNC client from which to interact with the vm's GUI.

The panel can be used to pause, resume and capture a vm as
well as for other neat purposes.

.. seealso:: Extra guide on GUI test development in the wiki.


INTERFACE
------------------------------------------------------

"""

import logging

# custom imports
from test_generator.generator_api import API, DEFAULT_PORT, expose_api

log = logging.getLogger("avocado.test.log")


###############################################################################
# TEST MAIN
###############################################################################


def run(test, params, env):
    """
    Main test run.

    :param test: test object
    :type test: :py:class:`avocado_vt.test.VirtTest`
    :param params: extended dictionary of parameters
    :type params: :py:class:`virttest.utils_params.Params`
    :param env: environment object
    :type env: :py:class:`virttest.utils_env.Env`
    """
    vmnet = env.get_vmnet()
    if params.get_boolean("api_only", False):
        expose_api(
            vmnet,
            remote_port=params.get_numeric("remote_port", DEFAULT_PORT),
            remote_host=params.get("remote_host", "127.0.0.1"),
        )
    else:
        from test_generator.generator_app import main

        log.info("Starting GUI test generator")
        main(API(vmnet))
