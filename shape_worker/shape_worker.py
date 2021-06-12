"""Shape worker

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

import numpy as np
import Metashape

from common.qt_wrapper.qt_wrapper import Window, LineEdit, Button, RadioButton
from common.shape_worker import shape_worker as sw
from .mesh_generator import MeshGenerator
from common.loggers.email_logger import log_method_by_crash_reporter


class GridGenerator(Window):

    NAME = "Build grid"
    VERSION = "1.0.1"

    def __init__(self):
        super().__init__(title=_("Generate grid"), size=(400, 300))

        self.start_group_box(_("Region"))
        self.start_horizontal()
        self.__left_x_line_edit = self.add_unit(LineEdit)
        self.__left_x_line_edit.set_validator('double')
        self.insert_text_label("-")
        self.__right_x_line_edit = self.add_unit(LineEdit)
        self.__right_x_line_edit.set_validator('double')
        self.insert_text_label(_("X"))
        self.cancel()

        self.start_horizontal()
        self.__bottom_y_line_edit = self.add_unit(LineEdit)
        self.__bottom_y_line_edit.set_validator('double')
        self.insert_text_label("-")
        self.__top_y_line_edit = self.add_unit(LineEdit)
        self.__top_y_line_edit.set_validator('double')
        self.insert_text_label(_("Y"))
        self.cancel()

        self.__fill_by_shape_btn = self.add_unit(Button, _("Fill by selected shape"), self.__fill_by_selected_shape)
        self.cancel()

        self.__cells_count_radio = self.add_unit(RadioButton, _("Cells count"), default_value=True)
        self.start_horizontal()
        self.__cells_x_count_line_edit = self.add_unit(LineEdit)
        self.__cells_x_count_line_edit.set_validator('double')
        self.__cells_x_count_line_edit.add_enabled_dependency(self.__cells_count_radio)
        self.insert_text_label("x")
        self.__cells_y_count_line_edit = self.add_unit(LineEdit)
        self.__cells_y_count_line_edit.set_validator('double')
        self.__cells_y_count_line_edit.add_enabled_dependency(self.__cells_count_radio)
        self.cancel()

        self.__cell_size_radio = self.add_unit(RadioButton, _("Cell size"), default_value=False)
        self.start_horizontal()
        self.__cell_x_size_line_edit = self.add_unit(LineEdit)
        self.__cell_x_size_line_edit.set_validator('double')
        self.__cell_x_size_line_edit.add_enabled_dependency(self.__cell_size_radio)
        self.insert_text_label("x")
        self.__cell_y_size_line_edit = self.add_unit(LineEdit)
        self.__cell_y_size_line_edit.set_validator('double')
        self.__cell_y_size_line_edit.add_enabled_dependency(self.__cell_size_radio)
        self.cancel()

        self.insert_text_label(_("Overlap"))
        self.start_horizontal()
        self.__x_overlap_line_edit = self.add_unit(LineEdit, default_value=0)
        self.__x_overlap_line_edit.set_validator('double')
        self.insert_text_label("x")
        self.__y_overlap_line_edit = self.add_unit(LineEdit, default_value=0)
        self.__y_overlap_line_edit.set_validator('double')
        self.cancel()

        self.__preview_btn = self.add_unit(Button, _("Generate"), self.__generate)

        self.__preview_shape_group = None

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def __fill_by_selected_shape(self):
        if len(sw.get_selected_shapes()) < 1:
            self.show_message("Select shape")
            return
        elif len(sw.get_selected_shapes()) > 1:
            self.show_message("You select more than one shape.\nPlease select one!")
            return

        chunk = Metashape.app.document.chunk
        shape = sw.get_selected_shapes()[0]

        min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')
        for v in shape.vertices:
            projected_point = Metashape.CoordinateSystem.transform(v, source=chunk.shapes.crs, target=chunk.crs)
            min_x = projected_point.x if projected_point.x < min_x else min_x
            min_y = projected_point.y if projected_point.y < min_y else min_y
            max_x = projected_point.x if projected_point.x > max_x else max_x
            max_y = projected_point.y if projected_point.y > max_y else max_y

        self.__left_x_line_edit.set_value(str(min_x))
        self.__right_x_line_edit.set_value(str(max_x))

        self.__bottom_y_line_edit.set_value(str(min_y))
        self.__top_y_line_edit.set_value(str(max_y))

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def __generate(self):
        if self.__preview_shape_group is None:
            region = np.array([[0, 0], [0, 0]], dtype=np.float64)
            cell_size = np.array([0, 0], dtype=np.float64)
            overlap = np.array([0, 0], dtype=np.float64)
            self.__collect_region_params(region, cell_size, overlap)

            self.__preview_shape_group = sw.create_group("Mesh", show_labels=False)

            try:
                mesh_generator = MeshGenerator(self.__preview_shape_group, region, cell_size, overlap)
            except MeshGenerator.MGException as err:
                self.show_message(str(err))
                return

            mesh_generator.generate_cells()

            self.__preview_btn.set_name(_("Remove"))
        else:
            sw.delete_group(self.__preview_shape_group, with_shapes=True)
            self.__preview_shape_group = None
            self.__preview_btn.set_name(_("Generate"))

    def __collect_region_params(self, region, cell_size, overlap):
        region[0][0] = np.fromstring(self.__left_x_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')
        region[0][1] = np.fromstring(self.__bottom_y_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')
        region[1][0] = np.fromstring(self.__right_x_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')
        region[1][1] = np.fromstring(self.__top_y_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')

        if self.__cell_size_radio.get_value():
            cell_size[0] = np.fromstring(self.__cell_x_size_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')
            cell_size[1] = np.fromstring(self.__cell_y_size_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')
        elif self.__cells_count_radio.get_value():
            cell_size[0] = (region[1][0] - region[0][0]) / int(self.__cells_x_count_line_edit.get_value())
            cell_size[1] = (region[1][1] - region[0][1]) / int(self.__cells_y_count_line_edit.get_value())

        overlap[0] = np.fromstring(self.__x_overlap_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')
        overlap[1] = np.fromstring(self.__y_overlap_line_edit.get_value(), count=1, dtype=np.float64, sep=' ')

    def log_values(self):
        region_coords = self.__left_x_line_edit.get_value(), self.__right_x_line_edit.get_value(), \
                        self.__bottom_y_line_edit.get_value(), self.__top_y_line_edit.get_value()

        d = {
            "Region coords": region_coords,
            "Cells count": (self.__cells_x_count_line_edit.get_value(), self.__cells_y_count_line_edit.get_value()),
            "Cell size": (self.__cell_x_size_line_edit.get_value(), self.__cell_y_size_line_edit.get_value()),
            "Overlap": (self.__x_overlap_line_edit.get_value(), self.__y_overlap_line_edit.get_value()),
        }
        return d


def grid_generator(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    exporter = GridGenerator()
    exporter.show()


if __name__ == "__main__":
    grid_generator()
