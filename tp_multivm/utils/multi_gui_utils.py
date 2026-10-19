"""
Visual helpers shared by the multi-GUI tests and test generator.

Copyright: Intra2net AG
"""

import logging

from guibot.guibot import GuiBot

log = logging.getLogger("avocado.test.utils")


class VisualObject(GuiBot):
    """
    Visual objects contain logic for manipulation of visual
    information.
    """

    def image_root(self, r=None):
        """
        Image root location where the images for the visual
        object will be searched for.
        """
        if r is None:
            return self._image_root
        else:
            self._image_root = r

    def __init__(self, imgroot, dc=None, cv=None):
        """
        Construct a visual object with optional custom backends.

        :param str imgroot: the image root location for the object
        :param dc: desktop control backend
        :type dc: Controller object
        :param cv: computer vision backend
        :type cv: Finder object
        """
        super(VisualObject, self).__init__(dc=dc, cv=cv)
        self._image_root = imgroot
        self.add_path(self._image_root)


class Linux(VisualObject):
    """
    Visual object to handle Linux OS related
    operations on the GUI.
    """

    def start_menu_option(self, option="admin"):
        """
        Open an option in the start menu, opening the start
        menu if necessary.

        :param str option: option in the start menu
        """
        log.info("Looking for '%s' in the start menu", option)
        self.press_keys([self.ALT, self.F2])
        self.type_text(option)
        self.press_keys(self.ENTER)


class Windows(VisualObject):
    """
    Visual object to handle Windows OS related
    operations on the GUI.
    """

    def start_menu_option(self, option="admin"):
        """
        Open an option in the start menu, opening the start
        menu if necessary.

        :param str option: option in the start menu
        """
        log.info("Looking for '%s' in the start menu", option)
        self.click("win10-start-button")
        self.type_text(option)
        self.press_keys(self.ENTER)
