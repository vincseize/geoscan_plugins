"""Apply Vertical Camera Alignment plugin for Agisoft Metashape

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

from PySide2 import QtWidgets
import Metashape

from fast_layout.fast_layout_manual import run_camera_alignment_manual
from fast_layout.fast_layout_automatic import run_camera_alignment_automatic
from fast_layout.fast_layout_gui import Ui_Dialog

from common.loggers.email_logger import log_method_by_crash_reporter


class VAlignmentGUI(QtWidgets.QDialog, Ui_Dialog):

    NAME = "Apply Vertical Camera Alignment"
    VERSION = "1.0.2"

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.ui = Ui_Dialog()
        self.setupUi(self)

        self.radioButton.setChecked(True)
        self.doubleSpinBox.setDisabled(True)

        self.pushButton.clicked.connect(self.run)
        self.radioButton.toggled.connect(lambda x=True: self.doubleSpinBox.setDisabled(x))
        self.radioButton_2.toggled.connect(lambda x=True: self.doubleSpinBox.setEnabled(x))

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def run(self):
        chunk = Metashape.app.document.chunk

        if self.radioButton.isChecked() and len([True for c in chunk.cameras if c.reference.location is not None]) > 4:
            run_camera_alignment_automatic()
        else:
            run_camera_alignment_manual(mount_angle=self.doubleSpinBox.value())

    def log_values(self):
        d = {
            'Automatic mode': self.radioButton.isChecked(),
            'Manual mode': self.radioButton_2.isChecked(),
            'Mount angle': self.doubleSpinBox.value(),
        }
        return d


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext

    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()

    plugin = VAlignmentGUI(parent)
    plugin.show()
