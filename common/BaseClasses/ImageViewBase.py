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
from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *


class ImageViewBase(QGraphicsView):
    """
    zoomable and draggable image base class
    """
    __metaclass__ = abc.ABCMeta
    next_camera_signal = Signal()
    prev_camera_signal = Signal()
    def __init__(self, parent=None):
        QGraphicsView.__init__(self, parent)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pixItem = None
        self.factor = None
        self.interface = parent
        self.setFocusPolicy(Qt.StrongFocus)
        self.image = None

    def __setPixmap(self, pixmap):
        self.pixItem = QGraphicsPixmapItem(pixmap)
        self.pixItem.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.pixItem.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.scene.clear()
        self.scene.addItem(self.pixItem)
        self.fitInView(self.pixItem, Qt.KeepAspectRatio)

    def load_image(self, photo):
        """
        open PhotoScan.Image in window
        """
        if photo.image():
            image = photo.image()
            qimg = QImage(image.tostring(), image.width, image.height, QImage.Format_RGB888) # todo fix format
            pixmap = QPixmap.fromImage(qimg)
            self.__setPixmap(pixmap)
            self.draw_overlay()
        else:
            raise FileNotFoundError

    def wheelEvent(self, event):
        """
        zoom
        """
        zoomInFactor = 1.25
        zoomOutFactor = 1 / zoomInFactor

        oldPos = self.mapToScene(event.pos())

        if event.delta() > 0:
            zoomFactor = zoomInFactor
        else:
            zoomFactor = zoomOutFactor
        self.factor = zoomFactor
        self.scale(zoomFactor, zoomFactor)

        newPos = self.mapToScene(event.pos())

        delta = newPos - oldPos
        self.translate(delta.x(), delta.y())


    def update(self, *__args):
        QGraphicsView.update(self, *__args)
        self.removeAll()
        self.draw_overlay()

    @abc.abstractmethod
    def removeAll(self):
        """
        remove all components added (overlay)
        """
        pass

    @abc.abstractmethod
    def draw_overlay(self):
        """
        draw basis lines, points, etc
        """
        pass

    def move_to_tower_center(self, pos, calibration):
        """
        move camera to tower and zoom it there
        """
        self.resetTransform()
        x, y = pos.x, pos.y
        if 0 < x < calibration.width and 0 < y < calibration.height:
            shift = x - calibration.width / 2, y - calibration.height / 2
            x, y = shift
            self.pixItem.setPos(self.pixItem.pos() - QPointF(x, y))
            self.scale(1.5, 1.5)
