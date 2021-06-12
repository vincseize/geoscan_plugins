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

from PySide2.QtGui import *

from common.BaseClasses.CurvedLine import CurvedLine
from common.cg.basis_line_ops import line_in_cam, ray


class BasisLine(CurvedLine):
    def __init__(self, marker, camera, parent=None):
        self.camera = camera
        self.marker = marker
        CurvedLine.__init__(self, parent)
        for child in self.childItems():
            color = self.get_color()
            pen = QPen(color)
            pen.setWidth(1)
            child.setPen(pen)

    def determine_segments(self):
        """
        project line going from camera center to marker position and cut it to segments.
        line is generally not straight
        """
        s, e = ray(self.marker, self.camera)
        if s is not None and e is not None:
            self.segments = line_in_cam(s, e, self.camera)

    def get_color(self):
        return QColor.fromRgb(0, 0, 0)