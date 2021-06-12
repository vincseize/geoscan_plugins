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

import traceback

import PhotoScan as ps
from PySide2.QtCore import *
from PySide2.QtWidgets import *

from common.loggers.email_logger import log_method_by_crash_reporter
from common.shape_worker.shape_worker import modify_contours_offset, duplicate_contours, \
    copy_contours_on_different_height
from common.utils.ui import findMainWindow, show_error


class ContourToolsUI(QWidget):

    NAME = "Shape utils"
    VERSION = "1.0.0"

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)

        vbox = QVBoxLayout()

        offset_layout = QVBoxLayout()
        offset_label = QLabel()
        offset_label.setText(_("Offset (sm)"))
        self.offset_text = QLineEdit()
        self.offset_btn = QPushButton()
        self.offset_btn.setText(_("Apply offset"))
        offset_layout.addWidget(offset_label)
        offset_layout.addWidget(self.offset_text)
        offset_layout.addWidget(self.offset_btn)

        height_layout = QVBoxLayout()
        height_label = QLabel()
        height_label.setText(_("Move up (sm)"))
        self.height_text = QLineEdit()
        self.height_btn = QPushButton()
        self.height_btn.setText(_("Apply height"))
        height_layout.addWidget(height_label)
        height_layout.addWidget(self.height_text)
        height_layout.addWidget(self.height_btn)

        duplicate_btn = QPushButton()
        duplicate_btn.setText(_("Duplicate selected"))

        vbox.addLayout(offset_layout)
        vbox.addLayout(height_layout)
        vbox.addWidget(duplicate_btn)

        self.setLayout(vbox)

        duplicate_btn.clicked.connect(lambda: self.duplicate_contour())
        self.height_btn.clicked.connect(lambda: self.modify_height())
        self.offset_btn.clicked.connect(lambda: self.modify_offset())

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def modify_height(self):
        try:
            delta_h = float(self.height_text.text())
        except (ValueError, TypeError) as e:
            show_error(_("Error"), _("Delta h is not a number"))
            return

        shapes = [c for c in ps.app.document.chunk.shapes if c.selected]
        copy_contours_on_different_height(shapes, delta_h)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def modify_offset(self):
        try:
            delta_o = float(self.offset_text.text())
        except (ValueError, TypeError) as e:
            show_error(_("Error"), _("Delta offset is not a number"))
            return
        shapes = [c for c in ps.app.document.chunk.shapes if c.selected]
        modify_contours_offset(shapes, delta_o)

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def duplicate_contour(self):
        shapes = [c for c in ps.app.document.chunk.shapes if c.selected]
        duplicate_contours(shapes)

    def log_values(self):
        d = {
            "height": self.height_text.text(),
            "offset": self.offset_text.text(),
        }
        return d


def start_contour_tools(trans):
    try:
        w = findMainWindow()
        trans.install()
        _ = trans.gettext
        dock = QDockWidget(_("Contour tools"), w)
        # dock.setAllowedAreas(Qt.BottomDockWidgetArea)
        dock.setObjectName(_("Contour tools"))
        # w.setDockOptions(QMainWindow.ForceTabbedDocks)
        w.addDockWidget(Qt.LeftDockWidgetArea, dock)
        model_builder_dock = ContourToolsUI(dock)
        dock.setWidget(model_builder_dock)
    except:
        traceback.print_exc()
