"""Common scripts, classes and functions

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
import threading

from PySide2 import QtWidgets

from common.utils.ui import load_ui_widget
from common.loggers.email_logger import LoggerValues, send_geoscan_plugins_error_to_devs


class CrashReporter:

    def __init__(self, error: str, logger_values: LoggerValues, parent=None):
        self.ui = load_ui_widget(
            os.path.join(os.path.dirname(__file__), "crash_reporter.ui"),
            parent=parent,
        )
        self.error = error

        self.init_translations()
        self.connect_buttons()

        self.logger_values = logger_values

    def init_translations(self):
        # examples:
        # self.ui.setWindowTitle(_('MapInfo table "Cameras"'))
        # self.ui.groupBox.setTitle(_("User data in MapInfo table"))
        # self.ui.CameraTypeLabel.setText(_("Camera type:"))
        # self.ui.CameraTypeCheckBox.setText(_("Fill camera type column automatically by EXIF"))
        pass

    def connect_buttons(self):

        def email_checkbox():
            self.ui.email_lineEdit.setDisabled(not self.ui.email_checkBox.isChecked())

        email_checkbox()
        self.ui.textBrowser.setText(self.error)
        self.ui.email_checkBox.stateChanged.connect(email_checkbox)
        self.ui.buttonBox.accepted.connect(lambda: self.run(True))
        self.ui.buttonBox.rejected.connect(lambda: self.run(False))

    def run(self, send_error: bool):
        if send_error:
            self.logger_values.reply_email = self.ui.email_lineEdit.text()
            self.logger_values.user_annotation = self.ui.plainTextEdit.toPlainText()
            send_geoscan_plugins_error_to_devs(error=self.error, values=self.logger_values)
        self.ui.close()


def run_crash_reporter(error, values, run_thread=False):
    def init():
        dialog.ui.show()
        dialog.ui.exec_()

    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    dialog = CrashReporter(error, values, parent=parent)
    if run_thread:
        thread = threading.Thread(target=init)
        thread.start()
    else:
        res = dialog.ui.exec_()


if __name__ == "__main__":
    pass
