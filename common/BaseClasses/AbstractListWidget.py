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
import abc
import PhotoScan


class AbstractListWidget(QListWidget):
    """
    List widget with navigation and bold rows
    """
    __metaclass__ = abc.ABCMeta

    def __init__(self, properties, view, parent=None):
        QListWidget.__init__(self, parent)
        self.properties = properties
        self.view = view
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.currentItemChanged.connect(lambda cur, prev: self.change_item(cur, prev))

    @abc.abstractmethod
    def boldCriterion(self, item_name):
        """
        criterion to make item bold
        """
        pass

    @abc.abstractmethod
    def change_item(self, cur, prev):
        """
        actions on item change
        """
        pass

    def toggleBold(self, item_name):
        """
        toggle items bold or green if boldCriterion
        """
        # items = self.findItems(item_name, Qt.MatchExactly) + self.findItems(item_name + " ", Qt.MatchStartsWith)
        for idx in range(self.count()):
            item = self.item(idx)
            text = item.text() or item.toolTip()
            if text == item_name or text.startswith(item_name + " "):
                if self.boldCriterion(item_name):
                    if item.icon():
                        item.setBackground(QColor(0, 255, 0))
                    else:
                        item.setBackground(QColor(245, 245, 245))
                else:
                    item.setBackground(QColor(255, 255, 255))
                font = QFont()
                font.setBold(self.boldCriterion(item_name))
                item.setFont(font)

    def num_of_markers(self, item_name):
        """
        add number of markers connected with such item
        """
        markers = [marker for marker in PhotoScan.app.document.chunk.markers if marker.label.split()[0] == item_name and marker.position]
        item = self.findItems(item_name + " ", Qt.MatchStartsWith)[0]
        item.setText(item.text().split()[0] + " (" + str(len(markers)) + ")")

    def nextItem(self):
        self.setCurrentRow((self.currentRow() + 1) % self.count())

    def prevItem(self):
        self.setCurrentRow((self.currentRow() - 1) % self.count())

    def color_rows(self):
        for idx in range(self.count()):
            if idx % 2:
                self.item(idx).setBackground(QColor(100, 100, 100))
