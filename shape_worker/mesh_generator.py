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
import PhotoScan as ps
from common.shape_worker import shape_worker as sw
from common.utils.bridge import camera_coordinates_to_chunk_crs


class MeshGenerator:
    class MGException(Exception):
        def __init__(self, message: str):
            self.__message = message

        def __str__(self):
            return self.__message

    def __init__(self, shapes_group, region: np.array, cell_size: list, overlap: list = None):
        if (ps.app.document.chunk.region is None) or ps.app.document.chunk.region.size.norm() == 0:
            raise self.MGException("Region size is zero!")

        if region[0][0] >= region[1][0] or region[0][1] >= region[1][1]:
            raise self.MGException("Bad region size")

        if len(cell_size) < 2 or cell_size[0] <= 0 or cell_size[1] <= 0:
            raise self.MGException("Bad cell size")

        if ps.app.document.chunk.shapes.crs is None:
            ps.app.document.chunk.shapes.crs = ps.app.document.chunk.crs

        self.__region = region
        self.__cell_size = cell_size
        self.__overlap = 0.5 * np.array([overlap[0], overlap[1]] if overlap is not None else [0, 0])
        self.__shapes_group_name = shapes_group

    def generate_cells(self):
        def walk_cells(callback: callable):
            y_start = self.__region[1][1] - self.__cell_size[1]
            x_start = self.__region[0][0]

            y = y_start

            step_cnt = np.array(np.ceil(np.abs(self.__region[1] - self.__region[0]) / self.__cell_size),
                                dtype=np.uint64)

            shapes_list = []
            for i in range(step_cnt[1]):
                x = x_start
                row_list = []
                for j in range(step_cnt[0]):
                    shape = callback([np.array([x, y]),
                              np.array([x + self.__cell_size[0], y + self.__cell_size[1]])], [i, j])
                    x += self.__cell_size[0]
                    row_list.append(shape)

                y -= self.__cell_size[1]
                shapes_list.append(row_list)

            return shapes_list

        def on_cell(coords, idx):
            coords[0] -= self.__overlap
            coords[1] += self.__overlap

            z_coord = camera_coordinates_to_chunk_crs(ps.app.document.chunk.region.center)[2]
            vertices = [
                [coords[0][0], coords[0][1], z_coord],
                [coords[0][0], coords[1][1], z_coord],
                [coords[1][0], coords[1][1], z_coord],
                [coords[1][0], coords[0][1], z_coord],
                [coords[0][0], coords[0][1], z_coord]
            ]

            projected_vertices = []
            for v in vertices:
                projected_vertices.append(ps.app.document.chunk.crs.transform(ps.Vector([v[0], v[1], z_coord]),
                                                                              ps.app.document.chunk.crs,
                                                                              ps.app.document.chunk.shapes.crs))

            return sw.create_shape(projected_vertices,
                                   group=self.__shapes_group_name, label="{}-{}".format(idx[0], idx[1]))

        return walk_cells(on_cell)


class MskMeshGenerator:
    """
    Provides grid generation in accordance with accepted local CRS nomenclature in russian geodesy. For PhotoScan.
    """
    LABEL_M2000 = {
        (0, 0): 'А',
        (0, 1): 'Б',
        (1, 0): 'В',
        (1, 1): 'Г',
    }

    LABEL_M2000_LATIN = {
        (0, 0): 'A',
        (0, 1): 'B',
        (1, 0): 'V',
        (1, 1): 'G',
    }

    LABEL_M1000 = {
        (0, 0): 'I',
        (0, 1): 'II',
        (1, 0): 'III',
        (1, 1): 'IV',
    }

    def __init__(self, crs_number, crs_zone, region, with_zone=False, m5000=True, m2000=True, m1000=True, m500=True,
                 spb_grid=False, use_latin_letters=False):
        self.__region = region
        self.crs_number = crs_number
        self.crs_zone = crs_zone
        self.m5000 = m5000
        self.m2000 = m2000
        self.m1000 = m1000
        self.m500 = m500
        self.LABEL_M2000 = self.LABEL_M2000 if not use_latin_letters else self.LABEL_M2000_LATIN

        if spb_grid:
            self.false_easting = 0
            self.__get_start_values_spb()
        else:
            self.false_easting = self.__get_false_easting(with_zone)
            self.__get_start_values()

    def __get_false_easting(self, with_zone):
        if with_zone:
            xmin = self.__region[0][0]
            str_xmin = str(xmin)
            str_xmin = str_xmin[len(self.crs_zone):]
            return xmin-int(str_xmin)
        else:
            return 0

    @staticmethod
    def __column_to_str(column):
        if column >= 0:
            return str(column)
        else:
            return 'з' + str(column)[1:]

    @staticmethod
    def __row_to_str(row):
        if row >= 0:
            return str(row)
        else:
            return 'ю' + str(row)[1:]

    def __get_start_values(self):
        k = 2000
        reg = self.__region

        easting = self.false_easting
        xmin = reg[0][0] - easting
        self.col_start = xmin // k
        self.x_start = self.col_start*k + easting
        self.row_start = reg[0][1]//k
        self.y_start = self.row_start*k

        xmax = reg[1][0] - easting
        self.col_stop = xmax // k
        self.x_end = (self.col_stop + 1) * k + easting
        self.row_stop = reg[1][1] // k
        self.y_end = (self.row_stop + 1) * k

        self.shp_group5000 = sw.create_group("1:5000", show_labels=True)
        self.shp_group2000 = sw.create_group("1:2000", show_labels=True)
        self.shp_group1000 = sw.create_group("1:1000", show_labels=True)
        self.shp_group500 = sw.create_group("1:500", show_labels=True)

        self.k = k

    def __get_start_values_spb(self):
        k = 4
        reg = self.__region

        xmin = (reg[0][0]) // 1000
        self.col_start = xmin // k
        self.x_start = self.col_start * k * 1000
        ymin = (reg[0][1]) // 1000
        self.row_start = ymin // k
        self.y_start = self.row_start * k * 1000

        xmax = (reg[1][0]) // 1000
        self.col_stop = xmax // k
        self.x_end = (self.col_stop + 1) * k * 1000

        ymax = (reg[1][1]) // 1000
        self.row_stop = ymax // k
        self.y_end = (self.row_stop + 1) * k * 1000

        self.shp_group10000 = sw.create_group("1:10000", show_labels=True)
        self.shp_group5000 = sw.create_group("1:5000", show_labels=True)
        self.shp_group2000 = sw.create_group("1:2000", show_labels=True)
        self.shp_group1000 = sw.create_group("1:1000", show_labels=True)
        self.shp_group500 = sw.create_group("1:500", show_labels=True)

        self.k = k

    def __generate_m5000_grid(self, spb_grid_use=False):
        region = np.array([
            [self.x_start, self.y_start],
            [self.x_end, self.y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group5000,
            region=region,
            cell_size=[2000, 2000],
            overlap=None,
        )

        if spb_grid_use:
            self.__generate_m10000_grid(region)
        else:
            head_str = self.crs_number if not self.crs_zone else '-'.join([self.crs_number, self.crs_zone])
            label_pattern = '{}-{{}}-{{}}'.format(head_str)

            shapes_list = mg.generate_cells()
            for i, row in enumerate(shapes_list):
                for j, shape in enumerate(row):
                    self.cur_row, self.cur_col = (self.row_stop - i, self.col_start + j)
                    label = label_pattern.format(self.__row_to_str(self.cur_row), self.__column_to_str(self.cur_col))
                    shape.label = label
                    x_start = self.cur_col * self.k + self.false_easting
                    y_start = self.cur_row * self.k
                    self.__fill_m2000(x_start, y_start, label)

    def __generate_m10000_grid(self, region):

        mg = MeshGenerator(
            shapes_group=self.shp_group10000,
            region=region,
            cell_size=[4000, 4000],
            overlap=None,
        )
        shapes_list = mg.generate_cells()
        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                self.cur_row, self.cur_col = (self.row_stop - i, self.col_start + j)
                label = str(self.cur_row) + str(self.cur_col)
                shape.label = label
                x_start = self.cur_col * 4000
                y_start = self.cur_row * 4000
                self.__fill_m5000_spb(x_start, y_start, label)
                self.__fill_m2000_spb(x_start, y_start, label)

    def __fill_m5000_spb(self, x_start, y_start, label):
        k = 4000
        x_end = x_start + k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group5000,
            region=region,
            cell_size=[k / 2, k / 2],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(self.LABEL_M2000[(i, j)]) # name for 2000 is the same as for m5000 in spb
                shape.label = label

    def __fill_m2000_spb(self, x_start, y_start, label):
        k = 4000
        x_end = x_start + k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group2000,
            region=region,
            cell_size=[k/4, k/4],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        n = len(shapes_list[0])
        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(n*i + j+1)
                shape.label = label
                self.__fill_m1000_spb(x_start, y_start, i, j, label)
                self.__fill_m500_spb(x_start, y_start, i, j, label)

    def __fill_m1000_spb(self, x_start, y_start, i, j, label):
        k = 1000
        x_start = x_start + i * 1000
        y_start = y_start + j * 1000
        x_end = x_start + k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group1000,
            region=region,
            cell_size=[k/2, k/2],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(self.LABEL_M2000[(i, j)]) # name m1000 in spb is the same as for m2000
                shape.label = label

    def __fill_m500_spb(self, x_start, y_start, i, j, label):
        k = 1000
        x_start = x_start + i * 1000
        y_start = y_start + j * 1000
        x_end = x_start + k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group500,
            region=region,
            cell_size=[k/4, k/4],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        n = len(shapes_list[0])
        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(n*i + j+1)
                shape.label = label

    def __fill_m2000(self, x_start, y_start, label):
        k = self.k
        x_end = x_start + k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group2000,
            region=region,
            cell_size=[k/2, k/2],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(self.LABEL_M2000[(i, j)])
                shape.label = label
                self.__fill_m1000(x_start, y_start, len(shapes_list)-i-1, j, label)
                self.__fill_m500(x_start, y_start, len(shapes_list)-i-1, j, label)

    def __fill_m1000(self, x_start, y_start, cur_row2000, cur_col2000, label):
        k = self.k/2
        x_start += cur_col2000 * k
        x_end = x_start + k
        y_start += cur_row2000 * k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group1000,
            region=region,
            cell_size=[k/2, k/2],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(self.LABEL_M1000[(i, j)])
                shape.label = label

    def __fill_m500(self, x_start, y_start, cur_row, cur_col, label):
        k = self.k/2
        x_start += cur_col * k
        x_end = x_start + k
        y_start += cur_row * k
        y_end = y_start + k

        region = np.array([
            [x_start, y_start],
            [x_end, y_end],
        ], dtype=np.float64
        )

        mg = MeshGenerator(
            shapes_group=self.shp_group500,
            region=region,
            cell_size=[k/4, k/4],
            overlap=None
        )

        label_pattern = label + '-{}'
        shapes_list = mg.generate_cells()

        n = len(shapes_list[0])
        for i, row in enumerate(shapes_list):
            for j, shape in enumerate(row):
                label = label_pattern.format(n*i + j+1)
                shape.label = label

    def generate_msk_grid(self, spb_grid=False):
        """
        Generates grid in accordance with accepted local CRS nomenclature in russian geodesy
        :return:
        """
        self.__generate_m5000_grid(spb_grid_use=spb_grid)
