# -*- coding: utf-8 -*-
"""Mesh creator for Agisoft Metashape

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

import os
import gettext

from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QPixmap
from PySide2.QtWidgets import QVBoxLayout, QFrame, QPushButton, QGroupBox, QGridLayout, QLabel, QLineEdit, QComboBox, \
    QWidget, QApplication

PLUGIN_PATH = os.path.dirname(__file__)

# aplly translation through gettext module

class Ui_Form(object):
    def setupUi(self, Form):
        Form.setObjectName("Form")

        vbox = QVBoxLayout(Form)
        vbox.setContentsMargins(5, 5, 5, 5)

        self.frame = QFrame(Form)
        vframe = QVBoxLayout(self.frame)
        vbox.addWidget(self.frame, alignment=Qt.AlignTop)

        self.groupbox_wall = QGroupBox(self.frame)
        self.groupbox_wall.setObjectName("groupbox_wall")
        vframe.addWidget(self.groupbox_wall, alignment=Qt.AlignTop)

        self.gridLayout_wall = QGridLayout(self.groupbox_wall)
        self.gridLayout_wall.setContentsMargins(5, 2, 5, 2)
        self.gridLayout_wall.setColumnStretch(2, 1)
        self.gridLayout_wall.setObjectName("gridLayout_wall")

        self.height_label = QLabel(self.groupbox_wall)
        self.height_label.setObjectName("height_label")
        self.height_label.setMinimumWidth(110)
        self.gridLayout_wall.addWidget(self.height_label, 0, 0, 1, 1, alignment=Qt.AlignLeft)

        self.height_text = QLineEdit(self.groupbox_wall)
        self.height_text.setObjectName("height_text")
        self.gridLayout_wall.addWidget(self.height_text, 0, 1, 1, 1, alignment=Qt.AlignRight)

        self.height_m_label = QLabel(self.groupbox_wall)
        self.height_m_label.setObjectName("height_m_label")
        self.gridLayout_wall.addWidget(self.height_m_label, 0, 2, 1, 1, alignment=Qt.AlignLeft)

        self.wall_btn = QPushButton(self.groupbox_wall)
        self.wall_btn.setFixedSize(50, 50)
        self.wall_btn.setIconSize(QSize(32, 32))
        self.wall_btn.setObjectName("wall_btn")
        self.gridLayout_wall.addWidget(self.wall_btn, 0, 3, 2, 1, alignment=Qt.AlignRight)

        self.direction = QLabel(self.groupbox_wall)
        self.direction.setObjectName("direction")
        self.direction.setMinimumWidth(110)
        self.gridLayout_wall.addWidget(self.direction, 1, 0, 1, 1, alignment=Qt.AlignLeft)

        self.direction_list = QComboBox(self.groupbox_wall)
        self.direction_list.setMinimumWidth(114)
        self.gridLayout_wall.addWidget(self.direction_list, 1, 1, 1, 1, alignment=Qt.AlignRight)

        self.groupbox_roof = QGroupBox(self.frame)
        self.groupbox_roof.setObjectName("groupbox_roof")
        vframe.addWidget(self.groupbox_roof, alignment=Qt.AlignTop)

        self.gridLayout_roof = QGridLayout(self.groupbox_roof)
        self.gridLayout_roof.setContentsMargins(5, 2, 5, 2)
        self.gridLayout_roof.setColumnStretch(2, 1)
        self.gridLayout_roof.setObjectName("gridLayout_roof")

        self.plane_roof_label = QLabel(self.groupbox_roof)
        self.plane_roof_label.setObjectName("plane_roof_label")
        self.gridLayout_roof.addWidget(self.plane_roof_label, 0, 0, 1, 1, alignment=Qt.AlignLeft)

        self.plane_roof_btn = QPushButton(self.groupbox_roof)
        self.plane_roof_btn.setFixedSize(50, 50)
        self.plane_roof_btn.setIconSize(QSize(32, 32))
        self.plane_roof_btn.setObjectName("plane_roof_btn")
        self.gridLayout_roof.addWidget(self.plane_roof_btn, 0, 3, 1, 1, alignment=Qt.AlignRight)

        self.roof_with_parapet_label = QLabel(self.groupbox_roof)
        self.roof_with_parapet_label.setObjectName("roof_with_parapet_label")
        self.gridLayout_roof.addWidget(self.roof_with_parapet_label, 1, 0, 1, 2, alignment=Qt.AlignLeft)

        self.inside_indent_label = QLabel(self.groupbox_wall)
        self.inside_indent_label.setObjectName("inside_indent_label")
        self.inside_indent_label.setMinimumWidth(110)
        self.gridLayout_roof.addWidget(self.inside_indent_label, 2, 0, 1, 1, alignment=Qt.AlignLeft)

        self.inside_indent_text = QLineEdit(self.groupbox_wall)
        self.inside_indent_text.setObjectName("inside_indent_text")
        self.gridLayout_roof.addWidget(self.inside_indent_text, 2, 1, 1, 1, alignment=Qt.AlignRight)

        self.inside_m_label = QLabel(self.groupbox_wall)
        self.inside_m_label.setObjectName("inside_m_label")
        self.gridLayout_roof.addWidget(self.inside_m_label, 2, 2, 1, 1, alignment=Qt.AlignLeft)

        self.down_indent_label = QLabel(self.groupbox_wall)
        self.down_indent_label.setObjectName("down_indent_label")
        self.down_indent_label.setMinimumWidth(110)
        self.gridLayout_roof.addWidget(self.down_indent_label, 3, 0, 1, 1, alignment=Qt.AlignLeft)

        self.down_indent_text = QLineEdit(self.groupbox_wall)
        self.down_indent_text.setObjectName("inside_indent_text")
        self.gridLayout_roof.addWidget(self.down_indent_text, 3, 1, 1, 1, alignment=Qt.AlignRight)

        self.down_m_label = QLabel(self.groupbox_wall)
        self.down_m_label.setObjectName("down_m_label")
        self.gridLayout_roof.addWidget(self.down_m_label, 3, 2, 1, 1, alignment=Qt.AlignLeft)

        self.roof_btn = QPushButton(self.groupbox_wall)
        self.roof_btn.setFixedSize(50, 50)
        self.roof_btn.setIconSize(QSize(32, 32))
        self.roof_btn.setObjectName("roof_btn")
        self.gridLayout_roof.addWidget(self.roof_btn, 2, 3, 2, 1, alignment=Qt.AlignRight)


        self.groupbox_inner_buffer = QGroupBox(self.frame)
        self.groupbox_inner_buffer.setObjectName("groupbox_inner_buffer")
        vframe.addWidget(self.groupbox_inner_buffer, alignment=Qt.AlignTop)

        self.gridLayout_inner_buffer = QGridLayout(self.groupbox_inner_buffer)
        self.gridLayout_inner_buffer.setContentsMargins(5, 2, 5, 2)
        self.gridLayout_inner_buffer.setColumnStretch(2, 1)
        self.gridLayout_inner_buffer.setObjectName("gridLayout_inner_buffer")

        self.inner_buffer_label = QLabel(self.groupbox_inner_buffer)
        self.inner_buffer_label.setObjectName("inner_buffer_label")
        self.inner_buffer_label.setMinimumWidth(110)
        self.gridLayout_inner_buffer.addWidget(self.inner_buffer_label, 0, 0, 1, 1, alignment=Qt.AlignLeft)

        self.inner_buffer_text = QLineEdit(self.groupbox_inner_buffer)
        self.inner_buffer_text.setObjectName("inner_buffer_text")
        self.gridLayout_inner_buffer.addWidget(self.inner_buffer_text, 0, 1, 1, 1, alignment=Qt.AlignRight)

        self.inner_buffer_m_label = QLabel(self.groupbox_inner_buffer)
        self.inner_buffer_m_label.setObjectName("inner_buffer_m_label")
        self.gridLayout_inner_buffer.addWidget(self.inner_buffer_m_label, 0, 2, 1, 1, alignment=Qt.AlignLeft)

        self.inner_buffer_btn = QPushButton(self.groupbox_wall)
        self.inner_buffer_btn.setFixedSize(50, 50)
        self.inner_buffer_btn.setIconSize(QSize(32, 32))
        self.inner_buffer_btn.setObjectName("inner_buffer_btn")
        self.gridLayout_inner_buffer.addWidget(self.inner_buffer_btn, 0, 3, 1, 1, alignment=Qt.AlignRight)


        # self.build_texture_btn = QPushButton(self.frame)
        # self.build_texture_btn.setObjectName("build_texture_btn")
        # vframe.addWidget(self.build_texture_btn, alignment=Qt.AlignTop)

        self.wiki = QLabel(Form)
        self.wiki.setText("<html><a href=\"https://geoscan.freshdesk.com/support/solutions/35000135997\">"
            + _("Support") + "</a></html>")
        self.wiki.setOpenExternalLinks(True)
        vbox.addWidget(self.wiki, alignment=Qt.AlignBottom)

        walls = QPixmap()
        roof = QPixmap()
        roof_s = QPixmap()
        buffer = QPixmap()
        walls.load(os.path.join(PLUGIN_PATH, "images/Walls_32.png"))
        roof.load(os.path.join(PLUGIN_PATH, "images/Roof_32.png"))
        roof_s.load(os.path.join(PLUGIN_PATH, "images/Roof_S_32.png"))
        buffer.load(os.path.join(PLUGIN_PATH, "images/Buffer_32.png"))

        self.wall_btn.setIcon(walls)
        self.roof_btn.setIcon(roof_s)
        self.inner_buffer_btn.setIcon(buffer)
        self.plane_roof_btn.setIcon(roof)

        self.groupbox_wall.setTitle(_("Wall"))
        self.groupbox_roof.setTitle(_("Roof"))
        self.groupbox_inner_buffer.setTitle(_("Inner buffer polygon"))

        self.height_label.setText(_("Height"))
        self.height_m_label.setText(_("(m)"))
        self.direction.setText(_("Direction"))
        self.direction_list.addItem(_("Down"))
        self.direction_list.addItem(_("Up"))
        self.plane_roof_label.setText(_("Plane roof"))
        self.roof_with_parapet_label.setText(_("Roof with parapet:"))
        self.inside_indent_label.setText(_("Inside indent"))
        self.inside_m_label.setText(_("(m)"))
        self.down_indent_label.setText(_("Down indent"))
        self.down_m_label.setText(_("(m)"))
        self.inner_buffer_label.setText(_("Buffer distance"))
        self.inner_buffer_m_label.setText(_("(m)"))
        # self.build_texture_btn.setText(_("Build texture"))

        # Add button to test something

        # self.test_btn = QPushButton(Form)
        # self.test_btn.setObjectName("test_btn")
        # vbox.addWidget(self.test_btn, alignment=Qt.AlignTop)
        # self.test_btn.setText("Button for test")

# This is code for testing design in IDE

# _ = lambda x: x
# class Form(QWidget, Ui_Form):
#     def __init__(self, parent=None):
#         QWidget.__init__(self, parent)
#
#         self.setupUi(self)
#
# app = QApplication()
# window = Form()
# window.show()
# app.exec_()
