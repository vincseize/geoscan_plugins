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

from os import path as osp

from PySide2.QtGui import *
from PySide2.QtCore import *
from PySide2.QtWidgets import *
from .AbstractListWidget import AbstractListWidget


class BasicCameraListWidget(AbstractListWidget):
    """
    List widget for cameras. used for displaying image thumbnails and navigation between them
    """
    def __init__(self, properties, view, parent=None):
        AbstractListWidget.__init__(self, properties, view, parent)
        self.setIconSize(QSize(128, 128))
        self.view.next_camera_signal.connect(lambda: self.nextItem())
        self.view.prev_camera_signal.connect(lambda: self.prevItem())

    def add_image(self, photo):
        """
        add image to list
        :param photo: PhotoScan.Photo
        :return:
        """
        if photo:
            item = QListWidgetItem(self)
            label = osp.split(photo.path)[-1]
            if photo.thumbnail():
                image = photo.thumbnail().image()
                qimg = QImage(image.tostring(), image.width, image.height, QImage.Format_RGB888) # todo fix format
                pixmap = QPixmap.fromImage(qimg)
                item.setIcon(QIcon(pixmap))
            else:
                item.setText(label)
            item.setToolTip(label)
            self.addItem(item)
