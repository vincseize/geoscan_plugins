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
from PySide2.QtCore import *
from PySide2.QtWidgets import *

class BasicDrawablePoint(QGraphicsEllipseItem):
    """
    Drawable point connected to marker
    """
    def __init__(self, x, y, marker, image_view, parent=None, scene=None):
        self.marker = marker
        self.image_view = image_view
        QGraphicsEllipseItem.__init__(self, parent, scene)

        self.setPos(x, y)
        self.setRect(QRectF(-10, -10, 20, 20))
        self.text = QGraphicsSimpleTextItem(self)
        self.color = QColor.fromRgb(255, 0, 0)

    def set_flags(self, condition):
        if condition:
            self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.setFlag(QGraphicsItem.ItemIsSelectable, True)

    def draw(self, painter, style_option):
        """
        circle with cross
        """
        rect = self.boundingRect()
        pen = QPen(self.color)
        self.text.setBrush(QBrush(self.color))
        label = self.marker.label if self.marker is not None else ""
        self.text.setText(label)
        self.text.show()
        painter.setPen(pen)
        if style_option.state & QStyle.State_Selected:
            painter.drawRect(rect)
        painter.drawEllipse(rect)
        pen = QPen(self.color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setBrush(self.color)
        painter.drawLine(-2, -2, 2, 2)
        painter.drawLine(-2, 2, 2, -2)
