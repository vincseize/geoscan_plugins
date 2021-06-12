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

from PySide2.QtWidgets import *

from .BasicDrawablePoint import BasicDrawablePoint


class MarkerProjection(BasicDrawablePoint):
    """
    drawable point collides with basis lines. don't show basis line colliding with point.
    point can be phantom - it's only point projection to show user position and error
    we can move points and then marker projections move too
    """
    def __init__(self, x, y, marker, is_phantom, image_view, parent=None, scene=None):
        BasicDrawablePoint.__init__(self, x, y, marker, image_view, parent, scene)
        self.is_phantom = is_phantom
        self.set_flags(not is_phantom)
        self.colliding_lines = []
        self.update_colliding()

    def update_colliding(self):
        """
        find colliding lines
        """
        for line in self.image_view.lines:
            line.show()
        self.colliding_lines = [line for line in self.collidingItems() if isinstance(line, QGraphicsLineItem)]

    def paint(self, painter, style_option, QWidget_widget=None):
        self.color = self.get_color()
        self.draw(painter, style_option)

        if self.isSelected():
            self.update_colliding()
        else:
            try:
                next(item for item in self.scene().selectedItems() if isinstance(item, MarkerProjection))
            except StopIteration:
                for line in self.colliding_lines:
                    line.parentItem().hide()

    def mouseReleaseEvent(self, QEvent):
        super().mouseReleaseEvent(QEvent)
        if self.marker.projections[self.camera].coord.x - self.pos().x() or self.marker.projections[self.camera].coord.y - self.pos().y():
            self.marker.projections[self.camera] = (self.pos().x(), self.pos().y())

    def get_color(self):
        raise NotImplementedError
