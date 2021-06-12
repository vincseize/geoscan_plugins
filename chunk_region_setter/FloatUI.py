"""Set region plugin for Agisoft Metashape

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

from PySide2.QtWidgets import QLabel, QLineEdit, QHBoxLayout

class FloatUI:
    def __init__(self, text):
        self.label = QLabel()
        self.line = QLineEdit()
        self.layout = QHBoxLayout()
        self.line.setText("0")

        self.layout.addWidget(self.label)
        self.layout.addWidget(self.line)
        self.label.setText(text)

    @property
    def value(self):
        return float(self.line.text())
