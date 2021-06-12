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

import traceback
from math import ceil, floor
import PhotoScan

from common.loggers.email_logger import log_method_by_crash_reporter
from common.qt_wrapper.qt_wrapper import Window, LineEdit, Button, CheckBox
from common.utils.project import available_extent, Extent, BadProject
from .mesh_generator import MskMeshGenerator


class MskGridGenerator(Window):

    NAME = "Build MSK grid"
    VERSION = "1.0.0"

    def __init__(self):
        super().__init__(_("Generate MSK grid"))
        self.start_group_box(_("Region"))

        self.start_horizontal()
        self.insert_text_label(_("Easting\t"))
        self.__left_x_line_edit = self.add_unit(LineEdit)
        self.__left_x_line_edit.set_validator('int')
        self.insert_text_label("—")
        self.__right_x_line_edit = self.add_unit(LineEdit)
        self.__right_x_line_edit.set_validator('int')
        self.cancel()

        self.start_horizontal()
        self.insert_text_label(_("Northing\t"))
        self.__bottom_y_line_edit = self.add_unit(LineEdit)
        self.__bottom_y_line_edit.set_validator('int')
        self.insert_text_label("—")
        self.__top_y_line_edit = self.add_unit(LineEdit)
        self.__top_y_line_edit.set_validator('int')
        self.cancel()
        self.__zone_in_coords = self.add_unit(CheckBox, _('Zone number in Easting coordinates'), False)
        self.__spb_grid = self.add_unit(CheckBox, _('Create msk grid like SPB grid'), False)
        self.cancel()

        self.start_group_box(_("MSK parameters"))
        self.start_horizontal()
        self.__crs_number = self.add_unit(LineEdit, _('Number:'))
        self.__crs_zone = self.add_unit(LineEdit, _('Zone:'))
        self.__crs_zone.set_validator('int')
        self.cancel()
        self.cancel()

        self.__is_latin = self.add_unit(CheckBox, _('Use latin letters'), False)

        self.__create_btn = self.add_unit(Button, _("Create"), self.__create)
        self.__set_default_region()

    def __set_default_region(self):
        try:
            extent = available_extent()
        except BadProject:
            extent = Extent()

        self.__left_x_line_edit.set_value(floor(extent.left) if extent.left is not None else '')
        self.__right_x_line_edit.set_value(ceil(extent.right) if extent.right is not None else '')
        self.__bottom_y_line_edit.set_value(floor(extent.bottom) if extent.bottom is not None else '')
        self.__top_y_line_edit.set_value(ceil(extent.top) if extent.top is not None else '')

    def __get_region(self):
        try:
            xmin = int(self.__left_x_line_edit.get_value())
            xmax = int(self.__right_x_line_edit.get_value())
            ymin = int(self.__bottom_y_line_edit.get_value())
            ymax = int(self.__top_y_line_edit.get_value())
        except ValueError:
            traceback.print_exc()
            PhotoScan.app.messageBox(_('Wrong values!'))
        else:
            print(xmin, xmax, ymin, ymax)
            region = [
                [xmin, ymin],
                [xmax, ymax]
            ]
            return region

    @log_method_by_crash_reporter(plugin_name=NAME, version=VERSION)
    def __create(self):
        region = self.__get_region()
        if not region:
            return
        crs_number = self.__crs_number.get_value()
        crs_zone = self.__crs_zone.get_value()
        mmg = MskMeshGenerator(
            region=region,
            crs_number=crs_number,
            crs_zone=crs_zone,
            with_zone=self.__zone_in_coords.get_value(),
            spb_grid=self.__spb_grid.get_value(),
            use_latin_letters=self.__is_latin.get_value()
        )
        print(mmg.false_easting)
        PhotoScan.app.update()
        mmg.generate_msk_grid(
            spb_grid=self.__spb_grid.get_value(),
        )
        self.close()

    def log_values(self):
        d = {
            "Easting": (self.__left_x_line_edit.get_value(), self.__right_x_line_edit.get_value()),
            "Northing": (self.__bottom_y_line_edit.get_value(), self.__top_y_line_edit.get_value()),
            "Zone number in Easting coordinates": self.__zone_in_coords.get_value(),
            "Create msk grid like SPB grid": self.__spb_grid.get_value(),
            "Use latin letters": self.__is_latin.get_value(),
            "MSK number": self.__crs_number.get_value(),
            "MSK Zone": self.__crs_zone.get_value(),
        }
        return d


def main(trans=None):
    if trans is not None:
        trans.install()
        _ = trans.gettext
    exporter = MskGridGenerator()
    exporter.show()


if __name__ == "__main__":
    main()
