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

import Metashape
from PySide2.QtWidgets import QHBoxLayout

from common.utils.ui import show_error
from .FloatUI import FloatUI


class CoordinateUI:
    def __init__(self):
        self.X = FloatUI("X")
        self.Y = FloatUI("Y")
        self.Z = FloatUI("Z")
        self.layout = QHBoxLayout()
        self.layout.addLayout(self.X.layout)
        self.layout.addLayout(self.Y.layout)
        self.layout.addLayout(self.Z.layout)

    def get_vector(self):
        try:
            return Metashape.Vector([float(self.X.value), float(self.Y.value), float(self.Z.value)])
        except ValueError:
            show_error(_("Error!"), _("You must enter valid value to all fields"))
            return None
