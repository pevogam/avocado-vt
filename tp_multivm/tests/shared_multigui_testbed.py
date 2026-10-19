"""

SUMMARY
------------------------------------------------------
Test to experiment with the multi-GUI virtual user extensions.

Copyright: Intra2net AG


CONTENTS
------------------------------------------------------
In particular, we might run it on manually prepared vm4/vm5 whose
preparation involves opening and maximizing paint/KolourPaint as
a window (mouse testing) and repeating the same with another window
for an editor (notepad/Kwrite). The preparation of the vms is concluded
with a stored online state with the name of "vu_alt".

Once you have prepared or obtained such images, you can both get the
"vu_alt" state and run the test with::

    avocado env setup=develop devmode=testbed vms=vm4,vm5

Then experiment on a canvas (paint->mouse) or blank space (editor->keys).


INTERFACE
------------------------------------------------------

"""

import logging
import random

# custom imports
from multi_gui_utils import Linux, Windows
from PyQt5 import QtCore, QtWidgets
from test_generator.generator_api import API
from test_generator.generator_app import GUITestGenerator

log = logging.getLogger("avocado.test.log")


###############################################################################
# TESTING
###############################################################################


def stress_test(gui, name, *args):
    """
    Run a stress test of a given class by calling this function.

    :param gui: the generator API
    :type gui: test_generator.generator_api.API
    :param str name: test class :"mouse-grid", "mouse-hit", "all-keys", or "custom"
    :param args: test arguments
    """
    tests = {
        "mouse-grid": StressTestMouseGrid,
        "mouse-hit": StressTestMouseHit,
        "all-keys": StressTestAllKeys,
        "custom": StressTestCustom,
    }
    # The generator already runs control code in a worker. Keep this call in
    # that worker so its Stop button and error reporting cover stress tests too.
    tests[name](gui, *args).run()


class StressTestMouseGrid(QtCore.QThread):
    """
    Fill a grid by clicks resulting in a filled square
    in case of 100% mouse hover+click precision.

    Window to use: **paint**

    Tested functionality: **mouse**
    """

    def __init__(self, gui, step=10):
        """
        Construct the stress test.

        :param gui: the GUI control window
        :type gui: test_generator.generator_api.API
        :param int step: grid interval
        """
        QtCore.QThread.__init__(self)
        self.gui = gui
        self.step = step

    def run(self):
        """Run the stress test."""
        from guibot.location import Location

        for i in range(0, 500 // self.step):
            for j in range(0, 500 // self.step):
                self.gui._visual_object.click(
                    Location(100 + self.step * i, 100 + self.step * j)
                )
                if self.gui.interrupt_requested:
                    return


class StressTestMouseHit(QtCore.QThread):
    """
    Test mouse precision by clicking on the same location
    then hovering away and then clicking again resulting
    in a single point visible on the screen in the case
    of 100% mouse hover+click precision.

    Window to use: **paint**

    Tested functionality: **mouse**
    """

    def __init__(self, gui, trials=100):
        """
        Construct the stress test.

        :param gui: the GUI control window
        :type gui: test_generator.generator_api.API
        :param int trials: number of trials to hit target
        """
        QtCore.QThread.__init__(self)
        self.gui = gui
        self.trials = trials

    def run(self):
        """Run the stress test."""
        from guibot.location import Location

        for i in range(self.trials):
            log.info(f"Performing hover-click hit {i}")
            self.gui._visual_object.hover(
                Location(random.randrange(100, 500), random.randrange(100, 500))
            )
            self.gui._visual_object.click(Location(300, 300))
            if self.gui.interrupt_requested:
                return


class StressTestAllKeys(QtCore.QThread):
    """
    Type all printable keys to check if the key translation
    is correct for the current virtual user backend.

    Window to use: **editor**

    Tested functionality: **keyboard**
    """

    def __init__(self, gui):
        """
        Construct the stress test.

        :param gui: the GUI control window
        :type gui: test_generator.generator_api.API
        """
        QtCore.QThread.__init__(self)
        self.gui = gui

    def run(self):
        """Run the stress test."""
        self.gui._visual_object.type_text(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
        )
        self.gui._visual_object.press_keys([self.gui._visual_object.ENTER])
        if self.gui.interrupt_requested:
            return
        self.gui._visual_object.type_text("`1234567890-=~!@#$%^&*()_+")
        self.gui._visual_object.press_keys([self.gui._visual_object.ENTER])
        if self.gui.interrupt_requested:
            return
        self.gui._visual_object.type_text("[]{};'\\:\"|,./<>?")
        self.gui._visual_object.press_keys([self.gui._visual_object.ENTER])


class StressTestCustom(QtCore.QThread):
    """
    Perform a custom stress test. The only thing you need to
    do is put your code in the :py:func:`StressTestCustom.run`
    method, allowing it to be interruptible at certain places
    through lines like::

        if self.gui.interrupt_requested:
            return

    Window to use: **paint, editor, etc.**

    Tested functionality: **mouse, keyboard, GUI control, etc.**
    """

    def __init__(self, gui, visual_os="windows"):
        """
        Construct the stress test.

        :param gui: the GUI control window
        :type gui: test_generator.generator_api.API
        """
        QtCore.QThread.__init__(self)
        self.gui = gui
        self.visual_os = visual_os

    def run(self):
        """
        Run the stress test.

        This code is just an example where we open the Windows menu
        500 times waiting for a failure to do so. It can be customized
        or changed to any other desired behavior.
        """
        if self.visual_os == "windows":
            os_type = Windows
        elif self.visual_os == "linux":
            os_type = Linux
        else:
            raise ValueError("Inappropriate choice of OS for custom stress test")
        os = os_type(self.gui._image_root, dc=self.gui._visual_object.dc_backend)
        # NOTE: this could be moved to the arguments but is kept here
        # to simplify the example stress test
        n = 500
        for i in range(n):
            log.info("Attempt %s/%s", i, n)
            os.start_menu_option()
            os.press_keys(os.ESC)
            if self.gui.interrupt_requested:
                return
        log.info("No errors")


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
    log.info("Initiating the GUI test generator's GUI with all stress tests")
    app = QtWidgets.QApplication([])

    vmnet = env.get_vmnet()
    api = API(vmnet, context=(globals().copy(), {}))
    mt = GUITestGenerator(api)
    mt.show()
    mt._w.text_edit.setText(
        "stress_test(self, 'mouse-grid', 10)\u2029"
        "stress_test(self, 'mouse-hit', 100)\u2029"
        "stress_test(self, 'all-keys')\u2029"
        "stress_test(self, 'custom')\u2029"
    )

    log.info("GUI test generator's GUI initiated")
    # TODO: Once this is converted from pseudotest to an actual tool,
    # we will be free to do this
    # sys.exit(app.exec_())
    app.exec_()

    log.info("Testbed completed successfully!")
