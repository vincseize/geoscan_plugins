"""GNSS Post Processing plugin for Agisoft Metashape

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

from gnss_post_processing.app.processor import GnssProcessor
from PySide2 import QtWidgets


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()
    window = GnssProcessor(parent)
    window.ui.show()
