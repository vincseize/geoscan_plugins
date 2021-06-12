"""Set altitudes for shape plugin for Agisoft Metashape

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

from statistics import median, stdev
import textwrap
import Metashape
from PySide2 import QtWidgets
from .set_altitudes_for_shape_ui import Ui_Dialog
from common.loggers.email_logger import log_method_by_crash_reporter


class SetAltitudesForShape(QtWidgets.QDialog, Ui_Dialog):

    NAME = "Set altitude for shape"
    VERSION = "1.0.1"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_Dialog()
        self.setupUi(self)

        self.chunk = Metashape.app.document.chunk

        self.pushButton.clicked.connect(self.set_selected_altitude)
        self.pushButton_2.clicked.connect(self.set_median_altitude)
        # self.pushButton_3.clicked.connect(self.__remove_outliers)

    def messageBox(self, text):
        return Metashape.app.messageBox(textwrap.fill(_(str(text)), 65))

    def get_selected_shapes(self):
        selected_shapes = []
        for shape in self.chunk.shapes:
            if shape.selected:
                selected_shapes.append(shape)
        return selected_shapes

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def set_selected_altitude(self):
        shapes = self.get_selected_shapes()
        if not shapes:
            self.messageBox('Select shape to process.')
            return

        custom_altitude = self.doubleSpinBox.value()
        for shape in shapes:
            new_vertices = [Metashape.Vector([v.x, v.y, custom_altitude]) for v in shape.vertices]
            shape.vertices = new_vertices

        self.messageBox('Altitude has been set! Update shape layer by double-click on layer in Workspace.')

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def set_median_altitude(self):
        shapes = self.get_selected_shapes()
        if not shapes:
            self.messageBox('Select shape to process.')
            return

        for shape in shapes:
            altitudes = [v.z for v in shape.vertices]
            median_alt = median(altitudes)
            new_vertices = [Metashape.Vector([v.x, v.y, median_alt]) for v in shape.vertices]
            shape.vertices = new_vertices

        if len(shapes) == 1:
            self.doubleSpinBox.setValue(round(median_alt, 2))

        self.messageBox('Altitude has been set! Update shape layer by double-click on layer in Workspace.')

    def __remove_outliers(self):
        shapes = self.get_selected_shapes()
        if not shapes:
            self.messageBox('Select shape to process.')
            return

        for shape in shapes:
            altitudes = [v.z for v in shape.vertices]
            new_altitudes = []
            for _ in range(3):
                if new_altitudes:
                    altitudes = new_altitudes
                median_alt = median(altitudes)
                stdev_alt = stdev(altitudes)
                if stdev_alt == 0:
                    return

                z_altitudes = [(v.z - median_alt)/stdev_alt for v in shape.vertices]
                new_altitudes = []
                for i, z in enumerate(z_altitudes):
                    if z < 2:
                        new_altitudes.append(altitudes[i])
                    else:
                        if i - 1 >= 0:
                            new_altitudes.append(altitudes[i-1])
                        else:
                            while z_altitudes[i] >= 2:
                                i += 1
                            new_altitudes.append(altitudes[i])

            new_vertices = [Metashape.Vector([v.x, v.y, new_altitudes[i]]) for i, v in enumerate(shape.vertices)]
            shape.vertices = new_vertices

        self.messageBox('Outliers have been removed! Update shape layer by double-click on layer in Workspace.')

    def log_values(self):
        d = {
            'Altitude': self.doubleSpinBox.value(),
        }
        return d


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext

    app = QtWidgets.QApplication.instance()
    parent = app.activeWindow()

    plugin = SetAltitudesForShape(parent)
    plugin.show()


if __name__ == "__main__":
    main()
