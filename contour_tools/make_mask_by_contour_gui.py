"""Contour tools for Agisoft Metashape

Copyright (C) 2021  Geoscan Ltd. https://www.geoscan.aero/

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

import os

from common.loggers.email_logger import log_method_by_crash_reporter
from common.utils.PluginBase import PluginBase
from contour_tools.project_contour import MakeMasks


class MainDialog(PluginBase):

    NAME = "Make masks from shapes"
    VERSION = "1.0.1"

    def __init__(self,  parent=None):
        ui_path = os.path.join(os.path.dirname(__file__), 'make_mask_by_shape_gui.ui')
        super(MainDialog, self).__init__(ui_path)

    def _init_ui(self):
        """
        Initialize UI of plugin.
        :return: None
        """
        dlg = self.dlg
        self.load_values()

        dlg.OkBut.clicked.connect(self.start_mask)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def start_mask(self):
        dlg = self.dlg

        MakeMasks().project_onto_cameras()

    def log_values(self):
        return {}


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext

    exporter = MainDialog()
    exporter.dlg.exec_()


if __name__ == "__main__":
    main()
