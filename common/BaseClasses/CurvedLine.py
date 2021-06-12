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

import abc

from PySide2.QtCore import *
from PySide2.QtWidgets import *


class Segment(QGraphicsLineItem):
    """
    curved line segment behavior
    """
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptHoverEvents(True)

    def paint(self, painter, option, widget):
        if self.isSelected():
            option = QStyleOptionGraphicsItem()
        super().paint(painter, option, widget)



class CurvedLine(QGraphicsItem):
    """
    base class for all drawable lines (which are curved)
    """
    __metaclass__ = abc.ABCMeta
    def __init__(self, parent):
        super(CurvedLine, self).__init__(parent)
        self.segments = []
        self.determine_segments()
        if self.segments:
            for i in range(len(self.segments)-1):
                line = Segment(parent=self)
                line.setLine(self.segments[i].x, self.segments[i].y, self.segments[i+1].x, self.segments[i+1].y)

    @abc.abstractmethod
    def determine_segments(self):
        pass

    def boundingRect(self, *args, **kwargs):
        return QRectF(0, 0, 1, 1)

    def paint(self, *args, **kwargs):
        pass